import json
from pathlib import Path

from swiss_grounding_mcp.sources.aerodatabox.parser import (
    flight_field_presence,
    parse_airport_flights,
    parse_flight_items,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "aerodatabox"


def _read_json(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_parse_flight_items_maps_core_fields_and_normalizes_timestamps():
    items = _read_json("lx14_by_number.json")

    flights = parse_flight_items(items)

    assert len(flights) == 1
    flight = flights[0]
    assert flight.flight_number == "LX14"
    assert flight.flight_date == "2026-09-25"
    assert flight.airline.iata == "LX"
    assert flight.departure.airport.iata == "ZRH"
    assert flight.departure.scheduled == "2026-09-25T10:20:00Z"
    assert flight.departure.estimated == "2026-09-25T10:25:00Z"
    assert flight.departure.actual is None
    assert flight.departure.terminal == "1"
    assert flight.departure.gate == "A12"
    assert flight.departure.delay_minutes == 5
    assert flight.arrival.airport.iata == "JFK"
    assert flight.arrival.estimated is None
    assert flight.flight_status == "Scheduled"


def test_parse_flight_items_returns_empty_list_for_empty_array():
    items = _read_json("empty_by_number.json")

    assert parse_flight_items(items) == []


def test_flight_field_presence_reports_present_and_missing_fields():
    items = _read_json("lx14_by_number.json")
    item = items[0]

    present, missing = flight_field_presence(item)

    assert "departure.scheduled" in present
    assert "departure.estimated" in present
    assert "departure.actual" in missing
    assert "departure.terminal" in present
    assert "arrival.estimated" in missing
    assert "arrival.gate" in missing


def test_parse_airport_flights_extracts_both_directions_from_fids_body():
    body = _read_json("zrh_fids.json")

    flights = parse_airport_flights(body)

    assert len(flights) == 2
    assert {f.flight_number for f in flights} == {"LX14", "LX16"}
    assert all(f.departure.airport.iata == "ZRH" for f in flights)
