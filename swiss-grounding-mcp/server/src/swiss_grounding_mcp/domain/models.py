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
    booking_url: str | None = None


class ConnectionSearchResult(BaseModel):
    status: Status
    message: str | None = None
    connections: list[Connection] = Field(default_factory=list)
    candidates: list[StopCandidate] = Field(default_factory=list)
    provenance: Provenance | None = None


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
