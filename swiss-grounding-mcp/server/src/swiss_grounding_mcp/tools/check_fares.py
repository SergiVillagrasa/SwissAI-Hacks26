from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FareProduct, FareResult, StopCandidate
from swiss_grounding_mcp.evidence.provenance import build_provenance
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError

_DOMINANT_MATCH_MARGIN = 0.3
_FARES_SOURCE = "SBB/CFF/FFS tariff information"
_FARES_SOURCE_URL = "https://www.sbb.ch/en/tickets-railtravel/fares.html"

# Curated point-to-point full-fare and discount examples for frequently
# requested Swiss routes. Prices are indicative and should be refreshed from
# the official SBB price list periodically.
_FARE_TABLE: dict[frozenset[str], list[FareProduct]] = {
    frozenset({"bern", "zurich hb"}): [
        FareProduct(product="Point-to-point ticket", price_chf=51.0, class_of_travel=2, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=25.5, class_of_travel=2, discount="half-fare"),
        FareProduct(product="Point-to-point ticket", price_chf=88.0, class_of_travel=1, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=44.0, class_of_travel=1, discount="half-fare"),
        FareProduct(product="Saver Day Pass", price_chf=59.0, class_of_travel=2, discount="none"),
    ],
    frozenset({"geneve", "zurich hb"}): [
        FareProduct(product="Point-to-point ticket", price_chf=92.0, class_of_travel=2, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=46.0, class_of_travel=2, discount="half-fare"),
        FareProduct(product="Point-to-point ticket", price_chf=160.0, class_of_travel=1, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=80.0, class_of_travel=1, discount="half-fare"),
        FareProduct(product="Saver Day Pass", price_chf=59.0, class_of_travel=2, discount="none"),
    ],
    frozenset({"basel sbb", "zurich hb"}): [
        FareProduct(product="Point-to-point ticket", price_chf=36.0, class_of_travel=2, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=18.0, class_of_travel=2, discount="half-fare"),
        FareProduct(product="Point-to-point ticket", price_chf=62.0, class_of_travel=1, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=31.0, class_of_travel=1, discount="half-fare"),
        FareProduct(product="Saver Day Pass", price_chf=59.0, class_of_travel=2, discount="none"),
    ],
    frozenset({"lausanne", "bern"}): [
        FareProduct(product="Point-to-point ticket", price_chf=55.0, class_of_travel=2, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=27.5, class_of_travel=2, discount="half-fare"),
        FareProduct(product="Point-to-point ticket", price_chf=95.0, class_of_travel=1, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=47.5, class_of_travel=1, discount="half-fare"),
        FareProduct(product="Saver Day Pass", price_chf=59.0, class_of_travel=2, discount="none"),
    ],
    frozenset({"luzern", "zurich hb"}): [
        FareProduct(product="Point-to-point ticket", price_chf=31.0, class_of_travel=2, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=15.5, class_of_travel=2, discount="half-fare"),
        FareProduct(product="Point-to-point ticket", price_chf=54.0, class_of_travel=1, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=27.0, class_of_travel=1, discount="half-fare"),
        FareProduct(product="Saver Day Pass", price_chf=59.0, class_of_travel=2, discount="none"),
    ],
    frozenset({"genf", "zurich hb"}): [
        FareProduct(product="Point-to-point ticket", price_chf=92.0, class_of_travel=2, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=46.0, class_of_travel=2, discount="half-fare"),
        FareProduct(product="Point-to-point ticket", price_chf=160.0, class_of_travel=1, discount="none"),
        FareProduct(product="Point-to-point ticket", price_chf=80.0, class_of_travel=1, discount="half-fare"),
        FareProduct(product="Saver Day Pass", price_chf=59.0, class_of_travel=2, discount="none"),
    ],
}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.strip().lower()


def _canonical_name(stop_ref: str, name: str) -> str:
    """Map a resolved station ref or name to the canonical name used by the fare table."""
    aliases = {
        "zurich hb": ["zurich hb", "zurich hauptbahnhof", "zuerich hb", "zürich hauptbahnhof"],
        "bern": ["bern"],
        "geneve": ["geneve", "genf", "ginevra", "geneva"],
        "basel sbb": ["basel sbb", "basel", "basilea"],
        "lausanne": ["lausanne", "losanna"],
        "luzern": ["luzern", "lucerne", "lucerna"],
    }
    normalized = _normalize(name)
    for canonical, names in aliases.items():
        if normalized in names:
            return canonical
    return normalized


def _resolve_station(
    query: str, candidates: list[StopCandidate], field_name: str
) -> tuple[StopCandidate | None, FareResult | None]:
    if not candidates:
        return None, FareResult(
            status="not_found",
            message=f"No Swiss station matches {field_name} '{query}'.",
        )

    if len(candidates) == 1:
        return candidates[0], None

    normalized_query = _normalize(query)
    for candidate in candidates:
        if _normalize(candidate.name) == normalized_query:
            return candidate, None

    ranked = sorted(candidates, key=lambda c: c.probability or 0.0, reverse=True)
    best, second = ranked[0], ranked[1]
    if (best.probability or 0.0) - (second.probability or 0.0) >= _DOMINANT_MATCH_MARGIN:
        return best, None

    return None, FareResult(
        status="needs_clarification",
        message=f"Multiple stations match {field_name} '{query}'. Please pick one.",
        candidates=ranked,
    )


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(date_value: str | None) -> tuple[str | None, str | None]:
    if date_value is None:
        return None, None
    if not _ISO_DATE_RE.match(date_value):
        return None, f"travel_date '{date_value}' is not a valid ISO date (YYYY-MM-DD)."
    try:
        datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError:
        return None, f"travel_date '{date_value}' is not a valid calendar date."
    return date_value, None


def _normalize_discount(discount: str | None) -> str:
    if discount is None:
        return "any"
    normalized = _normalize(discount)
    if normalized in {"none", "full", "full-fare", "regular", "ohne", "standard"}:
        return "none"
    if normalized in {
        "half-fare",
        "halbtax",
        "demi-tarif",
        "demi tarif",
        "meta-prezzo",
        "mezzo-prezzo",
        "50%",
        "50",
    }:
        return "half-fare"
    if normalized in {"junior", "child", "children", "kids", "enfant", "bambino"}:
        return "junior"
    if normalized in {"senior", "pensioner", "retired", "senior", "pensionato", "retraite"}:
        return "senior"
    if normalized in {"ga", "general-abonnement", "abonnement-general", "generalabonnement", "abbonamento-generale"}:
        return "ga"
    return normalized


def _lookup_fares(
    origin: StopCandidate, destination: StopCandidate, travel_class: int, discount: str
) -> list[FareProduct]:
    origin_key = _canonical_name(origin.stop_ref, origin.name)
    destination_key = _canonical_name(destination.stop_ref, destination.name)
    all_products = _FARE_TABLE.get(frozenset({origin_key, destination_key}), [])

    if not all_products:
        return []

    if discount == "ga":
        return [FareProduct(product="General Abonnement", price_chf=0.0, class_of_travel=travel_class, discount="ga")]

    products = [p for p in all_products if p.class_of_travel == travel_class]
    if discount != "any":
        products = [p for p in products if p.discount == discount]

    return products


def check_public_transport_fares(
    origin: str,
    destination: str,
    travel_class: int = 2,
    discount: str | None = None,
    travel_date: str | None = None,
    *,
    client,
    settings: Settings,
) -> FareResult:
    if not origin.strip():
        return FareResult(
            status="needs_clarification", message="Please provide an origin station."
        )
    if not destination.strip():
        return FareResult(
            status="needs_clarification", message="Please provide a destination station."
        )

    if travel_class not in (1, 2):
        return FareResult(
            status="needs_clarification",
            message="travel_class must be 1 (first class) or 2 (second class).",
        )

    validated_date, date_error = _validate_date(travel_date)
    if date_error:
        return FareResult(status="needs_clarification", message=date_error)

    normalized_discount = _normalize_discount(discount)

    try:
        origin_candidates = client.location_information(origin)
    except OjpSourceError as exc:
        return FareResult(status="source_error", message=str(exc))

    resolved_origin, failure = _resolve_station(origin, origin_candidates, "origin")
    if failure is not None:
        return failure

    try:
        destination_candidates = client.location_information(destination)
    except OjpSourceError as exc:
        return FareResult(status="source_error", message=str(exc))

    resolved_destination, failure = _resolve_station(
        destination, destination_candidates, "destination"
    )
    if failure is not None:
        return failure

    products = _lookup_fares(resolved_origin, resolved_destination, travel_class, normalized_discount)
    if not products:
        return FareResult(
            status="not_found",
            message=(
                f"No fare information is available for the route "
                f"'{resolved_origin.name}' to '{resolved_destination.name}'. "
                "This tool currently covers selected popular Swiss routes only."
            ),
        )

    date_note = f" for travel on {validated_date}" if validated_date else ""
    discount_note = (
        f" with discount '{normalized_discount}'"
        if discount and normalized_discount != "any"
        else ""
    )
    message = f"Found fares from '{resolved_origin.name}' to '{resolved_destination.name}'{discount_note}{date_note}. Prices are indicative."

    return FareResult(
        status="ok",
        message=message,
        origin=resolved_origin.name,
        destination=resolved_destination.name,
        currency="CHF",
        products=products,
        provenance=build_provenance(
            settings,
            source=_FARES_SOURCE,
            source_url=_FARES_SOURCE_URL,
            retrieved_at=datetime.now(timezone.utc),
        ),
    )
