from __future__ import annotations

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FlightSearchResult
from swiss_grounding_mcp.evidence.aviation_provenance import build_aviation_provenance
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackSourceError
from swiss_grounding_mcp.sources.aviationstack.parser import parse_flights

_ZRH_IATA = "ZRH"


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
    params: dict[str, str | int] = {"flight_date": flight_date, "limit": clamped_limit}
    if direction == "departure":
        params["dep_iata"] = _ZRH_IATA
        if airport_iata:
            params["arr_iata"] = airport_iata
        if airport_icao:
            params["arr_icao"] = airport_icao
    else:
        params["arr_iata"] = _ZRH_IATA
        if airport_iata:
            params["dep_iata"] = airport_iata
        if airport_icao:
            params["dep_icao"] = airport_icao
    if airline_iata:
        params["airline_iata"] = airline_iata

    try:
        body = client.get_flights(params)
    except AviationstackSourceError as exc:
        return FlightSearchResult(status="source_unavailable", message=str(exc))

    flights = parse_flights(body)
    if not flights:
        return FlightSearchResult(
            status="insufficient_evidence",
            message=f"No {direction} flights found matching the given filters on {flight_date}.",
        )

    return FlightSearchResult(
        status="answered",
        flights=flights,
        provenance=build_aviation_provenance(settings, applicable_date=flight_date),
    )
