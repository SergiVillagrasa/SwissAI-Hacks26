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


class StubAerodataboxClient:
    def get_flight_by_number(self, flight_number, date_local):
        return [
            {
                "number": "LX 14",
                "status": "Scheduled",
                "airline": {"name": "Swiss", "iata": "LX", "icao": "SWR"},
                "departure": {
                    "airport": {"iata": "ZRH", "icao": "LSZH", "name": "Zurich"},
                    "scheduledTime": {"utc": f"{date_local} 10:20Z"},
                    "revisedTime": None,
                    "runwayTime": None,
                    "terminal": "1",
                    "gate": "A12",
                },
                "arrival": {
                    "airport": {"iata": "JFK", "icao": "KJFK", "name": "JFK"},
                    "scheduledTime": {"utc": f"{date_local} 13:10Z"},
                    "revisedTime": None,
                    "runwayTime": None,
                    "terminal": "4",
                    "gate": None,
                },
            }
        ]


def test_aviation_tools_are_registered_and_callable(monkeypatch):
    monkeypatch.setattr(server_module, "get_client", lambda: StubClient())
    monkeypatch.setattr(server_module, "get_aviation_client", lambda: StubAerodataboxClient())

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
