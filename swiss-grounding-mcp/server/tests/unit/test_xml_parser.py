from pathlib import Path

from swiss_grounding_mcp.sources.ojp.xml_parser import (
    has_service_delivery_error,
    parse_location_information_response,
    parse_trip_response,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ojp"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parse_location_information_single_match():
    candidates = parse_location_information_response(
        _read("lir_response_single_match.xml")
    )

    assert len(candidates) == 1
    assert candidates[0].name == "Bern"
    assert candidates[0].stop_ref == "ch:1:sloid:7000"
    assert candidates[0].probability == 1.0


def test_parse_location_information_multi_match_preserves_order_and_probability():
    candidates = parse_location_information_response(
        _read("lir_response_multi_match.xml")
    )

    assert [c.name for c in candidates] == ["Fribourg/Freiburg", "Freiburg(Breisgau) Hbf"]
    assert candidates[0].probability == 0.62
    assert candidates[1].probability == 0.58


def test_parse_location_information_no_match_returns_empty_list():
    candidates = parse_location_information_response(_read("lir_response_no_match.xml"))

    assert candidates == []


def test_has_service_delivery_error_detects_error_condition():
    message = has_service_delivery_error(_read("lir_response_error.xml"))

    assert message == "Invalid API token"


def test_has_service_delivery_error_returns_none_for_healthy_response():
    message = has_service_delivery_error(_read("lir_response_single_match.xml"))

    assert message is None


def test_parse_trip_response_returns_two_connections_with_legs_and_changes():
    connections = parse_trip_response(_read("trip_response_two_trips.xml"))

    assert len(connections) == 2

    direct = connections[0]
    assert direct.departure == "2026-09-24T18:04:00Z"
    assert direct.arrival == "2026-09-24T18:57:00Z"
    assert direct.duration_minutes == 53
    assert direct.changes == 0
    assert len(direct.legs) == 1
    assert direct.legs[0].line == "IC 8"
    assert direct.legs[0].from_name == "Bern"
    assert direct.legs[0].to_name == "Zürich HB"

    with_change = connections[1]
    assert with_change.duration_minutes == 103
    assert with_change.changes == 1
    assert len(with_change.legs) == 2
    assert with_change.legs[0].line == "IR 15"
    assert with_change.legs[1].line == "S8"
