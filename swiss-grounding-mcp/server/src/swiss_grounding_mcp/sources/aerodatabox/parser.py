from __future__ import annotations

from datetime import datetime

from swiss_grounding_mcp.domain.booking_links import build_flight_booking_url
from swiss_grounding_mcp.domain.models import AirlineInfo, AirportInfo, Flight, FlightEndpoint

_ADB_UTC_FORMAT = "%Y-%m-%d %H:%MZ"
_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_ENDPOINT_TIME_FIELDS = ["scheduledTime", "revisedTime", "runwayTime"]
_ENDPOINT_STRING_FIELDS = ["terminal", "gate"]
_TIME_FIELD_ALIASES = {
    "scheduledTime": "scheduled",
    "revisedTime": "estimated",
    "runwayTime": "actual",
}


def _normalize_utc(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, _ADB_UTC_FORMAT)
    except ValueError:
        return value
    return parsed.strftime(_ISO_FORMAT)


def _time_field_utc(endpoint_json: dict, field_name: str) -> str | None:
    field = endpoint_json.get(field_name)
    if not field:
        return None
    return field.get("utc")


def _delay_minutes(endpoint_json: dict) -> int | None:
    scheduled = _time_field_utc(endpoint_json, "scheduledTime")
    revised = _time_field_utc(endpoint_json, "revisedTime")
    if not scheduled or not revised:
        return None
    try:
        scheduled_dt = datetime.strptime(scheduled, _ADB_UTC_FORMAT)
        revised_dt = datetime.strptime(revised, _ADB_UTC_FORMAT)
    except ValueError:
        return None
    return round((revised_dt - scheduled_dt).total_seconds() / 60)


def _normalize_flight_number(raw_number: str) -> str:
    return raw_number.strip().upper().replace(" ", "")


def _parse_endpoint(endpoint_json: dict | None) -> FlightEndpoint:
    endpoint_json = endpoint_json or {}
    airport_json = endpoint_json.get("airport") or {}
    airport = AirportInfo(
        iata=airport_json.get("iata"),
        icao=airport_json.get("icao"),
        name=airport_json.get("name"),
        timezone=None,
    )
    return FlightEndpoint(
        airport=airport,
        scheduled=_normalize_utc(_time_field_utc(endpoint_json, "scheduledTime")),
        estimated=_normalize_utc(_time_field_utc(endpoint_json, "revisedTime")),
        actual=_normalize_utc(_time_field_utc(endpoint_json, "runwayTime")),
        terminal=endpoint_json.get("terminal"),
        gate=endpoint_json.get("gate"),
        delay_minutes=_delay_minutes(endpoint_json),
    )


def _flight_date_from_item(item: dict) -> str:
    departure_scheduled = _time_field_utc(item.get("departure") or {}, "scheduledTime")
    normalized = _normalize_utc(departure_scheduled)
    if normalized:
        return normalized.split("T")[0]
    return ""


def parse_flight_items(items: list[dict]) -> list[Flight]:
    flights: list[Flight] = []
    for item in items:
        airline_json = item.get("airline") or {}
        raw_number = item.get("number") or item.get("callSign") or ""
        airline = AirlineInfo(
            name=airline_json.get("name"),
            iata=airline_json.get("iata"),
            icao=airline_json.get("icao"),
        )
        departure = _parse_endpoint(item.get("departure"))
        arrival = _parse_endpoint(item.get("arrival"))
        flight_date = _flight_date_from_item(item)
        flights.append(
            Flight(
                flight_number=_normalize_flight_number(raw_number),
                flight_date=flight_date,
                airline=airline,
                departure=departure,
                arrival=arrival,
                flight_status=item.get("status"),
                booking_url=build_flight_booking_url(
                    airline.iata,
                    airline.icao,
                    departure.airport.iata,
                    arrival.airport.iata,
                    flight_date or None,
                    origin_icao=departure.airport.icao,
                    destination_icao=arrival.airport.icao,
                ),
            )
        )
    return flights


def flight_field_presence(item: dict) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for side in ("departure", "arrival"):
        side_json = item.get(side) or {}
        for field_name in _ENDPOINT_TIME_FIELDS:
            path = f"{side}.{_TIME_FIELD_ALIASES[field_name]}"
            if _time_field_utc(side_json, field_name) is not None:
                present.append(path)
            else:
                missing.append(path)
        for field_name in _ENDPOINT_STRING_FIELDS:
            path = f"{side}.{field_name}"
            if side_json.get(field_name) is not None:
                present.append(path)
            else:
                missing.append(path)
    return present, missing


def parse_airport_flights(body: dict) -> list[Flight]:
    items = list(body.get("departures", [])) + list(body.get("arrivals", []))
    return parse_flight_items(items)
