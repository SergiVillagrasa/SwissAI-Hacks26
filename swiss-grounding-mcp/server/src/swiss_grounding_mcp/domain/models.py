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


class FareProduct(BaseModel):
    product: str
    price_chf: float
    class_of_travel: int = Field(default=2, ge=1, le=2)
    discount: str = "none"


class FareResult(BaseModel):
    status: Status
    message: str | None = None
    origin: str | None = None
    destination: str | None = None
    currency: str = "CHF"
    products: list[FareProduct] = Field(default_factory=list)
    candidates: list[StopCandidate] = Field(default_factory=list)
    provenance: Provenance | None = None
