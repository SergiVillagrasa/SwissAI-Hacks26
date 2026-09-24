from __future__ import annotations

import argparse

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import (
    ConnectionSearchResult,
    DisruptionSearchResult,
    StationBoardResult,
)
from swiss_grounding_mcp.sources.ojp.client import OjpClient
from swiss_grounding_mcp.tools.find_connections import find_train_connections
from swiss_grounding_mcp.tools.find_disruptions import find_station_disruptions
from swiss_grounding_mcp.tools.station_timetable import (
    get_station_board as get_station_board_impl,
)

load_dotenv()

settings = Settings.from_env()
mcp = MCPServer("Swiss Grounding MCP")

_client: OjpClient | None = None


def get_client() -> OjpClient:
    global _client
    if _client is None:
        _client = OjpClient(settings)
    return _client


@mcp.tool()
def find_connections(
    origin: str,
    destination: str,
    departure_time: str | None = None,
    arrival_time: str | None = None,
    results: int = 3,
) -> ConnectionSearchResult:
    """Find Swiss passenger-train connections between two stations.

    Scope: the current Swiss public-transport timetable only, via OJP 2.0
    (opentransportdata.swiss). Covers origin-to-destination connection
    search with an optional departure or arrival time. Does not cover
    fares, single-stop departure boards, disruption feeds, or non-Swiss
    travel. If the origin or destination is outside Switzerland, is not a
    recognizable station, or the question is unrelated to travel, this
    tool will say so rather than guess.
    """
    return find_train_connections(
        origin,
        destination,
        departure_time,
        arrival_time,
        results,
        client=get_client(),
        settings=settings,
    )

@mcp.tool()
def find_disruptions(
    stop: str,
) -> DisruptionSearchResult:
    """Find current public-transport disruptions affecting a Swiss station.

    Uses current real-time OJP 2.0 stop-event information.
    Covers cancellations, delays, and boarding/alighting restrictions
    affecting services at the requested station.
    """
    return find_station_disruptions(
        stop,
        client=get_client(),
        settings=settings,
    )


@mcp.tool()
def get_station_board(
    station: str,
    mode: str = "departures",
    when: str | None = None,
    results: int = 5,
) -> StationBoardResult:
    """Show upcoming departures or arrivals at a Swiss public-transport stop.

    Scope: station boards for stops in the Swiss network only, via OJP 2.0
    (opentransportdata.swiss). `mode` is 'departures' (default) or
    'arrivals'; `when` is an optional ISO 8601 timestamp (defaults to now);
    `results` is capped at 10. Stations outside Switzerland are refused as
    out of scope rather than guessed.
    """
    return get_station_board_impl(
        station,
        mode,
        when,
        results,
        client=get_client(),
        settings=settings,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Swiss Grounding MCP server")
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http"], default="stdio"
    )
    parser.add_argument("--host", default=settings.mcp_http_host)
    parser.add_argument("--port", type=int, default=settings.mcp_http_port)
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
