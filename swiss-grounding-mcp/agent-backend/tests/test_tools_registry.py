from agent_backend.tools_registry import TOOL_NAMES, TOOL_SCHEMAS

_EXPECTED_NAMES = {
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


def test_tool_names_match_expected_set():
    assert TOOL_NAMES == _EXPECTED_NAMES


def test_every_schema_is_well_formed_openai_function_tool():
    assert len(TOOL_SCHEMAS) == len(_EXPECTED_NAMES)
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        function = schema["function"]
        assert function["name"] in _EXPECTED_NAMES
        assert function["description"]
        assert function["parameters"]["type"] == "object"
        assert "properties" in function["parameters"]


def test_find_connections_requires_origin_and_destination():
    schema = next(
        s for s in TOOL_SCHEMAS if s["function"]["name"] == "find_connections"
    )
    assert set(schema["function"]["parameters"]["required"]) == {
        "origin",
        "destination",
    }


def test_get_flight_fares_requires_origin_and_destination_city():
    schema = next(
        s for s in TOOL_SCHEMAS if s["function"]["name"] == "get_flight_fares"
    )
    assert set(schema["function"]["parameters"]["required"]) == {
        "origin_city",
        "destination_city",
    }
