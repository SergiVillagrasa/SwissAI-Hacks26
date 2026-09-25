from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "needs_clarification", "not_found", "out_of_scope", "source_error"]
FareStatus = Literal[
    "success",
    "fallback_link",
    "out_of_scope",
    "needs_clarification",
    "source_error",
]


class Leg(BaseModel):
    mode: str
    line: str | None = None
    from_name: str
    to_name: str
    departure: str | None = None
    arrival: str | None = None


class Connection(BaseModel):
    departure: str
    arrival: str
    duration_minutes: int
    changes: int
    legs: list[Leg] = Field(default_factory=list)


class StopCandidate(BaseModel):
    name: str
    stop_ref: str
    probability: float | None = None


class Provenance(BaseModel):
    source: str
    source_url: str
    retrieved_at: str
    # OJP 2.0 always returns Zulu/UTC timestamps (trailing "Z"), and this
    # server never converts them to a local zone, so every time field
    # exposed by the train tools (departure/arrival/planned_time/etc.) is
    # UTC. Naming it explicitly here keeps it consistent with
    # AviationProvenance.timezone across all tools.
    timezone: str = "UTC"
    booking_url: str | None = None


class ConnectionSearchResult(BaseModel):
    status: Status
    message: str | None = None
    connections: list[Connection] = Field(default_factory=list)
    candidates: list[StopCandidate] = Field(default_factory=list)
    provenance: Provenance | None = None
    sorted_by: str | None = None


class StopEvent(BaseModel):
    line: str | None = None
    mode: str | None = None
    direction_name: str | None = None
    planned_time: str | None = None
    estimated_time: str | None = None
    platform: str | None = None
    delay_minutes: int | None = None


class StationBoardResult(BaseModel):
    status: Status
    message: str | None = None
    station_name: str | None = None
    event_type: str | None = None
    events: list[StopEvent] = Field(default_factory=list)
    candidates: list[StopCandidate] = Field(default_factory=list)
    provenance: Provenance | None = None


class FareProduct(BaseModel):
    product: str
    price_chf: float
    class_of_travel: str
    discount: str | None = None


class FareSearchResult(BaseModel):
    status: FareStatus
    message: str | None = None
    fares: list[FareProduct] = Field(default_factory=list)
    booking_url: str | None = None
    candidates: list[StopCandidate] = Field(default_factory=list)
    provenance: Provenance | None = None
    sorted_by: str | None = None


class Disruption(BaseModel):
    id: str
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    status: str | None = None
    affected_lines: list[str] = Field(default_factory=list)
    affected_stops: list[str] = Field(default_factory=list)


class DisruptionSearchResult(BaseModel):
    status: Status
    message: str | None = None
    disruptions: list[Disruption] = Field(default_factory=list)
    provenance: Provenance | None = None
    candidates: list[StopCandidate] = Field(default_factory=list)


AviationStatus = Literal[
    "answered", "needs_context", "insufficient_evidence", "out_of_scope", "source_unavailable"
]


class AirportInfo(BaseModel):
    iata: str | None = None
    icao: str | None = None
    name: str | None = None
    timezone: str | None = None


class FlightEndpoint(BaseModel):
    airport: AirportInfo
    scheduled: str | None = None
    estimated: str | None = None
    actual: str | None = None
    terminal: str | None = None
    gate: str | None = None
    delay_minutes: int | None = None


class AirlineInfo(BaseModel):
    name: str | None = None
    iata: str | None = None
    icao: str | None = None


class Flight(BaseModel):
    flight_number: str
    flight_date: str
    airline: AirlineInfo
    departure: FlightEndpoint
    arrival: FlightEndpoint
    flight_status: str | None = None
    booking_url: str | None = None


class AviationProvenance(BaseModel):
    source: str
    source_url: str
    retrieved_at: str
    applicable_date: str
    timezone: str


class FlightLookupResult(BaseModel):
    status: AviationStatus
    message: str | None = None
    flight: Flight | None = None
    fields_present: list[str] = Field(default_factory=list)
    fields_missing: list[str] = Field(default_factory=list)
    provenance: AviationProvenance | None = None


class FlightSearchResult(BaseModel):
    status: AviationStatus
    message: str | None = None
    flights: list[Flight] = Field(default_factory=list)
    provenance: AviationProvenance | None = None


class FlightFare(BaseModel):
    airline: str
    flight_number: str
    departure_time: str
    arrival_time: str
    price: float
    currency: str
    duration_minutes: int | None = None
    carbon_emissions_grams: int | None = None


class FlightFareSearchResult(BaseModel):
    status: Status
    message: str | None = None
    flights: list[FlightFare] = Field(default_factory=list)
    provenance: Provenance | None = None


class AirportGuidanceResult(BaseModel):
    status: AviationStatus
    topic: str
    message: str | None = None
    guidance: str | None = None
    source: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    applicable_airport: str | None = None
    limitations: str | None = None


class FlightToTrainResult(BaseModel):
    status: AviationStatus
    message: str | None = None
    flight: Flight | None = None
    train_connections: list[Connection] = Field(default_factory=list)
    flight_provenance: AviationProvenance | None = None
    rail_provenance: Provenance | None = None
