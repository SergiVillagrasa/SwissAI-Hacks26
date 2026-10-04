from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FareSearchResult, Provenance
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.resolution import is_swiss_stop, resolve_station

_ZURICH_TZ = ZoneInfo("Europe/Zurich")

_INTERNATIONAL_FARES_OUT_OF_SCOPE_MESSAGE = (
    "International fare lookups are outside the declared scope of this service. "
    "Please use the SBB official booking link for international pricing."
)

_LIVE_FARES_UNAVAILABLE_MESSAGE = (
    "Live fare prices are not available for this journey right now. "
    "Use the SBB booking link below for official pricing."
)


def build_sbb_deep_link(
    origin: str,
    destination: str,
    travel_date: str | None = None,
) -> str:
    """Return an SBB timetable deep link for the requested journey.

    Only *origin* and *destination* are required.  ``travel_date`` is
    optional (``YYYY-MM-DD``); when omitted the SBB website defaults to
    today.
    """
    base_url = "https://sbb.ch/en"
    params: dict[str, str] = {
        "von": origin,
        "nach": destination,
    }
    if travel_date is not None:
        params["date"] = travel_date
    query = urlencode(params, quote_via=quote)
    return f"{base_url}?{query}"


def extract_travel_date(departure_time: str | None) -> str | None:
    """Return the ``YYYY-MM-DD`` portion of an ISO-8601 datetime in Swiss
    local time (Europe/Zurich), or *None*.

    OJP and aviation timestamps are UTC. Naively slicing the first ten
    characters of such a string reports the wrong calendar day whenever the
    UTC instant falls on one side of midnight but the Zurich-local instant
    falls on the other (e.g. a 23:10 UTC departure is already past
    midnight in Zurich) -- which produces an SBB deep link for the wrong
    date. Converting to Europe/Zurich before formatting avoids that.
    """
    if departure_time is None:
        return None
    try:
        dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_ZURICH_TZ).strftime("%Y-%m-%d")


def _build_provenance(
    booking_url: str,
) -> Provenance:
    """Build a ``Provenance`` whose ``source_url`` is the SBB deep link."""
    return Provenance(
        source="SBB Official / opentransportdata.swiss",
        source_url=booking_url,
        retrieved_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        booking_url=booking_url,
    )


def check_public_transport_fares(
    origin: str,
    destination: str,
    departure_time: str | None = None,
    travel_class: str = "2",
    discount_card: str | None = None,
    sort_by: str | None = None,
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
        # resolve_station reports either "not_found" (no match at all, e.g.
        # a typo like "Zuerch") or "needs_clarification" (ambiguous match).
        # Neither means the journey is outside the declared scope -- a
        # misspelled or ambiguous *Swiss* station must not be reported as
        # out_of_scope, which would incorrectly suggest the service does
        # not cover it at all.
        return FareSearchResult(
            status=failure.status,
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
            status=failure.status,
            message=failure.message,
            candidates=failure.candidates,
        )

    travel_date = extract_travel_date(departure_time)
    booking_url = build_sbb_deep_link(
        resolved_origin.name,
        resolved_destination.name,
        travel_date,
    )
    provenance = _build_provenance(booking_url)

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
        sorted_by = None
        if sort_by == "price":
            fares = sorted(fares, key=lambda fare: fare.price_chf)
            sorted_by = "price"
        return FareSearchResult(
            status="success",
            message="Live fares retrieved.",
            fares=fares,
            booking_url=booking_url,
            provenance=provenance,
            sorted_by=sorted_by,
        )

    return FareSearchResult(
        status="fallback_link",
        message=_LIVE_FARES_UNAVAILABLE_MESSAGE,
        booking_url=booking_url,
        provenance=provenance,
    )
