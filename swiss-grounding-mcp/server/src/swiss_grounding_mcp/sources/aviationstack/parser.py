from __future__ import annotations

from swiss_grounding_mcp.domain.models import AirlineInfo, AirportInfo, Flight, FlightEndpoint

_ENDPOINT_FIELD_NAMES = ["scheduled", "estimated", "actual", "terminal", "gate"]


def _parse_endpoint(endpoint_json: dict | None) -> FlightEndpoint:
    endpoint_json = endpoint_json or {}
    airport = AirportInfo(
        iata=endpoint_json.get("iata"),
        icao=endpoint_json.get("icao"),
        name=endpoint_json.get("airport"),
        timezone=endpoint_json.get("timezone"),
    )
    return FlightEndpoint(
        airport=airport,
        scheduled=endpoint_json.get("scheduled"),
        estimated=endpoint_json.get("estimated"),
        actual=endpoint_json.get("actual"),
        terminal=endpoint_json.get("terminal"),
        gate=endpoint_json.get("gate"),
        delay_minutes=endpoint_json.get("delay"),
    )


def parse_flights(body: dict) -> list[Flight]:
    flights: list[Flight] = []
    for item in body.get("data", []):
        flight_info = item.get("flight") or {}
        airline_json = item.get("airline") or {}
        flights.append(
            Flight(
                flight_number=flight_info.get("iata") or flight_info.get("icao") or "",
                flight_date=item.get("flight_date", ""),
                airline=AirlineInfo(
                    name=airline_json.get("name"),
                    iata=airline_json.get("iata"),
                    icao=airline_json.get("icao"),
                ),
                departure=_parse_endpoint(item.get("departure")),
                arrival=_parse_endpoint(item.get("arrival")),
                flight_status=item.get("flight_status"),
            )
        )
    return flights


def flight_field_presence(flight_json: dict) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for side in ("departure", "arrival"):
        side_json = flight_json.get(side) or {}
        for field_name in _ENDPOINT_FIELD_NAMES:
            path = f"{side}.{field_name}"
            if side_json.get(field_name) is not None:
                present.append(path)
            else:
                missing.append(path)
    return present, missing
