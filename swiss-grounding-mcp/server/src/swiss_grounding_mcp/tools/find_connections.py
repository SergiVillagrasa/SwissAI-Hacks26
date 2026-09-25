from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import ConnectionSearchResult
from swiss_grounding_mcp.evidence.provenance import build_provenance
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.resolution import is_swiss_stop, resolve_station

_LIR_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ojp-lir")

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

    origin_future = _LIR_POOL.submit(client.location_information, origin)
    destination_future = _LIR_POOL.submit(client.location_information, destination)

    try:
        origin_candidates = origin_future.result()
    except OjpSourceError as exc:
        return ConnectionSearchResult(status="source_error", message=str(exc))

    resolved_origin, failure = resolve_station(origin, origin_candidates, "origin")
    if failure is not None:
        failure.provenance = build_provenance(settings)
        return failure

    try:
        destination_candidates = destination_future.result()
    except OjpSourceError as exc:
        return ConnectionSearchResult(status="source_error", message=str(exc))

    # Fast scope check before any disambiguation: if neither side could
    # possibly resolve to a Swiss stop (resolved stop or any LIR
    # candidate), no user pick can produce a Swiss-connected journey --
    # answer out_of_scope directly instead of entering a clarification
    # loop on foreign stations that can never succeed.
    def _could_be_swiss(resolved, candidates) -> bool:
        if resolved is not None:
            return is_swiss_stop(resolved.stop_ref)
        if not candidates:
            return True  # unresolvable input -> let the failure path answer
        return any(is_swiss_stop(c.stop_ref) for c in candidates)

    resolved_origin, origin_failure = resolve_station(
        origin, origin_candidates, "origin"
    )
    resolved_destination, destination_failure = resolve_station(
        destination, destination_candidates, "destination"
    )
    if not _could_be_swiss(resolved_origin, origin_candidates) and not _could_be_swiss(
        resolved_destination, destination_candidates
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
        return ConnectionSearchResult(
            status="not_found",
            message=(
                f"No connections found between '{resolved_origin.name}' and "
                f"'{resolved_destination.name}' for the requested time."
            ),
            provenance=build_provenance(settings),
        )

    if used_margin:
        time_note += _MARGIN_NOTE

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
    )
