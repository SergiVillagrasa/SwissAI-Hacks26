from __future__ import annotations

from pydantic import BaseModel

from agent_backend.dispatch import UnknownToolError

WIDGET_TYPES: dict[str, str] = {
    "find_connections": "train_connections",
    "find_disruptions": "disruptions",
    "get_station_board": "station_board",
    "check_public_transport_fares": "fares",
    "find_flight_by_number": "flight",
    "search_airport_flights": "flight_search",
    "get_airport_guidance": "airport_guidance",
    "connect_flight_to_train": "flight_to_train",
}


def map_result(tool_name: str, result: BaseModel) -> dict:
    widget_type = WIDGET_TYPES.get(tool_name)
    if widget_type is None:
        raise UnknownToolError(tool_name)
    return {
        "widget_type": widget_type,
        "status": result.status,
        "data": result.model_dump(),
    }
