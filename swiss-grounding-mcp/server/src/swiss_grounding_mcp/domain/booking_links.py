from __future__ import annotations

from urllib.parse import quote_plus

# Airline portals block static deep links without a booking session
# (swiss.com /us/en/Book/{o}-{d}/from-{date} returns 404), so flights
# with a known route deep-link into Google Flights with origin,
# destination and date preloaded instead. Airline portals are kept as
# the entry point when the route is not available.
_AIRLINE_PORTALS = {
    "LX": "https://www.swiss.com/ch/en/book-flights",
    "LH": "https://www.lufthansa.com",
    "OS": "https://www.austrian.com",
    "SN": "https://www.brusselsairlines.com",
    "BA": "https://www.britishairways.com",
    "U2": "https://www.easyjet.com",
    "AF": "https://www.airfrance.com",
    "KL": "https://www.klm.com",
    "EK": "https://www.emirates.com",
    "UA": "https://www.united.com",
}

_ICAO_TO_IATA = {
    "SWR": "LX",
    "DLH": "LH",
    "AUA": "OS",
    "BEL": "SN",
    "BAW": "BA",
    "EZY": "U2",
    "AFR": "AF",
    "KLM": "KL",
    "UAE": "EK",
    "UAL": "UA",
}

_GOOGLE_FLIGHTS_BASE = "https://www.google.com/travel/flights"


def _normalize_airline_code(airline_iata: str | None, airline_icao: str | None) -> str:
    iata = (airline_iata or "").strip().upper()
    if iata:
        return iata
    icao = (airline_icao or "").strip().upper()
    return _ICAO_TO_IATA.get(icao, icao)


_ZRH_IATA = "ZRH"


def _google_flights_url(
    origin_iata: str | None, destination_iata: str | None, flight_date: str | None
) -> str:
    if not (origin_iata and destination_iata):
        return _GOOGLE_FLIGHTS_BASE
    query = f"Flights from {origin_iata} to {destination_iata}"
    if flight_date:
        query += f" on {flight_date}"
    return f"{_GOOGLE_FLIGHTS_BASE}?q={quote_plus(query)}"


def _portal_fallback(airline_iata: str | None, airline_icao: str | None) -> str:
    portal = _AIRLINE_PORTALS.get(_normalize_airline_code(airline_iata, airline_icao))
    return portal if portal else _GOOGLE_FLIGHTS_BASE


def build_flight_booking_url(
    airline_iata: str | None,
    airline_icao: str | None,
    origin_iata: str | None,
    destination_iata: str | None,
    flight_date: str | None,
    *,
    origin_icao: str | None = None,
    destination_icao: str | None = None,
) -> str:
    # The flight tools are Zurich-scoped: a missing endpoint code means
    # the flight's other side is Zurich airport. ICAO codes work as
    # fallback identifiers for Google Flights.
    origin = origin_iata or origin_icao or _ZRH_IATA
    destination = destination_iata or destination_icao or _ZRH_IATA
    if origin != destination:
        return _google_flights_url(origin, destination, flight_date)
    return _portal_fallback(airline_iata, airline_icao)
