from __future__ import annotations

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import ConnectionSearchResult
from swiss_grounding_mcp.evidence.provenance import build_provenance
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.resolution import is_swiss_stop, resolve_station

_OUT_OF_SCOPE_MESSAGE = (
    "This service covers Swiss public transport and cross-border journeys "
    "connecting to Switzerland. Purely foreign transit outside Switzerland "
    "is outside the declared scope."
)


def find_train_connections(
    origin: str,
    destination: str,
    departure_time: str | None,
    arrival_time: str | None,
    results: int,
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

    try:
        origin_candidates = client.location_information(origin)
    except OjpSourceError as exc:
        return ConnectionSearchResult(status="source_error", message=str(exc))

    resolved_origin, failure = resolve_station(origin, origin_candidates, "origin")
    if failure is not None:
        return failure

    try:
        destination_candidates = client.location_information(destination)
    except OjpSourceError as exc:
        return ConnectionSearchResult(status="source_error", message=str(exc))

    resolved_destination, failure = resolve_station(
        destination, destination_candidates, "destination"
    )
    if failure is not None:
        return failure

    if not is_swiss_stop(resolved_origin.stop_ref) and not is_swiss_stop(
        resolved_destination.stop_ref
    ):
        return ConnectionSearchResult(
            status="out_of_scope", message=_OUT_OF_SCOPE_MESSAGE
        )

    effective_departure_time = departure_time
    effective_arrival_time = arrival_time if departure_time is None else None
    time_note = ""
    if departure_time is not None and arrival_time is not None:
        effective_arrival_time = None
        time_note = " Both departure_time and arrival_time were given; departure_time was used."

    try:
        connections = client.trip_request(
            resolved_origin.stop_ref,
            resolved_destination.stop_ref,
            origin_name=resolved_origin.name,
            destination_name=resolved_destination.name,
            departure_time=effective_departure_time,
            arrival_time=effective_arrival_time,
            number_of_results=clamped_results,
        )
    except OjpSourceError as exc:
        return ConnectionSearchResult(status="source_error", message=str(exc))

    if not connections:
        return ConnectionSearchResult(
            status="not_found",
            message=(
                f"No connections found between '{resolved_origin.name}' and "
                f"'{resolved_destination.name}' for the requested time."
            ),
        )

    return ConnectionSearchResult(
        status="ok",
        message=("Connections found." + time_note) if time_note else None,
        connections=connections[:clamped_results],
        provenance=build_provenance(settings),
    )
