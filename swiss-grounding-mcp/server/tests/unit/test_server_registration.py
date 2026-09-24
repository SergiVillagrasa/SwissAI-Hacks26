import asyncio

from mcp import Client

from swiss_grounding_mcp.domain.models import Connection, StopCandidate
from swiss_grounding_mcp.server import mcp
import swiss_grounding_mcp.server as server_module


class StubClient:
    def location_information(self, name):
        return [StopCandidate(name=name, stop_ref=f"ch:1:sloid:{abs(hash(name)) % 9999}", probability=1.0)]

    def trip_request(self, *args, **kwargs):
        return [
            Connection(
                departure="2026-09-24T18:04:00Z",
                arrival="2026-09-24T18:57:00Z",
                duration_minutes=53,
                changes=0,
                legs=[],
            )
        ]

    def get_stop_events(self, *args, **kwargs):
        return []


def test_find_connections_tool_is_registered_and_callable(monkeypatch):
    monkeypatch.setattr(server_module, "get_client", lambda: StubClient())

    async def run():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools.tools]
            assert "find_connections" in names
            assert "get_station_board" in names

            result = await client.call_tool(
                "find_connections", {"origin": "Bern", "destination": "Zürich HB"}
            )
            assert result.structured_content["status"] == "ok"
            assert len(result.structured_content["connections"]) == 1

    asyncio.run(run())


class StubAviationstackClient:
    def get_flights(self, params):
        return {
            "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 1},
            "data": [
                {
                    "flight_date": params.get("flight_date", "2026-09-25"),
                    "flight_status": "scheduled",
                    "departure": {
                        "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH",
                        "icao": "LSZH", "terminal": "1", "gate": "A12", "delay": None,
                        "scheduled": "2026-09-25T10:20:00+00:00", "estimated": None, "actual": None,
                    },
                    "arrival": {
                        "airport": "JFK", "timezone": "America/New_York", "iata": "JFK",
                        "icao": "KJFK", "terminal": "4", "gate": None, "delay": None,
                        "scheduled": "2026-09-25T13:10:00+00:00", "estimated": None, "actual": None,
                    },
                    "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
                    "flight": {"number": "14", "iata": "LX14", "icao": "SWR14", "codeshared": None},
                    "aircraft": None,
                    "live": None,
                }
            ],
        }


def test_aviation_tools_are_registered_and_callable(monkeypatch):
    monkeypatch.setattr(server_module, "get_client", lambda: StubClient())
    monkeypatch.setattr(server_module, "get_aviation_client", lambda: StubAviationstackClient())

    async def run():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools.tools]
            for expected in [
                "find_flight_by_number",
                "search_airport_flights",
                "get_airport_guidance",
                "connect_flight_to_train",
            ]:
                assert expected in names

            flight_result = await client.call_tool(
                "find_flight_by_number", {"flight_number": "LX14", "flight_date": "2026-09-25"}
            )
            assert flight_result.structured_content["status"] == "answered"

            guidance_result = await client.call_tool(
                "get_airport_guidance", {"topic": "transfers"}
            )
            assert guidance_result.structured_content["status"] == "answered"

            connect_result = await client.call_tool(
                "connect_flight_to_train",
                {
                    "flight_number": None,
                    "flight_date": None,
                    "confirmed_arrival_time": "2026-09-25T22:00:00+00:00",
                    "destination_station": "Bern",
                    "transfer_buffer_minutes": 30,
                    "rail_results": 3,
                },
            )
            assert connect_result.structured_content["status"] == "answered"

    asyncio.run(run())
