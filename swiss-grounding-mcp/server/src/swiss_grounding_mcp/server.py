from __future__ import annotations

import argparse

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import ConnectionSearchResult, FareResult
from swiss_grounding_mcp.sources.ojp.client import OjpClient
from swiss_grounding_mcp.tools.check_fares import check_public_transport_fares
from swiss_grounding_mcp.tools.find_connections import find_train_connections

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
def check_fares(
    origin: str,
    destination: str,
    travel_class: int = 2,
    discount: str | None = None,
    travel_date: str | None = None,
) -> FareResult:
    """Check indicative public-transport fares and tickets for Swiss routes.

    Scope: selected popular point-to-point routes within Switzerland.
    Covers full-fare and common discount prices (Half Fare / Halbtax,
    first/second class, saver day passes) based on SBB/CFF/FFS tariff
    information. Does not cover municipal zone fares, season tickets,
    international travel, or real-time dynamic prices. If the route is
    outside the curated fare table, this tool will say so rather than guess.
    """
    return check_public_transport_fares(
        origin,
        destination,
        travel_class,
        discount,
        travel_date,
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
