from __future__ import annotations

from typing import Any

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.tools.connect_flight_to_train import connect_flight_to_train
from swiss_grounding_mcp.tools.fares import check_public_transport_fares
from swiss_grounding_mcp.tools.find_connections import find_train_connections
from swiss_grounding_mcp.tools.find_disruptions import find_station_disruptions
from swiss_grounding_mcp.tools.find_flight_by_number import find_flight_by_number
from swiss_grounding_mcp.tools.get_airport_guidance import get_airport_guidance
from swiss_grounding_mcp.tools.search_airport_flights import search_airport_flights
from swiss_grounding_mcp.tools.station_timetable import get_station_board


class UnknownToolError(Exception):
    def __init__(self, tool_name: str):
        super().__init__(f"Unknown tool: {tool_name}")
        self.tool_name = tool_name


def dispatch(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    ojp_client,
    aviation_client,
    settings: Settings,
):
    if tool_name == "find_connections":
        return find_train_connections(
            arguments["origin"],
            arguments["destination"],
            arguments.get("departure_time"),
            arguments.get("arrival_time"),
            arguments.get("results", 3),
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
            arguments.get("results", 5),
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
            client=ojp_client,
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
            arguments.get("limit", 10),
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
            arguments["transfer_buffer_minutes"],
            arguments.get("rail_results", 3),
            aviation_client=aviation_client,
            ojp_client=ojp_client,
            settings=settings,
        )
    raise UnknownToolError(tool_name)
