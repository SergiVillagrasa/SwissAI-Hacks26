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


def _google_flights_url(
    origin_iata: str | None, destination_iata: str | None, flight_date: str | None
) -> str:
    if not (origin_iata and destination_iata):
        return _GOOGLE_FLIGHTS_BASE
    query = f"Flights from {origin_iata} to {destination_iata}"
    if flight_date:
        query += f" on {flight_date}"
    return f"{_GOOGLE_FLIGHTS_BASE}?q={quote_plus(query)}"


def build_flight_booking_url(
    airline_iata: str | None,
    airline_icao: str | None,
    origin_iata: str | None,
    destination_iata: str | None,
    flight_date: str | None,
) -> str:
    if origin_iata and destination_iata:
        return _google_flights_url(origin_iata, destination_iata, flight_date)

    portal = _AIRLINE_PORTALS.get(_normalize_airline_code(airline_iata, airline_icao))
    if portal:
        return portal

    return _google_flights_url(origin_iata, destination_iata, flight_date)
