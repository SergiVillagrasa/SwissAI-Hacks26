from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Flight, FlightEndpoint, FlightSearchResult
from swiss_grounding_mcp.evidence.aviation_provenance import build_aviation_provenance
from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxSourceError
from swiss_grounding_mcp.sources.aerodatabox.parser import parse_airport_flights

_ZRH_IATA = "ZRH"
_ZRH_ICAO = "LSZH"
_ZRH_TZ = ZoneInfo("Europe/Zurich")
_DIRECTION_PARAM = {"arrival": "Arrival", "departure": "Departure"}
_ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _day_windows(flight_date: str) -> list[tuple[str, str]] | None:
    # AeroDataBox's FIDS endpoint caps each call's range at 12 hours, so a
    # full day requires two calls. flight_date is caller-supplied (and may
    # ultimately originate from an LLM-extracted date); an unparsable value
    # must not crash the request, so return None instead of letting
    # date.fromisoformat raise ValueError.
    try:
        day = date.fromisoformat(flight_date)
    except ValueError:
        return None
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


def _relevant_endpoint(flight: Flight, direction: str) -> FlightEndpoint:
    return flight.departure if direction == "departure" else flight.arrival


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, _ISO_UTC_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _sort_key(flight: Flight, direction: str) -> datetime:
    endpoint = _relevant_endpoint(flight, direction)
    # Sort by the best available estimate of when this endpoint happens;
    # flights with no parseable time sort last rather than erroring.
    return (
        _parse_utc(endpoint.estimated)
        or _parse_utc(endpoint.scheduled)
        or datetime.max.replace(tzinfo=timezone.utc)
    )


def _has_already_happened(flight: Flight, direction: str, now_utc: datetime) -> bool:
    endpoint = _relevant_endpoint(flight, direction)
    if _parse_utc(endpoint.actual) is not None:
        # A recorded runway time means this endpoint has already occurred.
        return True
    reference = _parse_utc(endpoint.estimated) or _parse_utc(endpoint.scheduled)
    return reference is not None and reference < now_utc


def _is_today_in_zurich(flight_date: str, now_utc: datetime) -> bool:
    return date.fromisoformat(flight_date) == now_utc.astimezone(_ZRH_TZ).date()


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
    now: datetime | None = None,
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
    # airport_iata/airport_icao/airline_iata are all optional filters. If a
    # counterpart airport is named, it must be an exact IATA/ICAO code (a
    # city or country name alone is not enough to search flights) — that
    # case is validated below. Leaving all three unset lists every ZRH
    # flight for the given direction/date, most relevant first.
    if airport_iata is not None and not airport_iata.strip():
        airport_iata = None
    if airport_icao is not None and not airport_icao.strip():
        airport_icao = None
    if airline_iata is not None and not airline_iata.strip():
        airline_iata = None

    # airport_iata/airport_icao filter the *other* end of the flight (the
    # origin for arrivals, the destination for departures). ZRH is always
    # one side of every result here, so passing ZRH itself as that filter
    # can never match anything — it would silently look like "no flights",
    # not an invalid request. Catch it explicitly instead of returning a
    # misleading empty result.
    if (airport_iata and airport_iata.strip().upper() == _ZRH_IATA) or (
        airport_icao and airport_icao.strip().upper() == _ZRH_ICAO
    ):
        return FlightSearchResult(
            status="needs_context",
            message=(
                "airport_iata/airport_icao should be the *other* airport on "
                "the route, not Zurich (ZRH) itself — every result here "
                "already departs from or arrives at ZRH, so filtering on "
                "ZRH matches nothing. Provide the other airport's IATA/ICAO "
                "code, or an airline code, instead."
            ),
        )

    windows = _day_windows(flight_date)
    if windows is None:
        return FlightSearchResult(
            status="needs_context",
            message=f"'{flight_date}' is not a valid date. Please provide flight_date in YYYY-MM-DD format.",
        )

    clamped_limit = max(1, min(100, limit))
    adb_direction = _DIRECTION_PARAM[direction]

    all_flights = []
    try:
        for from_local, to_local in windows:
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
    matching.sort(key=lambda flight: _sort_key(flight, direction))

    # "Now"/"today" queries (the common case for this tool) should surface
    # the next upcoming flights, not the ones from earlier today. Only
    # drop already-happened flights when flight_date is ZRH's current
    # local calendar day — a fully past or future date is returned as-is.
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    filtered_by_time = False
    if _is_today_in_zurich(flight_date, now_utc):
        before_time_filter = len(matching)
        matching = [
            flight for flight in matching if not _has_already_happened(flight, direction, now_utc)
        ]
        filtered_by_time = before_time_filter > 0 and not matching

    if not matching:
        if filtered_by_time:
            verb = "departed" if direction == "departure" else "arrived"
            message = f"All matching {direction} flights on {flight_date} have already {verb}."
        elif airport_iata or airport_icao or airline_iata:
            message = f"No {direction} flights found matching the given filters on {flight_date}."
        else:
            message = f"No {direction} flights found for ZRH on {flight_date}."
        return FlightSearchResult(status="insufficient_evidence", message=message)

    return FlightSearchResult(
        status="answered",
        flights=matching[:clamped_limit],
        provenance=build_aviation_provenance(settings, applicable_date=flight_date),
    )
