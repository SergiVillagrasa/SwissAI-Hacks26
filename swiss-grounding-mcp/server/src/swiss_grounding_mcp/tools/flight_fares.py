from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import unicodedata

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import (
    FlightFare,
    FlightFareSearchResult,
    Provenance,
)
from swiss_grounding_mcp.sources.serpapi.flight_client import SerpApiSourceError


_AIRPORT_ALIASES = {
    "zrh": "ZRH",
    "zurich": "ZRH",
    "zuerich": "ZRH",
    "gva": "GVA",
    "geneva": "GVA",
    "geneve": "GVA",
    "genf": "GVA",
    "bsl": "BSL",
    "eap": "BSL",
    "mlh": "BSL",
    "basel": "BSL",
    "mulhouse": "BSL",
    "basel mulhouse": "BSL",
    "lug": "LUG",
    "lugano": "LUG",
    "ach": "ACH",
    "st gallen": "ACH",
    "st gallen altenrhein": "ACH",
    "altenrhein": "ACH",
    "sir": "SIR",
    "sion": "SIR",
    "sitten": "SIR",
}
_FOREIGN_LOCATIONS = {
    "paris",
    "cdg",
    "ory",
    "madrid",
    "mad",
    "barcelona",
    "bcn",
    "london",
    "lhr",
    "berlin",
    "ber",
    "milan",
    "mxp",
    "rome",
    "fco",
    "vienna",
    "vie",
}
_SUPPORTED = "ZRH/Zurich, GVA/Geneva, BSL/EAP/MLH/Basel, LUG/Lugano, ACH/Altenrhein, SIR/Sion"
_OUT_OF_SCOPE_MESSAGE = (
    "This tool only covers domestic flight connections and fares within Switzerland."
)


def _normalize_location(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_value = "".join(character for character in normalized if not unicodedata.combining(character))
    return " ".join(ascii_value.replace("-", " ").replace(".", " ").split())


def _resolve_airport(value: str) -> tuple[str | None, str]:
    normalized = _normalize_location(value)
    if not normalized:
        return None, "missing"
    airport = _AIRPORT_ALIASES.get(normalized)
    if airport:
        return airport, "swiss"
    if normalized in _FOREIGN_LOCATIONS or (len(normalized) == 3 and normalized.isalpha()):
        return None, "foreign"
    return None, "unknown"


def _parse_itinerary(item: object, currency: str) -> FlightFare | None:
    if not isinstance(item, dict):
        return None
    legs = item.get("flights")
    if not isinstance(legs, list) or not legs:
        return None
    valid_legs = [leg for leg in legs if isinstance(leg, dict)]
    if not valid_legs:
        return None
    departure = valid_legs[0].get("departure_airport")
    arrival = valid_legs[-1].get("arrival_airport")
    price = item.get("price")
    if not isinstance(departure, dict) or not isinstance(arrival, dict):
        return None
    if not departure.get("time") or not arrival.get("time") or not isinstance(price, (int, float)):
        return None

    airlines = list(dict.fromkeys(str(leg["airline"]) for leg in valid_legs if leg.get("airline")))
    flight_numbers = list(
        dict.fromkeys(str(leg["flight_number"]) for leg in valid_legs if leg.get("flight_number"))
    )
    if not airlines or not flight_numbers:
        return None
    emissions = item.get("carbon_emissions")
    carbon = emissions.get("this_flight") if isinstance(emissions, dict) else None
    duration = item.get("total_duration")
    return FlightFare(
        airline=" / ".join(airlines),
        flight_number=" / ".join(flight_numbers),
        departure_time=str(departure["time"]),
        arrival_time=str(arrival["time"]),
        price=float(price),
        currency=currency,
        duration_minutes=duration if isinstance(duration, int) else None,
        carbon_emissions_grams=carbon if isinstance(carbon, int) else None,
    )


def get_flight_fares(
    origin_city: str,
    destination_city: str,
    outbound_date: str | None = None,
    currency: str = "CHF",
    *,
    client,
    settings: Settings,
) -> FlightFareSearchResult:
    origin, origin_kind = _resolve_airport(origin_city or "")
    destination, destination_kind = _resolve_airport(destination_city or "")
    if "foreign" in (origin_kind, destination_kind):
        return FlightFareSearchResult(status="out_of_scope", message=_OUT_OF_SCOPE_MESSAGE)
    if not origin or not destination:
        return FlightFareSearchResult(
            status="needs_clarification",
            message=f"Please provide recognizable Swiss origin and destination airports. Supported airports: {_SUPPORTED}.",
        )
    if origin == destination:
        return FlightFareSearchResult(
            status="needs_clarification",
            message="Origin and destination must be different Swiss airports.",
        )

    requested_date = outbound_date or (date.today() + timedelta(days=1)).isoformat()
    try:
        date.fromisoformat(requested_date)
    except ValueError:
        return FlightFareSearchResult(
            status="needs_clarification",
            message="Please provide outbound_date in YYYY-MM-DD format.",
        )
    normalized_currency = currency.strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        return FlightFareSearchResult(
            status="needs_clarification",
            message="Please provide a three-letter currency code such as CHF.",
        )

    try:
        body = client.search_flights(origin, destination, requested_date, normalized_currency)
    except SerpApiSourceError as exc:
        return FlightFareSearchResult(status="source_error", message=str(exc))

    items = []
    for key in ("best_flights", "other_flights"):
        values = body.get(key, []) if isinstance(body, dict) else []
        if isinstance(values, list):
            items.extend(values)
    flights = [fare for item in items if (fare := _parse_itinerary(item, normalized_currency))]
    if not flights:
        return FlightFareSearchResult(
            status="not_found",
            message=(
                f"No commercial domestic flights were found from {origin} to {destination} "
                f"on {requested_date}. Domestic commercial services in Switzerland are limited."
            ),
        )

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return FlightFareSearchResult(
        status="ok",
        flights=flights[:5],
        provenance=Provenance(
            source="SerpApi (Google Flights)",
            source_url="https://serpapi.com",
            retrieved_at=retrieved_at,
        ),
    )
