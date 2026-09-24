from __future__ import annotations

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FlightLookupResult
from swiss_grounding_mcp.evidence.aviation_provenance import build_aviation_provenance
from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxSourceError
from swiss_grounding_mcp.sources.aerodatabox.parser import (
    flight_field_presence,
    parse_flight_items,
)

_ZRH_IATA = "ZRH"


def _normalize_flight_number(value: str) -> str:
    return value.strip().upper().replace(" ", "")


def _matches_direction(item: dict, direction: str | None) -> bool:
    if direction is None:
        return True
    side = "departure" if direction == "departure" else "arrival"
    airport = (item.get(side) or {}).get("airport") or {}
    return airport.get("iata") == _ZRH_IATA


def find_flight_by_number(
    flight_number: str,
    flight_date: str,
    direction: str | None,
    *,
    client,
    settings: Settings,
) -> FlightLookupResult:
    if not flight_number or not flight_number.strip():
        return FlightLookupResult(
            status="needs_context",
            message="Please provide a flight number, e.g. 'LX14'.",
        )
    if not flight_date or not flight_date.strip():
        return FlightLookupResult(
            status="needs_context",
            message="Please provide a flight date in YYYY-MM-DD format.",
        )

    normalized_number = _normalize_flight_number(flight_number)

    try:
        items = client.get_flight_by_number(normalized_number, flight_date)
    except AerodataboxSourceError as exc:
        return FlightLookupResult(status="source_unavailable", message=str(exc))

    matching_items = [item for item in items if _matches_direction(item, direction)]
    if not matching_items:
        return FlightLookupResult(
            status="insufficient_evidence",
            message=f"No flight found for '{flight_number}' on {flight_date}.",
        )

    flights = parse_flight_items(matching_items)
    fields_present, fields_missing = flight_field_presence(matching_items[0])

    return FlightLookupResult(
        status="answered",
        flight=flights[0],
        fields_present=fields_present,
        fields_missing=fields_missing,
        provenance=build_aviation_provenance(settings, applicable_date=flight_date),
    )
