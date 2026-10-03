from __future__ import annotations

import argparse
import json
from math import ceil

import uvicorn
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

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
from swiss_grounding_mcp.http_security import (
    SlidingWindowRateLimiter,
    bearer_token_matches,
    client_ip,
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
from swiss_grounding_mcp.tools.find_flight_by_number import (
    find_flight_by_number as _find_flight_by_number,
)
from swiss_grounding_mcp.tools.flight_fares import get_flight_fares as _get_flight_fares
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


class _HttpGuard:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.rate_limiter = SlidingWindowRateLimiter(
            settings.mcp_rate_limit_per_minute, 60
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if self.settings.mcp_auth_token and not bearer_token_matches(
            headers.get("authorization"), self.settings.mcp_auth_token
        ):
            await self._respond(
                send,
                401,
                {"error": "unauthorized"},
                [(b"www-authenticate", b"Bearer")],
            )
            return

        peer = scope.get("client")
        retry_after = self.rate_limiter.check(
            client_ip(
                headers,
                peer[0] if peer else None,
                self.settings.mcp_client_ip_header,
            )
        )
        if retry_after is not None:
            await self._respond(
                send,
                429,
                {"error": "rate_limited"},
                [(b"retry-after", str(ceil(retry_after)).encode())],
            )
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _respond(
        send: Send,
        status: int,
        payload: dict[str, str],
        extra_headers: list[tuple[bytes, bytes]],
    ) -> None:
        body = json.dumps(payload).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    *extra_headers,
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def ensure_http_exposure_is_safe(host: str, settings: Settings) -> None:
    if (
        host.strip().lower() not in {"127.0.0.1", "localhost", "::1"}
        and not settings.mcp_auth_token
        and not settings.mcp_allow_unauthenticated
    ):
        raise SystemExit(
            "Public HTTP binds require MCP_AUTH_TOKEN or explicit "
            "MCP_ALLOW_UNAUTHENTICATED=true."
        )


def build_http_app(settings: Settings, host: str) -> ASGIApp:
    transport_security = (
        TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(settings.mcp_allowed_hosts),
            allowed_origins=list(settings.mcp_allowed_origins),
        )
        if settings.mcp_allowed_hosts
        else None
    )
    app = mcp.streamable_http_app(
        host=host, transport_security=transport_security
    )
    return _HttpGuard(app, settings)


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
    sort_by: str | None = None,
) -> ConnectionSearchResult:
    """Find Swiss passenger-train connections between two stations.

    Scope: the current Swiss public-transport timetable only, via OJP 2.0
    (opentransportdata.swiss). Covers origin-to-destination connection
    search with an optional departure or arrival time. Does not cover
    fares, single-stop departure boards, disruption feeds, or non-Swiss
    travel. If the origin or destination is outside Switzerland, is not a
    recognizable station, or the question is unrelated to travel, this
    tool will say so rather than guess.

    departure_time / arrival_time: ISO 8601, e.g. "2026-09-25T18:00:00Z".
    Leave unset for "now" — this tool fills in the current real date and
    time itself, so do not guess or compute "today"/"tomorrow" yourself
    from prior knowledge. If the caller gives a relative day ("tomorrow",
    "next Monday"), resolve it against the current date rather than
    assuming one. A requested time that misses the timetable by a couple
    of minutes still returns the nearest connections rather than
    "not found". All returned times are UTC (trailing "Z"), not local
    Swiss time. `sort_by` accepts "departure" to order the returned
    connections by soonest departure (shortest wait); the applied
    criterion is echoed back in the `sorted_by` field.
    """
    return find_train_connections(
        origin,
        destination,
        departure_time,
        arrival_time,
        results,
        sort_by,
        client=get_client(),
        settings=settings,
    )

@mcp.tool()
def find_disruptions(
    stop: str,
) -> DisruptionSearchResult:
    """Find current public-transport disruptions affecting a station.

    Uses current real-time OJP 2.0 stop-event information. Covers
    cancellations, delays, and boarding/alighting restrictions affecting
    services at the requested station. Unlike find_connections and
    get_station_board, this is not restricted to Swiss stations: OJP 2.0
    indexes stops across the wider network (e.g. nearby stations in
    France, Germany, Italy, or Austria), so call this tool for a
    disruption question about any such stop rather than refusing it as
    out of scope.
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
    'arrivals'; `when` is an optional ISO 8601 timestamp — leave it unset
    for "now" rather than computing today's date yourself, since this
    tool fills in the current real date and time automatically; `results`
    is capped at 10. Stations outside Switzerland are refused as out of
    scope rather than guessed. Returned times are UTC (trailing "Z"), not
    local Swiss time.
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
    sort_by: str | None = None,
) -> FareSearchResult:
    """Check public-transport fares between two Swiss stations.

    Scope: Swiss domestic public-transport fares only, via the OJP Fare
    Beta endpoint (opentransportdata.swiss). `travel_class` defaults to
    second class; `discount_card` may be set to a supported card such as
    "Halbtax". If live fare data is unavailable, the response includes a
    pre-populated SBB booking deep link for official pricing. International
    routes and ambiguous station names are refused rather than guessed.
    `sort_by` accepts "price" to order fares from cheapest to most
    expensive; the applied criterion is echoed back in `sorted_by`.
    """
    return _check_public_transport_fares(
        origin,
        destination,
        departure_time=departure_time,
        travel_class=travel_class,
        discount_card=discount_card,
        sort_by=sort_by,
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
    St. Gallen/Altenrhein, and Sion. `outbound_date` (YYYY-MM-DD) defaults
    to tomorrow when left unset — leave it unset for relative dates like
    "tomorrow" instead of computing the date yourself, since this tool
    resolves it against the current real date. The currency defaults to
    CHF. Foreign routes are refused rather than queried.
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
    cover fares, visas, or airline-specific rules. `flight_date` has no
    default — resolve relative dates like "today" or "tomorrow" against
    the current real date rather than guessing. All returned times are
    UTC, not the airport's local zone.
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

    direction is 'arrival' or 'departure'. airport_iata, airport_icao, and
    airline_iata are all optional — leave them all unset for generic
    queries like "which flights depart from Zurich today", which returns
    every matching ZRH flight for that direction/date (subject to limit).
    For "which flights depart/arrive now" style questions, pass today's
    date: results are sorted chronologically and flights that have
    already departed/arrived are dropped, so you get the next upcoming
    flights rather than everything since midnight. This only applies
    when flight_date is today (ZRH local calendar day); other dates are
    returned in full. If given, airport_iata/airport_icao must be the
    *other* airport on the route (the origin for arrivals, the
    destination for departures) — never ZRH/LSZH itself, since every
    result already touches ZRH and that filter would match nothing. A
    city or country name is not accepted either; the tool will ask for
    the precise airport code. Data via AeroDataBox (aerodatabox.com).
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
        ensure_http_exposure_is_safe(args.host, settings)
        uvicorn.run(build_http_app(settings, args.host), host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
