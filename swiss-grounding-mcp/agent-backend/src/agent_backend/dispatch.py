from __future__ import annotations

from typing import Any

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.tools.connect_flight_to_train import connect_flight_to_train
from swiss_grounding_mcp.tools.fares import check_public_transport_fares
from swiss_grounding_mcp.tools.find_connections import find_train_connections
from swiss_grounding_mcp.tools.find_disruptions import find_station_disruptions
from swiss_grounding_mcp.tools.find_flight_by_number import find_flight_by_number
from swiss_grounding_mcp.tools.flight_fares import get_flight_fares
from swiss_grounding_mcp.tools.get_airport_guidance import get_airport_guidance
from swiss_grounding_mcp.tools.search_airport_flights import search_airport_flights
from swiss_grounding_mcp.tools.station_timetable import get_station_board


class UnknownToolError(Exception):
    def __init__(self, tool_name: str):
        super().__init__(f"Unknown tool: {tool_name}")
        self.tool_name = tool_name


def _coerce_int(value: Any, default: int) -> int:
    """Best-effort int coercion for LLM-supplied tool arguments.

    The model's function-calling output is JSON, but a numeric parameter
    can still arrive as a numeric string (e.g. "3") or other odd type.
    Tool implementations do unguarded arithmetic on these (e.g.
    ``max(1, min(5, results))``), which raises TypeError when comparing a
    str to an int. Falling back to *default* on anything uncoercible keeps
    dispatch robust instead of crashing the whole turn.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def dispatch(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    ojp_client,
    aviation_client,
    settings: Settings,
    flight_fares_client=None,
):
    if tool_name == "find_connections":
        return find_train_connections(
            arguments["origin"],
            arguments["destination"],
            arguments.get("departure_time"),
            arguments.get("arrival_time"),
            _coerce_int(arguments.get("results"), 3),
            arguments.get("sort_by"),
            arguments.get("via"),
            client=ojp_client,
            settings=settings,
        )
    if tool_name == "find_disruptions":
        return find_station_disruptions(
            arguments["stop"], client=ojp_client, settings=settings
        )
    if tool_name == "get_station_board":
        return get_station_board(
            arguments["station"],
            arguments.get("mode", "departures"),
            arguments.get("when"),
            _coerce_int(arguments.get("results"), 5),
            client=ojp_client,
            settings=settings,
        )
    if tool_name == "check_public_transport_fares":
        return check_public_transport_fares(
            arguments["origin"],
            arguments["destination"],
            departure_time=arguments.get("departure_time"),
            travel_class=arguments.get("travel_class", "2"),
            discount_card=arguments.get("discount_card"),
            sort_by=arguments.get("sort_by"),
            client=ojp_client,
            settings=settings,
        )
    if tool_name == "get_flight_fares":
        return get_flight_fares(
            arguments["origin_city"],
            arguments["destination_city"],
            arguments.get("outbound_date"),
            arguments.get("currency", "CHF"),
            client=flight_fares_client,
            settings=settings,
        )
    if tool_name == "find_flight_by_number":
        return find_flight_by_number(
            arguments["flight_number"],
            arguments["flight_date"],
            arguments.get("direction"),
            client=aviation_client,
            settings=settings,
        )
    if tool_name == "search_airport_flights":
        return search_airport_flights(
            arguments["direction"],
            arguments["flight_date"],
            arguments.get("airport_iata"),
            arguments.get("airport_icao"),
            arguments.get("airline_iata"),
            _coerce_int(arguments.get("limit"), 10),
            client=aviation_client,
            settings=settings,
        )
    if tool_name == "get_airport_guidance":
        return get_airport_guidance(arguments["topic"])
    if tool_name == "connect_flight_to_train":
        return connect_flight_to_train(
            arguments.get("flight_number"),
            arguments.get("flight_date"),
            arguments.get("confirmed_arrival_time"),
            arguments["destination_station"],
            _coerce_int(arguments.get("transfer_buffer_minutes"), 0),
            _coerce_int(arguments.get("rail_results"), 3),
            aviation_client=aviation_client,
            ojp_client=ojp_client,
            settings=settings,
        )
    raise UnknownToolError(tool_name)
