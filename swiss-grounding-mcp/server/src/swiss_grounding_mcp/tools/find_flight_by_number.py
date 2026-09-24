from __future__ import annotations

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FlightLookupResult
from swiss_grounding_mcp.evidence.aviation_provenance import build_aviation_provenance
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackSourceError
from swiss_grounding_mcp.sources.aviationstack.parser import (
    flight_field_presence,
    parse_flights,
)


def _normalize_flight_number(value: str) -> str:
    return value.strip().upper().replace(" ", "")


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
    # Note: the `flight_date` query parameter is a restricted function on
    # Aviationstack's free tier (confirmed live: HTTP 403
    # function_access_restricted). To keep this tool working on any plan
    # tier, we never send flight_date to the API; instead we fetch the
    # flight_iata's small rolling window of recent/current occurrences and
    # filter by the requested date ourselves.
    params: dict[str, str] = {"flight_iata": normalized_number}
    if direction == "arrival":
        params["arr_iata"] = "ZRH"
    elif direction == "departure":
        params["dep_iata"] = "ZRH"

    try:
        body = client.get_flights(params)
    except AviationstackSourceError as exc:
        return FlightLookupResult(status="source_unavailable", message=str(exc))

    raw_flights = [
        item for item in body.get("data", []) if item.get("flight_date") == flight_date
    ]
    if not raw_flights:
        return FlightLookupResult(
            status="insufficient_evidence",
            message=(
                f"No flight found for '{flight_number}' on {flight_date}. This may "
                "also mean the requested date falls outside the aviation data "
                "provider's currently available window."
            ),
        )

    flights = parse_flights({"data": raw_flights})
    fields_present, fields_missing = flight_field_presence(raw_flights[0])

    return FlightLookupResult(
        status="answered",
        flight=flights[0],
        fields_present=fields_present,
        fields_missing=fields_missing,
        provenance=build_aviation_provenance(settings, applicable_date=flight_date),
    )
