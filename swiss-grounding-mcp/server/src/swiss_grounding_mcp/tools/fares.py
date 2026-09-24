from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote, urlencode

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FareSearchResult
from swiss_grounding_mcp.evidence.provenance import build_provenance
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.resolution import is_swiss_stop, resolve_station

_INTERNATIONAL_FARES_OUT_OF_SCOPE_MESSAGE = (
    "International fare lookups are outside the declared scope of this service. "
    "Please use the SBB official booking link for international pricing."
)

_LIVE_FARES_UNAVAILABLE_MESSAGE = (
    "Live prices are currently redirected to the SBB Official Timetable "
    "due to OJP Fare Beta backend limits."
)


def build_sbb_deep_link(
    origin: str, destination: str, date: str, time: str
) -> str:
    """Return an SBB timetable/booking deep link for the requested journey."""
    base_url = "https://www.sbb.ch/en/timetable.html"
    params = {
        "from": origin,
        "to": destination,
        "date": date,
        "time": time,
    }
    query = urlencode(params, quote_via=quote)
    return f"{base_url}?{query}"


def _split_departure_time(
    departure_time: str | None,
) -> tuple[str, str]:
    """Return (date, time) strings suitable for the SBB deep link.

    Defaults to the current UTC date/time if no departure_time is supplied.
    """
    if departure_time is None:
        dt = datetime.now(timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def check_public_transport_fares(
    origin: str,
    destination: str,
    departure_time: str | None = None,
    travel_class: str = "2",
    discount_card: str | None = None,
    *,
    client,
    settings: Settings,
) -> FareSearchResult:
    if not origin.strip():
        return FareSearchResult(
            status="needs_clarification", message="Please provide an origin station."
        )
    if not destination.strip():
        return FareSearchResult(
            status="needs_clarification",
            message="Please provide a destination station.",
        )

    try:
        origin_candidates = client.location_information(origin)
    except OjpSourceError as exc:
        return FareSearchResult(status="source_error", message=str(exc))

    resolved_origin, failure = resolve_station(origin, origin_candidates, "origin")
    if failure is not None:
        return FareSearchResult(
            status="needs_clarification",
            message=failure.message,
            candidates=failure.candidates,
        )

    try:
        destination_candidates = client.location_information(destination)
    except OjpSourceError as exc:
        return FareSearchResult(status="source_error", message=str(exc))

    resolved_destination, failure = resolve_station(
        destination, destination_candidates, "destination"
    )
    if failure is not None:
        return FareSearchResult(
            status="needs_clarification",
            message=failure.message,
            candidates=failure.candidates,
        )

    travel_date, travel_time = _split_departure_time(departure_time)
    booking_url = build_sbb_deep_link(
        resolved_origin.name,
        resolved_destination.name,
        travel_date,
        travel_time,
    )
    provenance = build_provenance(
        settings,
        source="SBB Official / opentransportdata.swiss",
        booking_url=booking_url,
    )

    if not is_swiss_stop(resolved_origin.stop_ref) or not is_swiss_stop(
        resolved_destination.stop_ref
    ):
        return FareSearchResult(
            status="out_of_scope",
            message=_INTERNATIONAL_FARES_OUT_OF_SCOPE_MESSAGE,
            booking_url=booking_url,
            provenance=provenance,
        )

    try:
        fares = client.fare_request(
            resolved_origin.stop_ref,
            resolved_destination.stop_ref,
            origin_name=resolved_origin.name,
            destination_name=resolved_destination.name,
            departure_time=departure_time,
            travel_class=travel_class,
            discount_card=discount_card,
        )
    except OjpSourceError:
        fares = []

    if fares:
        return FareSearchResult(
            status="success",
            message="Live fares retrieved.",
            fares=fares,
            booking_url=booking_url,
            provenance=provenance,
        )

    return FareSearchResult(
        status="fallback_link",
        message=_LIVE_FARES_UNAVAILABLE_MESSAGE,
        booking_url=booking_url,
        provenance=provenance,
    )
