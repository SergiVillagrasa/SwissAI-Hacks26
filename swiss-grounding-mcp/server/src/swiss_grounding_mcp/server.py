from __future__ import annotations

import argparse

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import (
    AirportGuidanceResult,
    ConnectionSearchResult,
    DisruptionSearchResult,
    FareSearchResult,
    FlightFareSearchResult,
    FlightLookupResult,
    FlightSearchResult,
    FlightToTrainResult,
    StationBoardResult,
)
from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxClient
from swiss_grounding_mcp.sources.ojp.client import OjpClient
from swiss_grounding_mcp.sources.serpapi.flight_client import SerpApiFlightClient
from swiss_grounding_mcp.tools.connect_flight_to_train import (
    connect_flight_to_train as _connect_flight_to_train,
)
from swiss_grounding_mcp.tools.fares import (
    check_public_transport_fares as _check_public_transport_fares,
)
from swiss_grounding_mcp.tools.find_connections import find_train_connections
from swiss_grounding_mcp.tools.find_disruptions import find_station_disruptions
from swiss_grounding_mcp.tools.flight_fares import get_flight_fares as _get_flight_fares
from swiss_grounding_mcp.tools.find_flight_by_number import (
    find_flight_by_number as _find_flight_by_number,
)
from swiss_grounding_mcp.tools.get_airport_guidance import (
    get_airport_guidance as _get_airport_guidance,
)
from swiss_grounding_mcp.tools.search_airport_flights import (
    search_airport_flights as _search_airport_flights,
)
from swiss_grounding_mcp.tools.station_timetable import (
    get_station_board as get_station_board_impl,
)

load_dotenv()

settings = Settings.from_env()
mcp = MCPServer("Swiss Grounding MCP")

_client: OjpClient | None = None
_aviation_client: AerodataboxClient | None = None
_flight_fares_client: SerpApiFlightClient | None = None


def get_client() -> OjpClient:
    global _client
    if _client is None:
        _client = OjpClient(settings)
    return _client


def get_aviation_client() -> AerodataboxClient:
    global _aviation_client
    if _aviation_client is None:
        _aviation_client = AerodataboxClient(settings)
    return _aviation_client


def get_flight_fares_client() -> SerpApiFlightClient:
    global _flight_fares_client
    if _flight_fares_client is None:
        _flight_fares_client = SerpApiFlightClient(settings)
    return _flight_fares_client


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


@mcp.tool()
def check_public_transport_fares(
    origin: str,
    destination: str,
    departure_time: str | None = None,
    travel_class: str = "2",
    discount_card: str | None = None,
) -> FareSearchResult:
    """Check public-transport fares between two Swiss stations.

    Scope: Swiss domestic public-transport fares only, via the OJP Fare
    Beta endpoint (opentransportdata.swiss). `travel_class` defaults to
    second class; `discount_card` may be set to a supported card such as
    "Halbtax". If live fare data is unavailable, the response includes a
    pre-populated SBB booking deep link for official pricing. International
    routes and ambiguous station names are refused rather than guessed.
    """
    return _check_public_transport_fares(
        origin,
        destination,
        departure_time=departure_time,
        travel_class=travel_class,
        discount_card=discount_card,
        client=get_client(),
        settings=settings,
    )


@mcp.tool()
def get_flight_fares(
    origin_city: str,
    destination_city: str,
    outbound_date: str | None = None,
    currency: str = "CHF",
) -> FlightFareSearchResult:
    """Find current commercial flight fares between supported Swiss airports.

    Scope: domestic Swiss routes only, using SerpApi Google Flights results.
    Supported locations are Zurich, Geneva, Basel/Mulhouse, Lugano,
    St. Gallen/Altenrhein, and Sion. The date defaults to tomorrow and the
    currency defaults to CHF. Foreign routes are refused rather than queried.
    """
    return _get_flight_fares(
        origin_city,
        destination_city,
        outbound_date,
        currency,
        client=get_flight_fares_client(),
        settings=settings,
    )


@mcp.tool()
def find_flight_by_number(
    flight_number: str,
    flight_date: str,
    direction: str | None = None,
) -> FlightLookupResult:
    """Look up a flight at Zurich Airport (ZRH) by flight number and date.

    Scope: scheduled/estimated/actual times, terminal, gate, and delay as
    reported by AeroDataBox (aerodatabox.com), a third-party aggregator
    (not the airport operator). Supports scheduled future dates, not just
    the current day. Only fields present in the response are returned.
    direction, if given, is 'arrival' or 'departure' at ZRH. Does not
    cover fares, visas, or airline-specific rules.
    """
    return _find_flight_by_number(
        flight_number, flight_date, direction, client=get_aviation_client(), settings=settings
    )


@mcp.tool()
def search_airport_flights(
    direction: str,
    flight_date: str,
    airport_iata: str | None = None,
    airport_icao: str | None = None,
    airline_iata: str | None = None,
    limit: int = 10,
) -> FlightSearchResult:
    """Search ZRH arrivals or departures for a date.

    direction is 'arrival' or 'departure'. Filter by the exact IATA/ICAO
    code of the other airport (a city or country name is not accepted;
    the tool will ask for the precise airport code) and/or an airline
    IATA code. Data via AeroDataBox (aerodatabox.com).
    """
    return _search_airport_flights(
        direction,
        flight_date,
        airport_iata,
        airport_icao,
        airline_iata,
        limit,
        client=get_aviation_client(),
        settings=settings,
    )


@mcp.tool()
def get_airport_guidance(topic: str) -> AirportGuidanceResult:
    """Cited Zurich Airport passenger guidance.

    Topics: arrival_process, transfers, baggage, airport_rail_access,
    flight_status_verification. Every answer cites an official Zurich
    Airport (flughafen-zuerich.ch) page. Does not cover visa/immigration
    rules or airline-specific policies.
    """
    return _get_airport_guidance(topic)


@mcp.tool()
def connect_flight_to_train(
    destination_station: str,
    transfer_buffer_minutes: int,
    flight_number: str | None = None,
    flight_date: str | None = None,
    confirmed_arrival_time: str | None = None,
    rail_results: int = 3,
) -> FlightToTrainResult:
    """Connect a ZRH arrival to onward Swiss train travel.

    Provide either flight_number + flight_date (looked up via
    aerodatabox.com) or a confirmed_arrival_time. transfer_buffer_minutes
    (minimum 15) is added to the arrival time before searching trains via
    OJP 2.0 from Zürich Flughafen. Never assumes a train is reachable
    without this explicit buffer.
    """
    return _connect_flight_to_train(
        flight_number,
        flight_date,
        confirmed_arrival_time,
        destination_station,
        transfer_buffer_minutes,
        rail_results,
        aviation_client=get_aviation_client(),
        ojp_client=get_client(),
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
