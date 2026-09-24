from __future__ import annotations

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import StationBoardResult
from swiss_grounding_mcp.evidence.provenance import build_provenance
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.resolution import is_swiss_stop, resolve_station

_MAX_RESULTS = 10

_MODE_ALIASES = {
    "departure": "departure",
    "departures": "departure",
    "dep": "departure",
    "arrival": "arrival",
    "arrivals": "arrival",
    "arr": "arrival",
}

_OUT_OF_SCOPE_MESSAGE = (
    "This service covers Swiss public transport only. "
    "Stations outside the Swiss network are outside the declared scope."
)


def get_station_board(
    station: str,
    mode: str = "departures",
    when: str | None = None,
    results: int = 5,
    *,
    client,
    settings: Settings,
) -> StationBoardResult:
    if not station.strip():
        return StationBoardResult(
            status="needs_clarification",
            message="Please provide a station name.",
        )

    event_type = _MODE_ALIASES.get(mode.strip().lower())
    if event_type is None:
        return StationBoardResult(
            status="needs_clarification",
            message="Mode must be 'departures' or 'arrivals'.",
        )

    clamped_results = max(1, min(_MAX_RESULTS, results))

    try:
        candidates = client.location_information(station)
    except OjpSourceError as exc:
        return StationBoardResult(status="source_error", message=str(exc))

    resolved, failure = resolve_station(station, candidates, "station")
    if failure is not None:
        return StationBoardResult(
            status=failure.status,
            message=failure.message,
            candidates=failure.candidates,
        )

    if not is_swiss_stop(resolved.stop_ref):
        return StationBoardResult(
            status="out_of_scope", message=_OUT_OF_SCOPE_MESSAGE
        )

    try:
        events = client.get_stop_events(
            resolved.stop_ref,
            event_type=event_type,
            when=when,
            limit=clamped_results,
            station_name=resolved.name,
        )
    except OjpSourceError as exc:
        return StationBoardResult(status="source_error", message=str(exc))

    if not events:
        return StationBoardResult(
            status="not_found",
            message=(
                f"No {event_type}s found at '{resolved.name}' "
                "for the requested time."
            ),
            station_name=resolved.name,
            event_type=event_type,
        )

    return StationBoardResult(
        status="ok",
        station_name=resolved.name,
        event_type=event_type,
        events=events[:clamped_results],
        provenance=build_provenance(settings),
    )
