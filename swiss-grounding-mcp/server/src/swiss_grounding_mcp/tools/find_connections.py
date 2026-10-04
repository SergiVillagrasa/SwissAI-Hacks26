from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import ConnectionSearchResult
from swiss_grounding_mcp.evidence.provenance import build_provenance
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.resolution import is_swiss_stop, resolve_station

# 3 workers: one each for the concurrent origin, destination, and (when
# requested) via LocationInformationRequest lookups below, so all three
# can run in parallel instead of queuing behind each other.
_LIR_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ojp-lir")

_OUT_OF_SCOPE_MESSAGE = (
    "This service covers Swiss public transport and cross-border journeys "
    "connecting to Switzerland. Purely foreign transit outside Switzerland "
    "is outside the declared scope."
)

_MARGIN_NOTE = (
    " No connection matched the exact requested time, so nearby "
    "connections within a small margin are shown instead."
)


def _shift_iso_time(value: str, minutes: float) -> str | None:
    """Shift an ISO 8601 timestamp by *minutes* (may be negative).

    Returns None if *value* cannot be parsed, so callers can fall back to
    the original not-found behaviour instead of guessing.
    """
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    shifted = dt + timedelta(minutes=minutes)
    return shifted.strftime("%Y-%m-%dT%H:%M:%SZ")


def find_train_connections(
    origin: str,
    destination: str,
    departure_time: str | None,
    arrival_time: str | None,
    results: int,
    sort_by: str | None = None,
    via: str | None = None,
    *,
    client,
    settings: Settings,
) -> ConnectionSearchResult:
    if not origin.strip():
        return ConnectionSearchResult(
            status="needs_clarification", message="Please provide an origin station."
        )
    if not destination.strip():
        return ConnectionSearchResult(
            status="needs_clarification", message="Please provide a destination station."
        )

    clamped_results = max(1, min(5, results))
    # Guard the type before calling .strip(): an LLM-supplied tool argument
    # is JSON, so `via` could in principle arrive as a non-string (e.g. a
    # number or bool) rather than the declared str | None, which would
    # otherwise raise AttributeError here instead of degrading gracefully.
    via = via.strip() if isinstance(via, str) and via.strip() else None

    origin_future = _LIR_POOL.submit(client.location_information, origin)
    destination_future = _LIR_POOL.submit(client.location_information, destination)
    via_future = _LIR_POOL.submit(client.location_information, via) if via else None

    # Resolve origin and destination together before making any scope or
    # disambiguation decision. Both lookups were already launched
    # concurrently above; blocking on origin's result first and returning
    # early on its failure (as a previous version of this function did)
    # meant a foreign, ambiguous, or unresolvable origin always triggered a
    # clarification request even when the destination alone already
    # proved the whole journey out of scope -- e.g. "Paris" to "Lyon"
    # would ask the user to disambiguate "Paris" instead of answering
    # out_of_scope immediately. Gathering both results first lets the
    # combined scope check below run before any such early return.
    try:
        origin_candidates = origin_future.result()
    except OjpSourceError as exc:
        return ConnectionSearchResult(status="source_error", message=str(exc))
    try:
        destination_candidates = destination_future.result()
    except OjpSourceError as exc:
        return ConnectionSearchResult(status="source_error", message=str(exc))

    resolved_origin, origin_failure = resolve_station(origin, origin_candidates, "origin")
    resolved_destination, destination_failure = resolve_station(
        destination, destination_candidates, "destination"
    )

    # Resolve via (if requested) before the scope check below, not after:
    # a foreign origin and destination with a Swiss via stop (e.g. Paris to
    # Milan via Bern) is still an in-scope, Swiss-connected journey, so the
    # scope decision must already know about via by the time it's made.
    resolved_via = None
    via_candidates: list = []
    via_failure = None
    if via_future is not None:
        try:
            via_candidates = via_future.result()
        except OjpSourceError as exc:
            return ConnectionSearchResult(status="source_error", message=str(exc))
        resolved_via, via_failure = resolve_station(via, via_candidates, "via station")

    # Fast scope check before any disambiguation: if neither the origin,
    # the destination, nor a requested via stop could possibly resolve to
    # a Swiss stop (resolved stop or any LIR candidate), no user pick can
    # produce a Swiss-connected journey -- answer out_of_scope directly
    # instead of entering a clarification loop on foreign stations that
    # can never succeed.
    def _could_be_swiss(resolved, candidates) -> bool:
        if resolved is not None:
            return is_swiss_stop(resolved.stop_ref)
        if not candidates:
            return True  # unresolvable input -> let the failure path answer
        return any(is_swiss_stop(c.stop_ref) for c in candidates)

    # A via that was never requested can't rescue an otherwise out-of-scope
    # route, so it only counts toward scope when the caller actually gave one.
    via_could_be_swiss = bool(via) and _could_be_swiss(resolved_via, via_candidates)

    if (
        not _could_be_swiss(resolved_origin, origin_candidates)
        and not _could_be_swiss(resolved_destination, destination_candidates)
        and not via_could_be_swiss
    ):
        return ConnectionSearchResult(
            status="out_of_scope",
            message=_OUT_OF_SCOPE_MESSAGE,
            provenance=build_provenance(settings),
        )

    if origin_failure is not None:
        origin_failure.provenance = build_provenance(settings)
        return origin_failure
    if destination_failure is not None:
        destination_failure.provenance = build_provenance(settings)
        return destination_failure
    if via_failure is not None:
        via_failure.provenance = build_provenance(settings)
        return via_failure

    effective_departure_time = departure_time
    effective_arrival_time = arrival_time if departure_time is None else None
    time_note = ""
    if departure_time is not None and arrival_time is not None:
        effective_arrival_time = None
        time_note = " Both departure_time and arrival_time were given; departure_time was used."

    def _search(dep_time: str | None, arr_time: str | None):
        return client.trip_request(
            resolved_origin.stop_ref,
            resolved_destination.stop_ref,
            origin_name=resolved_origin.name,
            destination_name=resolved_destination.name,
            departure_time=dep_time,
            arrival_time=arr_time,
            number_of_results=clamped_results,
            via_ref=resolved_via.stop_ref if resolved_via else None,
            via_name=resolved_via.name if resolved_via else "",
        )

    try:
        connections = _search(effective_departure_time, effective_arrival_time)
    except OjpSourceError as exc:
        return ConnectionSearchResult(status="source_error", message=str(exc))

    # A precise departure/arrival time that misses the actual timetable by
    # a minute or two (e.g. "18:00" when the train leaves at 18:01) should
    # not be reported as "not found". Retry once with a small margin before
    # giving up, widening the search in the direction that still satisfies
    # the user's request (earlier for a departure floor, later for an
    # arrival deadline).
    used_margin = False
    if not connections:
        margin = settings.trip_time_margin_minutes
        if effective_departure_time is not None:
            shifted = _shift_iso_time(effective_departure_time, -margin)
            if shifted is not None:
                try:
                    connections = _search(shifted, None)
                    used_margin = bool(connections)
                except OjpSourceError as exc:
                    return ConnectionSearchResult(status="source_error", message=str(exc))
        elif effective_arrival_time is not None:
            shifted = _shift_iso_time(effective_arrival_time, margin)
            if shifted is not None:
                try:
                    connections = _search(None, shifted)
                    used_margin = bool(connections)
                except OjpSourceError as exc:
                    return ConnectionSearchResult(status="source_error", message=str(exc))

    if not connections:
        via_note = f" via '{resolved_via.name}'" if resolved_via else ""
        return ConnectionSearchResult(
            status="not_found",
            message=(
                f"No connections found between '{resolved_origin.name}' and "
                f"'{resolved_destination.name}'{via_note} for the requested time."
            ),
            provenance=build_provenance(settings),
        )

    if used_margin:
        time_note += _MARGIN_NOTE

    for connection in connections:
        connection.origin_latitude = resolved_origin.latitude
        connection.origin_longitude = resolved_origin.longitude
        connection.destination_latitude = resolved_destination.latitude
        connection.destination_longitude = resolved_destination.longitude

    sorted_by = None
    if sort_by == "departure":
        connections = sorted(
            connections,
            key=lambda c: (c.departure, c.duration_minutes, c.changes),
        )
        sorted_by = "departure"

    return ConnectionSearchResult(
        status="ok",
        message=("Connections found." + time_note) if time_note else None,
        connections=connections[:clamped_results],
        provenance=build_provenance(settings),
        sorted_by=sorted_by,
        via_stop_name=resolved_via.name if resolved_via else None,
    )
