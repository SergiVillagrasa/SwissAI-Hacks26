from __future__ import annotations

from datetime import date, timedelta

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FlightSearchResult
from swiss_grounding_mcp.evidence.aviation_provenance import build_aviation_provenance
from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxSourceError
from swiss_grounding_mcp.sources.aerodatabox.parser import parse_airport_flights

_ZRH_IATA = "ZRH"
_DIRECTION_PARAM = {"arrival": "Arrival", "departure": "Departure"}


def _day_windows(flight_date: str) -> list[tuple[str, str]]:
    # AeroDataBox's FIDS endpoint caps each call's range at 12 hours, so a
    # full day requires two calls.
    day = date.fromisoformat(flight_date)
    next_day = day + timedelta(days=1)
    midday = f"{flight_date}T12:00"
    return [
        (f"{flight_date}T00:00", midday),
        (midday, f"{next_day.isoformat()}T00:00"),
    ]


def _counterpart_matches(flight, direction: str, airport_iata: str | None, airport_icao: str | None) -> bool:
    if not airport_iata and not airport_icao:
        return True
    counterpart = flight.arrival if direction == "departure" else flight.departure
    if airport_iata and counterpart.airport.iata == airport_iata:
        return True
    if airport_icao and counterpart.airport.icao == airport_icao:
        return True
    return False


def search_airport_flights(
    direction: str,
    flight_date: str,
    airport_iata: str | None,
    airport_icao: str | None,
    airline_iata: str | None,
    limit: int,
    *,
    client,
    settings: Settings,
) -> FlightSearchResult:
    if direction not in ("arrival", "departure"):
        return FlightSearchResult(
            status="needs_context",
            message="Please specify direction as 'arrival' or 'departure'.",
        )
    if not flight_date or not flight_date.strip():
        return FlightSearchResult(
            status="needs_context",
            message="Please provide a flight date in YYYY-MM-DD format.",
        )
    if not airport_iata and not airport_icao and not airline_iata:
        return FlightSearchResult(
            status="needs_context",
            message=(
                "Please provide the exact origin/destination airport IATA or "
                "ICAO code (a city or country name alone is not enough to "
                "search flights), or an airline code."
            ),
        )

    clamped_limit = max(1, min(100, limit))
    adb_direction = _DIRECTION_PARAM[direction]

    all_flights = []
    try:
        for from_local, to_local in _day_windows(flight_date):
            body = client.get_airport_flights(
                "iata", _ZRH_IATA, from_local, to_local, direction=adb_direction
            )
            all_flights.extend(parse_airport_flights(body))
    except AerodataboxSourceError as exc:
        return FlightSearchResult(status="source_unavailable", message=str(exc))

    matching = [
        flight
        for flight in all_flights
        if _counterpart_matches(flight, direction, airport_iata, airport_icao)
        and (not airline_iata or flight.airline.iata == airline_iata)
    ]

    if not matching:
        return FlightSearchResult(
            status="insufficient_evidence",
            message=(
                f"No {direction} flights found matching the given filters on "
                f"{flight_date}."
            ),
        )

    return FlightSearchResult(
        status="answered",
        flights=matching[:clamped_limit],
        provenance=build_aviation_provenance(settings, applicable_date=flight_date),
    )
