from __future__ import annotations

from urllib.parse import quote_plus

# Lufthansa Group airlines share the same booking engine; the
# /us/en/Book/{origin}-{destination}/from-{date} path is the canonical
# swiss.com booking deep link pattern.
_LH_GROUP_BOOKING_BASES = {
    "LX": "https://www.swiss.com",
    "LH": "https://www.lufthansa.com",
    "OS": "https://www.austrian.com",
    "SN": "https://www.brusselsairlines.com",
}

_AIRLINE_PORTALS = {
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
    code = _normalize_airline_code(airline_iata, airline_icao)

    lh_group_base = _LH_GROUP_BOOKING_BASES.get(code)
    if lh_group_base:
        if origin_iata and destination_iata and flight_date:
            return (
                f"{lh_group_base}/us/en/Book/"
                f"{origin_iata}-{destination_iata}/from-{flight_date}"
            )
        return lh_group_base

    portal = _AIRLINE_PORTALS.get(code)
    if portal:
        return portal

    return _google_flights_url(origin_iata, destination_iata, flight_date)
