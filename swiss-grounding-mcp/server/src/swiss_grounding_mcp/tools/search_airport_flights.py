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
    # Note: the `flight_date` query parameter is a restricted function on
    # Aviationstack's free tier (confirmed live: HTTP 403
    # function_access_restricted). To keep this tool working on any plan
    # tier, we never send flight_date to the API; instead we fetch a wider
    # page of matching flights (across the provider's rolling window) and
    # filter by the requested date ourselves before truncating to `limit`.
    fetch_limit = max(clamped_limit, 100)
    params: dict[str, str | int] = {"limit": fetch_limit}
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

    matching_raw = [
        item for item in body.get("data", []) if item.get("flight_date") == flight_date
    ]
    if not matching_raw:
        return FlightSearchResult(
            status="insufficient_evidence",
            message=(
                f"No {direction} flights found matching the given filters on "
                f"{flight_date}. This may also mean the requested date falls "
                "outside the aviation data provider's currently available window."
            ),
        )

    flights = parse_flights({"data": matching_raw})[:clamped_limit]

    return FlightSearchResult(
        status="answered",
        flights=flights,
        provenance=build_aviation_provenance(settings, applicable_date=flight_date),
    )
