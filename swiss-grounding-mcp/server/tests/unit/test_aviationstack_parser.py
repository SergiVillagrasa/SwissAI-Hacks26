import json
from pathlib import Path

from swiss_grounding_mcp.sources.aviationstack.parser import (
    flight_field_presence,
    parse_flights,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "aviationstack"


def _read_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_parse_flights_maps_all_core_fields():
    body = _read_json("lx14_zrh_jfk.json")

    flights = parse_flights(body)

    assert len(flights) == 1
    flight = flights[0]
    assert flight.flight_number == "LX14"
    assert flight.flight_date == "2026-09-25"
    assert flight.airline.iata == "LX"
    assert flight.departure.airport.iata == "ZRH"
    assert flight.departure.scheduled == "2026-09-25T10:20:00+00:00"
    assert flight.departure.estimated == "2026-09-25T10:25:00+00:00"
    assert flight.departure.actual is None
    assert flight.departure.gate == "A12"
    assert flight.departure.delay_minutes == 5
    assert flight.arrival.airport.iata == "JFK"
    assert flight.flight_status == "scheduled"


def test_parse_flights_returns_empty_list_for_empty_data():
    body = _read_json("empty.json")

    assert parse_flights(body) == []


def test_flight_field_presence_reports_present_and_missing_fields():
    body = _read_json("lx14_partial_fields.json")
    flight_json = body["data"][0]

    present, missing = flight_field_presence(flight_json)

    assert "departure.scheduled" in present
    assert "departure.actual" in present
    assert "departure.terminal" in missing
    assert "departure.gate" in missing
    assert "arrival.estimated" in missing
    assert "arrival.actual" in missing
    assert "arrival.terminal" in present
