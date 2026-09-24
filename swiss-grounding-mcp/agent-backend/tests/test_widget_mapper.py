import pytest
from swiss_grounding_mcp.domain.models import (
    ConnectionSearchResult,
    FareSearchResult,
    FlightFareSearchResult,
    FlightLookupResult,
    StopCandidate,
)

from agent_backend.widget_mapper import WIDGET_TYPES, map_result
from agent_backend.dispatch import UnknownToolError


def test_widget_types_cover_all_nine_tools():
    assert set(WIDGET_TYPES) == {
        "find_connections",
        "find_disruptions",
        "get_station_board",
        "check_public_transport_fares",
        "get_flight_fares",
        "find_flight_by_number",
        "search_airport_flights",
        "get_airport_guidance",
        "connect_flight_to_train",
    }
    assert WIDGET_TYPES["find_connections"] == "train_connections"
    assert WIDGET_TYPES["check_public_transport_fares"] == "fares"
    assert WIDGET_TYPES["get_flight_fares"] == "flight_fares"
    assert WIDGET_TYPES["find_flight_by_number"] == "flight"
    assert WIDGET_TYPES["connect_flight_to_train"] == "flight_to_train"


def test_map_result_ok_connections():
    result = ConnectionSearchResult(status="ok", connections=[])
    mapped = map_result("find_connections", result)

    assert mapped["widget_type"] == "train_connections"
    assert mapped["status"] == "ok"
    assert mapped["data"]["connections"] == []


def test_map_result_needs_clarification_with_candidates():
    result = ConnectionSearchResult(
        status="needs_clarification",
        message="Which Fribourg?",
        candidates=[StopCandidate(name="Fribourg/Freiburg", stop_ref="8504100")],
    )
    mapped = map_result("find_connections", result)

    assert mapped["status"] == "needs_clarification"
    assert mapped["data"]["candidates"][0]["name"] == "Fribourg/Freiburg"


def test_map_result_fares_fallback_link():
    result = FareSearchResult(status="fallback_link", booking_url="https://sbb.ch/x")
    mapped = map_result("check_public_transport_fares", result)

    assert mapped["widget_type"] == "fares"
    assert mapped["status"] == "fallback_link"
    assert mapped["data"]["booking_url"] == "https://sbb.ch/x"


def test_map_result_flight_fares_ok():
    result = FlightFareSearchResult(status="ok", flights=[])
    mapped = map_result("get_flight_fares", result)

    assert mapped["widget_type"] == "flight_fares"
    assert mapped["status"] == "ok"
    assert mapped["data"]["flights"] == []


def test_map_result_flight_source_unavailable():
    result = FlightLookupResult(status="source_unavailable", message="quota exceeded")
    mapped = map_result("find_flight_by_number", result)

    assert mapped["widget_type"] == "flight"
    assert mapped["status"] == "source_unavailable"
    assert mapped["data"]["flight"] is None


def test_map_result_unknown_tool_raises():
    with pytest.raises(UnknownToolError):
        map_result("not_a_real_tool", ConnectionSearchResult(status="ok"))
