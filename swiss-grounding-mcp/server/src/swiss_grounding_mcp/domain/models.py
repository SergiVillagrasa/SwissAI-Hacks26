from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "needs_clarification", "not_found", "out_of_scope", "source_error"]


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
