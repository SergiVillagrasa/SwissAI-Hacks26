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

    def fare_request(self, *args, **kwargs):
        return []


def test_find_connections_tool_is_registered_and_callable(monkeypatch):
    monkeypatch.setattr(server_module, "get_client", lambda: StubClient())

    async def run():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools.tools]
            assert "find_connections" in names
            assert "get_station_board" in names
            assert "check_public_transport_fares" in names

            result = await client.call_tool(
                "find_connections", {"origin": "Bern", "destination": "Zürich HB"}
            )
            assert result.structured_content["status"] == "ok"
            assert len(result.structured_content["connections"]) == 1

            fares_result = await client.call_tool(
                "check_public_transport_fares",
                {"origin": "Bern", "destination": "Zürich HB"},
            )
            assert fares_result.structured_content["status"] == "fallback_link"
            assert "sbb.ch" in fares_result.structured_content["booking_url"]

    asyncio.run(run())
