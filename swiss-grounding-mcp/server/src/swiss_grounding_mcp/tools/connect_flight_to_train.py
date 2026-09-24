from __future__ import annotations

from datetime import datetime, timedelta

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FlightToTrainResult
from swiss_grounding_mcp.evidence.provenance import build_provenance
from swiss_grounding_mcp.tools.find_connections import find_train_connections
from swiss_grounding_mcp.tools.find_flight_by_number import find_flight_by_number

_ZRH_STATION_NAME = "Zürich Flughafen"
_MIN_BUFFER_MINUTES = 15


def _add_minutes(iso_timestamp: str, minutes: int) -> str:
    dt = datetime.fromisoformat(iso_timestamp)
    return (dt + timedelta(minutes=minutes)).isoformat()


def connect_flight_to_train(
    flight_number: str | None,
    flight_date: str | None,
    confirmed_arrival_time: str | None,
    destination_station: str,
    transfer_buffer_minutes: int,
    rail_results: int,
    *,
    aviation_client,
    ojp_client,
    settings: Settings,
) -> FlightToTrainResult:
    if not destination_station or not destination_station.strip():
        return FlightToTrainResult(
            status="needs_context", message="Please provide a destination station."
        )
    if transfer_buffer_minutes < _MIN_BUFFER_MINUTES:
        return FlightToTrainResult(
            status="needs_context",
            message=(
                f"Please provide a transfer_buffer_minutes of at least "
                f"{_MIN_BUFFER_MINUTES} minutes."
            ),
        )
    if not flight_number and not confirmed_arrival_time:
        return FlightToTrainResult(
            status="needs_context",
            message="Please provide either a flight_number and flight_date, or a confirmed_arrival_time.",
        )

    flight = None
    flight_provenance = None

    if flight_number:
        if not flight_date:
            return FlightToTrainResult(
                status="needs_context",
                message="Please provide flight_date alongside flight_number.",
            )
        lookup = find_flight_by_number(
            flight_number, flight_date, "arrival", client=aviation_client, settings=settings
        )
        if lookup.status == "source_unavailable":
            return FlightToTrainResult(
                status="needs_context",
                message=(
                    f"Flight lookup is unavailable ({lookup.message}). Please provide "
                    "confirmed_arrival_time instead."
                ),
            )
        if lookup.status != "answered":
            return FlightToTrainResult(status=lookup.status, message=lookup.message)

        flight = lookup.flight
        flight_provenance = lookup.provenance
        arrival_time = flight.arrival.actual or flight.arrival.estimated or flight.arrival.scheduled
        if arrival_time is None:
            return FlightToTrainResult(
                status="insufficient_evidence",
                message="The flight was found but no arrival time was reported by the data source.",
            )
    else:
        arrival_time = confirmed_arrival_time

    train_departure_time = _add_minutes(arrival_time, transfer_buffer_minutes)

    train_result = find_train_connections(
        _ZRH_STATION_NAME,
        destination_station,
        train_departure_time,
        None,
        rail_results,
        client=ojp_client,
        settings=settings,
    )

    if train_result.status != "ok":
        return FlightToTrainResult(
            status="insufficient_evidence" if train_result.status == "not_found" else "source_unavailable",
            message=train_result.message,
            flight=flight,
            flight_provenance=flight_provenance,
        )

    return FlightToTrainResult(
        status="answered",
        message=(
            f"Considering onward trains departing no earlier than "
            f"{train_departure_time} ({transfer_buffer_minutes}-minute transfer buffer)."
        ),
        flight=flight,
        train_connections=train_result.connections,
        flight_provenance=flight_provenance,
        rail_provenance=train_result.provenance or build_provenance(settings),
    )
