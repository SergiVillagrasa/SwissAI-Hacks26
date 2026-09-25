from __future__ import annotations

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import (
    DisruptionSearchResult,
)
from swiss_grounding_mcp.evidence.provenance import build_provenance
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.resolution import resolve_station


def find_station_disruptions(
    stop: str,
    *,
    client,
    settings: Settings,
) -> DisruptionSearchResult:

    if not stop.strip():
        return DisruptionSearchResult(
            status="needs_clarification",
            message="Please provide a station.",
        )

    try:
        candidates = client.location_information(stop)

    except OjpSourceError as exc:
        return DisruptionSearchResult(
            status="source_error",
            message=str(exc),
        )

    resolved_stop, failure = resolve_station(
        stop,
        candidates,
        "stop",
    )

    if failure is not None:
        return DisruptionSearchResult(
            status=failure.status,
            message=failure.message,
            candidates=failure.candidates,
            provenance=build_provenance(settings),
        )

    try:
        disruptions = client.stop_events(
            resolved_stop.stop_ref,
            stop_name=resolved_stop.name,
            number_of_results=10,
        )

    except OjpSourceError as exc:
        return DisruptionSearchResult(
            status="source_error",
            message=str(exc),
        )

    if not disruptions:
        return DisruptionSearchResult(
            status="not_found",
            message=f"No current disruptions found at '{resolved_stop.name}'.",
            provenance=build_provenance(settings),
        )

    return DisruptionSearchResult(
        status="ok",
        message=f"Found {len(disruptions)} affected service(s).",
        disruptions=disruptions,
        provenance=build_provenance(settings),
    )