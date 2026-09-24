# ZRH Aviation Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Swiss Grounding MCP server with four aviation tools —
`find_flight_by_number`, `search_airport_flights`, `get_airport_guidance`,
`connect_flight_to_train` — backed by the Aviationstack API and official
Zurich Airport guidance pages, using the honest outcomes `answered`,
`needs_context`, `insufficient_evidence`, `out_of_scope`, `source_unavailable`.

**Architecture:** Mirrors the existing OJP module's layering.
`sources/aviationstack/` holds the HTTP client (with a short in-memory
cache) and the JSON-to-domain-model parser. `sources/zrh/guidance.py`
holds static, citable guidance records. `domain/models.py` gains aviation
pydantic models. `tools/` holds one orchestration function per tool,
following the existing `find_train_connections` pattern (pure functions
taking a client + settings, fully unit-testable with stub clients).
`server.py` registers the four new `@mcp.tool()` wrappers alongside the
existing `find_connections`, reusing `get_client()` for the OJP client in
`connect_flight_to_train`.

**Tech Stack:** Python 3.10+, `mcp` SDK v2.x, `httpx` (already a
dependency) for the Aviationstack HTTP call, `pydantic` for domain
models, `pytest` for tests, `uv` for dependency management. No new
dependencies are required.

**Spec:** `docs/superpowers/specs/2026-09-24-zrh-aviation-module-design.md`

## Global Constraints

- Implementation lives under `swiss-grounding-mcp/server/`; the existing
  `find_connections` tool and its tests are untouched (spec §4, §9).
- Aviation tools use the status set `answered | needs_context |
  insufficient_evidence | out_of_scope | source_unavailable`, distinct
  from the train tool's `ok | needs_clarification | not_found |
  out_of_scope | source_error` (spec §5).
- Only fields actually present in the Aviationstack response are
  populated; absent fields are never guessed and are listed in
  `fields_missing` (spec §5.1, §7).
- Every `answered` result carries a `provenance` (or
  `flight_provenance`/`rail_provenance`) block with source, source_url,
  retrieved_at, applicable_date, and `timezone: "Europe/Zurich"` (spec
  §5, §9).
- `AVIATIONSTACK_API_KEY` and other Aviationstack settings are read from
  env only; `.env.example` ships with empty/default values, no secrets
  committed (spec §8).
- If `AVIATIONSTACK_ENABLE` is false or the API key is empty, aviation
  flight tools return `source_unavailable` without making an HTTP call
  (spec §8).
- `connect_flight_to_train` requires `transfer_buffer_minutes >= 15`,
  computes `train_departure_time = arrival_time + buffer`, and calls the
  existing `find_train_connections` with origin `"Zürich Flughafen"`,
  keeping flight and rail provenance in separate fields (spec §5.4, §9).
- `search_airport_flights` must reject bare city/country text (no
  airport code) with `needs_context`, not guess an airport (spec §5.2,
  §9).
- No scraping of `flughafen-zuerich.ch`; guidance text is a static,
  pre-written record per topic with its official source URL (spec §3.2,
  §11).
- A short in-memory cache (default 60s) on the Aviationstack client
  avoids burning the free-tier quota during a demo (spec §7, §12).

## Review Focus

- **`connect_flight_to_train` when the flight lookup itself fails.** The
  spec says failed/unavailable flight lookup should fall back to asking
  for `confirmed_arrival_time`, not silently return `source_unavailable`
  for the whole tool when the user could still supply a time. Covered in
  Task 8.
- **`search_airport_flights` with a real airport code that has zero
  matching flights.** Must be `insufficient_evidence`, not `answered`
  with an empty list — distinguishing "no flights found" from "provider
  failed" per the top-level requirement. Covered in Task 7.
- **Aviationstack response with `data: []` vs. an HTTP/auth error.**
  These are different failure modes (`insufficient_evidence` vs.
  `source_unavailable`) and must not be conflated. Covered in Task 3
  (client raises only on transport/HTTP/auth failure, never on an empty
  `data` array) and Task 4 (parser returns an empty list, tools decide
  the status).
- **Partial field availability (e.g., `actual` present but `gate`
  missing, or vice versa).** The LLM must never see a gate/time it
  wasn't given. Covered in Task 4's `fields_present`/`fields_missing`
  tests and Task 6's flight-lookup tests.
- **`get_airport_guidance` with an unsupported topic string.** Must
  return `out_of_scope`, not throw or silently default to one topic.
  Covered in Task 5.

---

## Task 1: Extend `Settings` with Aviationstack configuration

**Files:**
- Modify: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/config/settings.py`
- Modify: `swiss-grounding-mcp/server/.env.example`
- Modify: `swiss-grounding-mcp/server/tests/unit/test_settings.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Settings` fields `aviationstack_api_key: str`,
  `aviationstack_base_url: str`, `aviationstack_timeout_seconds: float`,
  `aviationstack_enable: bool`, `aviationstack_cache_seconds: float`.
  Used by Task 3 (`AviationstackClient`).

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_settings.py`:

```python
def test_aviationstack_defaults_when_env_empty():
    settings = Settings.from_env({})

    assert settings.aviationstack_api_key == ""
    assert settings.aviationstack_base_url == "https://api.aviationstack.com/v1"
    assert settings.aviationstack_timeout_seconds == 10.0
    assert settings.aviationstack_enable is True
    assert settings.aviationstack_cache_seconds == 60.0


def test_aviationstack_env_overrides_defaults():
    env = {
        "AVIATIONSTACK_API_KEY": "test-key",
        "AVIATIONSTACK_BASE_URL": "https://example.test/v1",
        "AVIATIONSTACK_TIMEOUT_SECONDS": "5",
        "AVIATIONSTACK_ENABLE": "false",
        "AVIATIONSTACK_CACHE_SECONDS": "30",
    }

    settings = Settings.from_env(env)

    assert settings.aviationstack_api_key == "test-key"
    assert settings.aviationstack_base_url == "https://example.test/v1"
    assert settings.aviationstack_timeout_seconds == 5.0
    assert settings.aviationstack_enable is False
    assert settings.aviationstack_cache_seconds == 30.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_settings.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'aviationstack_api_key'`.

- [ ] **Step 3: Implement the settings fields**

In `src/swiss_grounding_mcp/config/settings.py`, add fields to the
`Settings` dataclass (after `mcp_http_port`):

```python
    aviationstack_api_key: str = ""
    aviationstack_base_url: str = "https://api.aviationstack.com/v1"
    aviationstack_timeout_seconds: float = 10.0
    aviationstack_enable: bool = True
    aviationstack_cache_seconds: float = 60.0
```

And in `from_env`, add corresponding entries to the returned `cls(...)`
call (after `mcp_http_port=...`):

```python
            aviationstack_api_key=source.get(
                "AVIATIONSTACK_API_KEY", defaults.aviationstack_api_key
            ),
            aviationstack_base_url=source.get(
                "AVIATIONSTACK_BASE_URL", defaults.aviationstack_base_url
            ),
            aviationstack_timeout_seconds=float(
                source.get(
                    "AVIATIONSTACK_TIMEOUT_SECONDS", defaults.aviationstack_timeout_seconds
                )
            ),
            aviationstack_enable=_parse_bool(
                source.get("AVIATIONSTACK_ENABLE", str(defaults.aviationstack_enable)),
                defaults.aviationstack_enable,
            ),
            aviationstack_cache_seconds=float(
                source.get(
                    "AVIATIONSTACK_CACHE_SECONDS", defaults.aviationstack_cache_seconds
                )
            ),
```

Update `.env.example` to append:

```
AVIATIONSTACK_API_KEY=
AVIATIONSTACK_BASE_URL=https://api.aviationstack.com/v1
AVIATIONSTACK_TIMEOUT_SECONDS=10
AVIATIONSTACK_ENABLE=true
AVIATIONSTACK_CACHE_SECONDS=60
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_settings.py -v`
Expected: PASS (all tests, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/config/settings.py \
        swiss-grounding-mcp/server/.env.example \
        swiss-grounding-mcp/server/tests/unit/test_settings.py
git commit -m "feat: add Aviationstack settings"
```

---

## Task 2: Aviation domain models

**Files:**
- Modify: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/domain/models.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_aviation_domain_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces (all pydantic `BaseModel`s in `domain/models.py`):
  - `AviationStatus = Literal["answered", "needs_context", "insufficient_evidence", "out_of_scope", "source_unavailable"]`
  - `AirportInfo(iata: str | None, icao: str | None, name: str | None, timezone: str | None)`
  - `FlightEndpoint(airport: AirportInfo, scheduled: str | None, estimated: str | None, actual: str | None, terminal: str | None, gate: str | None, delay_minutes: int | None)`
  - `AirlineInfo(name: str | None, iata: str | None, icao: str | None)`
  - `Flight(flight_number: str, flight_date: str, airline: AirlineInfo, departure: FlightEndpoint, arrival: FlightEndpoint, flight_status: str | None)`
  - `AviationProvenance(source: str, source_url: str, retrieved_at: str, applicable_date: str, timezone: str)`
  - `FlightLookupResult(status: AviationStatus, message: str | None, flight: Flight | None, fields_present: list[str], fields_missing: list[str], provenance: AviationProvenance | None)`
  - `FlightSearchResult(status: AviationStatus, message: str | None, flights: list[Flight], provenance: AviationProvenance | None)`
  - `AirportGuidanceResult(status: AviationStatus, topic: str, guidance: str | None, source: str | None, source_url: str | None, retrieved_at: str | None, applicable_airport: str | None, limitations: str | None, message: str | None)`
  - `FlightToTrainResult(status: AviationStatus, message: str | None, flight: Flight | None, train_connections: list[Connection], flight_provenance: AviationProvenance | None, rail_provenance: Provenance | None)`

  All list fields default to `[]` via `Field(default_factory=list)`, all
  optional fields default to `None`. Used by Tasks 3, 4, 5, 6, 7, 8.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_aviation_domain_models.py
from swiss_grounding_mcp.domain.models import (
    AirlineInfo,
    AirportGuidanceResult,
    AirportInfo,
    AviationProvenance,
    Flight,
    FlightEndpoint,
    FlightLookupResult,
    FlightSearchResult,
    FlightToTrainResult,
)


def _endpoint(**overrides) -> FlightEndpoint:
    defaults = dict(
        airport=AirportInfo(iata="ZRH", icao="LSZH", name="Zurich Airport", timezone="Europe/Zurich"),
        scheduled="2026-09-25T10:20:00+02:00",
        estimated=None,
        actual=None,
        terminal="1",
        gate=None,
        delay_minutes=None,
    )
    defaults.update(overrides)
    return FlightEndpoint(**defaults)


def _flight() -> Flight:
    return Flight(
        flight_number="LX14",
        flight_date="2026-09-25",
        airline=AirlineInfo(name="SWISS", iata="LX", icao="SWR"),
        departure=_endpoint(),
        arrival=_endpoint(airport=AirportInfo(iata="JFK", icao="KJFK", name="JFK", timezone="America/New_York")),
        flight_status="scheduled",
    )


def test_flight_lookup_result_answered_carries_flight_and_field_lists():
    result = FlightLookupResult(
        status="answered",
        message=None,
        flight=_flight(),
        fields_present=["departure.scheduled"],
        fields_missing=["departure.actual"],
        provenance=AviationProvenance(
            source="aviationstack.com",
            source_url="https://api.aviationstack.com/v1/flights",
            retrieved_at="2026-09-24T22:15:00Z",
            applicable_date="2026-09-25",
            timezone="Europe/Zurich",
        ),
    )

    dumped = result.model_dump()
    assert dumped["status"] == "answered"
    assert dumped["flight"]["flight_number"] == "LX14"
    assert dumped["fields_missing"] == ["departure.actual"]
    assert dumped["provenance"]["timezone"] == "Europe/Zurich"


def test_flight_search_result_defaults_to_empty_flights_and_no_provenance():
    result = FlightSearchResult(status="needs_context", message="Provide an airport code.")

    dumped = result.model_dump()
    assert dumped["flights"] == []
    assert dumped["provenance"] is None


def test_airport_guidance_result_out_of_scope_has_no_guidance_text():
    result = AirportGuidanceResult(
        status="out_of_scope",
        topic="visa_requirements",
        message="Topic not covered by this tool.",
    )

    dumped = result.model_dump()
    assert dumped["guidance"] is None
    assert dumped["source_url"] is None


def test_flight_to_train_result_keeps_separate_provenance_fields():
    result = FlightToTrainResult(
        status="answered",
        message=None,
        flight=_flight(),
        train_connections=[],
        flight_provenance=AviationProvenance(
            source="aviationstack.com",
            source_url="https://api.aviationstack.com/v1/flights",
            retrieved_at="2026-09-24T22:15:00Z",
            applicable_date="2026-09-25",
            timezone="Europe/Zurich",
        ),
        rail_provenance=None,
    )

    dumped = result.model_dump()
    assert dumped["flight_provenance"]["source"] == "aviationstack.com"
    assert dumped["rail_provenance"] is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_aviation_domain_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'AirlineInfo' ...`.

- [ ] **Step 3: Implement the models**

Append to `src/swiss_grounding_mcp/domain/models.py` (keep existing
`Status`/train models untouched, add below them):

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_aviation_domain_models.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/domain/models.py \
        swiss-grounding-mcp/server/tests/unit/test_aviation_domain_models.py
git commit -m "feat: add aviation domain models"
```

---

## Task 3: Aviationstack HTTP client with caching

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/aviationstack/__init__.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/aviationstack/client.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_aviationstack_client.py`
- Create fixtures:
  - `swiss-grounding-mcp/server/tests/fixtures/aviationstack/lx14_zrh_jfk.json`
  - `swiss-grounding-mcp/server/tests/fixtures/aviationstack/empty.json`
  - `swiss-grounding-mcp/server/tests/fixtures/aviationstack/error_quota.json`

**Interfaces:**
- Consumes: `swiss_grounding_mcp.config.settings.Settings`.
- Produces: `AviationstackSourceError(Exception)` and
  `AviationstackClient`, with method
  `get_flights(self, params: dict[str, str | int]) -> dict` returning the
  parsed JSON body (`{"pagination": ..., "data": [...]}`). Raises
  `AviationstackSourceError` on network failure, non-2xx response, or an
  Aviationstack `error` object in the JSON body. Does **not** raise for
  an empty `data` list — that is a valid "no matches" response. Caches
  responses in-memory for `settings.aviationstack_cache_seconds`, keyed
  by the sorted params. Used by Tasks 6, 7, 8.

- [ ] **Step 1: Create the fixtures**

```json
// swiss-grounding-mcp/server/tests/fixtures/aviationstack/lx14_zrh_jfk.json
{
  "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 1},
  "data": [
    {
      "flight_date": "2026-09-25",
      "flight_status": "scheduled",
      "departure": {
        "airport": "Zurich",
        "timezone": "Europe/Zurich",
        "iata": "ZRH",
        "icao": "LSZH",
        "terminal": "1",
        "gate": "A12",
        "delay": 5,
        "scheduled": "2026-09-25T10:20:00+00:00",
        "estimated": "2026-09-25T10:25:00+00:00",
        "actual": null
      },
      "arrival": {
        "airport": "John F Kennedy International",
        "timezone": "America/New_York",
        "iata": "JFK",
        "icao": "KJFK",
        "terminal": "4",
        "gate": "B22",
        "delay": null,
        "scheduled": "2026-09-25T13:10:00+00:00",
        "estimated": "2026-09-25T13:05:00+00:00",
        "actual": null
      },
      "airline": {"name": "Swiss International Air Lines", "iata": "LX", "icao": "SWR"},
      "flight": {"number": "14", "iata": "LX14", "icao": "SWR14", "codeshared": null},
      "aircraft": null,
      "live": null
    }
  ]
}
```

```json
// swiss-grounding-mcp/server/tests/fixtures/aviationstack/empty.json
{
  "pagination": {"limit": 100, "offset": 0, "count": 0, "total": 0},
  "data": []
}
```

```json
// swiss-grounding-mcp/server/tests/fixtures/aviationstack/error_quota.json
{
  "error": {
    "code": "usage_limit_reached",
    "message": "Your monthly API request volume has been reached. Please upgrade your plan."
  }
}
```

- [ ] **Step 2: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_aviationstack_client.py
import json
import time
from pathlib import Path

import httpx
import pytest

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.aviationstack.client import (
    AviationstackClient,
    AviationstackSourceError,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "aviationstack"


def _read_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _settings(**overrides) -> Settings:
    env = {
        "AVIATIONSTACK_API_KEY": "test-key",
        "AVIATIONSTACK_BASE_URL": "https://example.test/v1",
        "AVIATIONSTACK_CACHE_SECONDS": "60",
    }
    env.update(overrides)
    return Settings.from_env(env)


def _client_with_transport(handler, settings=None) -> AviationstackClient:
    transport = httpx.MockTransport(handler)
    client = AviationstackClient(settings or _settings())
    client._http = httpx.Client(transport=transport)
    return client


def test_get_flights_returns_parsed_json_and_sends_access_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=_read_json("lx14_zrh_jfk.json"))

    client = _client_with_transport(handler)

    body = client.get_flights({"flight_iata": "LX14", "flight_date": "2026-09-25"})

    assert seen["params"]["access_key"] == "test-key"
    assert seen["params"]["flight_iata"] == "LX14"
    assert len(body["data"]) == 1


def test_empty_data_array_does_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_read_json("empty.json"))

    client = _client_with_transport(handler)

    body = client.get_flights({"flight_iata": "XX0000"})

    assert body["data"] == []


def test_embedded_error_object_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_read_json("error_quota.json"))

    client = _client_with_transport(handler)

    with pytest.raises(AviationstackSourceError, match="usage_limit_reached"):
        client.get_flights({"flight_iata": "LX14"})


def test_non_2xx_response_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    client = _client_with_transport(handler)

    with pytest.raises(AviationstackSourceError):
        client.get_flights({"flight_iata": "LX14"})


def test_network_error_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client_with_transport(handler)

    with pytest.raises(AviationstackSourceError):
        client.get_flights({"flight_iata": "LX14"})


def test_disabled_client_raises_source_error_without_http_call():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP call should not happen when disabled")

    client = _client_with_transport(handler, settings=_settings(AVIATIONSTACK_ENABLE="false"))

    with pytest.raises(AviationstackSourceError, match="disabled"):
        client.get_flights({"flight_iata": "LX14"})


def test_missing_api_key_raises_source_error_without_http_call():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP call should not happen without an API key")

    client = _client_with_transport(handler, settings=_settings(AVIATIONSTACK_API_KEY=""))

    with pytest.raises(AviationstackSourceError, match="API key"):
        client.get_flights({"flight_iata": "LX14"})


def test_repeated_call_within_cache_window_reuses_response():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_read_json("lx14_zrh_jfk.json"))

    client = _client_with_transport(handler)

    client.get_flights({"flight_iata": "LX14", "flight_date": "2026-09-25"})
    client.get_flights({"flight_iata": "LX14", "flight_date": "2026-09-25"})

    assert call_count["n"] == 1


def test_call_after_cache_expiry_hits_http_again(monkeypatch):
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_read_json("lx14_zrh_jfk.json"))

    client = _client_with_transport(handler, settings=_settings(AVIATIONSTACK_CACHE_SECONDS="0"))

    client.get_flights({"flight_iata": "LX14"})
    client.get_flights({"flight_iata": "LX14"})

    assert call_count["n"] == 2
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_aviationstack_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.sources.aviationstack'`.

- [ ] **Step 4: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/aviationstack/__init__.py
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/aviationstack/client.py
from __future__ import annotations

import time

import httpx

from swiss_grounding_mcp.config.settings import Settings


class AviationstackSourceError(Exception):
    """Raised when Aviationstack cannot be reached or reports a failure."""


class AviationstackClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.Client(timeout=settings.aviationstack_timeout_seconds)
        self._cache: dict[tuple, tuple[float, dict]] = {}

    def _cache_key(self, params: dict) -> tuple:
        return tuple(sorted(params.items()))

    def get_flights(self, params: dict) -> dict:
        if not self._settings.aviationstack_enable:
            raise AviationstackSourceError(
                "Aviationstack integration is disabled (AVIATIONSTACK_ENABLE=false)."
            )
        if not self._settings.aviationstack_api_key:
            raise AviationstackSourceError(
                "No Aviationstack API key configured (AVIATIONSTACK_API_KEY is empty)."
            )

        cache_key = self._cache_key(params)
        cached = self._cache.get(cache_key)
        if cached is not None:
            cached_at, body = cached
            if time.monotonic() - cached_at < self._settings.aviationstack_cache_seconds:
                return body

        query = {"access_key": self._settings.aviationstack_api_key, **params}
        try:
            response = self._http.get(
                f"{self._settings.aviationstack_base_url}/flights", params=query
            )
        except httpx.HTTPError as exc:
            raise AviationstackSourceError(f"Aviationstack request failed: {exc}") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise AviationstackSourceError(
                f"Aviationstack returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise AviationstackSourceError(
                f"Aviationstack returned an unparsable response: {exc}"
            ) from exc

        error = body.get("error")
        if error:
            code = error.get("code", "unknown_error")
            message = error.get("message", "no message")
            raise AviationstackSourceError(f"Aviationstack reported an error ({code}): {message}")

        self._cache[cache_key] = (time.monotonic(), body)
        return body
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_aviationstack_client.py -v`
Expected: PASS (8 tests).

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/aviationstack \
        swiss-grounding-mcp/server/tests/unit/test_aviationstack_client.py \
        swiss-grounding-mcp/server/tests/fixtures/aviationstack
git commit -m "feat: add Aviationstack HTTP client with in-memory caching"
```

---

## Task 4: Aviationstack response parser

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/aviationstack/parser.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_aviationstack_parser.py`
- Create fixture: `swiss-grounding-mcp/server/tests/fixtures/aviationstack/lx14_partial_fields.json`

**Interfaces:**
- Consumes: raw JSON `dict` as returned by
  `AviationstackClient.get_flights` (i.e. `{"data": [...]}`).
- Produces: `parse_flights(body: dict) -> list[Flight]` and
  `flight_field_presence(flight_json: dict) -> tuple[list[str], list[str]]`
  returning `(fields_present, fields_missing)` using the dotted paths
  `departure.scheduled`, `departure.estimated`, `departure.actual`,
  `departure.terminal`, `departure.gate`, `arrival.scheduled`,
  `arrival.estimated`, `arrival.actual`, `arrival.terminal`,
  `arrival.gate`. Used by Tasks 6 and 7.

- [ ] **Step 1: Create the partial-fields fixture**

```json
// swiss-grounding-mcp/server/tests/fixtures/aviationstack/lx14_partial_fields.json
{
  "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 1},
  "data": [
    {
      "flight_date": "2026-09-25",
      "flight_status": "active",
      "departure": {
        "airport": "Zurich",
        "timezone": "Europe/Zurich",
        "iata": "ZRH",
        "icao": "LSZH",
        "terminal": null,
        "gate": null,
        "delay": null,
        "scheduled": "2026-09-25T10:20:00+00:00",
        "estimated": "2026-09-25T10:20:00+00:00",
        "actual": "2026-09-25T10:24:00+00:00"
      },
      "arrival": {
        "airport": "John F Kennedy International",
        "timezone": "America/New_York",
        "iata": "JFK",
        "icao": "KJFK",
        "terminal": "4",
        "gate": null,
        "delay": null,
        "scheduled": "2026-09-25T13:10:00+00:00",
        "estimated": null,
        "actual": null
      },
      "airline": {"name": "Swiss International Air Lines", "iata": "LX", "icao": "SWR"},
      "flight": {"number": "14", "iata": "LX14", "icao": "SWR14", "codeshared": null},
      "aircraft": null,
      "live": null
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_aviationstack_parser.py
import json
from pathlib import Path

from swiss_grounding_mcp.sources.aviationstack.parser import (
    flight_field_presence,
    parse_flights,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "aviationstack"


def _read_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_parse_flights_maps_all_core_fields():
    body = _read_json("lx14_zrh_jfk.json")

    flights = parse_flights(body)

    assert len(flights) == 1
    flight = flights[0]
    assert flight.flight_number == "LX14"
    assert flight.flight_date == "2026-09-25"
    assert flight.airline.iata == "LX"
    assert flight.departure.airport.iata == "ZRH"
    assert flight.departure.scheduled == "2026-09-25T10:20:00+00:00"
    assert flight.departure.estimated == "2026-09-25T10:25:00+00:00"
    assert flight.departure.actual is None
    assert flight.departure.gate == "A12"
    assert flight.departure.delay_minutes == 5
    assert flight.arrival.airport.iata == "JFK"
    assert flight.flight_status == "scheduled"


def test_parse_flights_returns_empty_list_for_empty_data():
    body = _read_json("empty.json")

    assert parse_flights(body) == []


def test_flight_field_presence_reports_present_and_missing_fields():
    body = _read_json("lx14_partial_fields.json")
    flight_json = body["data"][0]

    present, missing = flight_field_presence(flight_json)

    assert "departure.scheduled" in present
    assert "departure.actual" in present
    assert "departure.terminal" in missing
    assert "departure.gate" in missing
    assert "arrival.estimated" in missing
    assert "arrival.actual" in missing
    assert "arrival.terminal" in present
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_aviationstack_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.sources.aviationstack.parser'`.

- [ ] **Step 4: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/aviationstack/parser.py
from __future__ import annotations

from swiss_grounding_mcp.domain.models import AirlineInfo, AirportInfo, Flight, FlightEndpoint

_ENDPOINT_FIELD_NAMES = ["scheduled", "estimated", "actual", "terminal", "gate"]


def _parse_endpoint(endpoint_json: dict | None) -> FlightEndpoint:
    endpoint_json = endpoint_json or {}
    airport = AirportInfo(
        iata=endpoint_json.get("iata"),
        icao=endpoint_json.get("icao"),
        name=endpoint_json.get("airport"),
        timezone=endpoint_json.get("timezone"),
    )
    return FlightEndpoint(
        airport=airport,
        scheduled=endpoint_json.get("scheduled"),
        estimated=endpoint_json.get("estimated"),
        actual=endpoint_json.get("actual"),
        terminal=endpoint_json.get("terminal"),
        gate=endpoint_json.get("gate"),
        delay_minutes=endpoint_json.get("delay"),
    )


def parse_flights(body: dict) -> list[Flight]:
    flights: list[Flight] = []
    for item in body.get("data", []):
        flight_info = item.get("flight") or {}
        airline_json = item.get("airline") or {}
        flights.append(
            Flight(
                flight_number=flight_info.get("iata") or flight_info.get("icao") or "",
                flight_date=item.get("flight_date", ""),
                airline=AirlineInfo(
                    name=airline_json.get("name"),
                    iata=airline_json.get("iata"),
                    icao=airline_json.get("icao"),
                ),
                departure=_parse_endpoint(item.get("departure")),
                arrival=_parse_endpoint(item.get("arrival")),
                flight_status=item.get("flight_status"),
            )
        )
    return flights


def flight_field_presence(flight_json: dict) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for side in ("departure", "arrival"):
        side_json = flight_json.get(side) or {}
        for field_name in _ENDPOINT_FIELD_NAMES:
            path = f"{side}.{field_name}"
            if side_json.get(field_name) is not None:
                present.append(path)
            else:
                missing.append(path)
    return present, missing
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_aviationstack_parser.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/aviationstack/parser.py \
        swiss-grounding-mcp/server/tests/unit/test_aviationstack_parser.py \
        swiss-grounding-mcp/server/tests/fixtures/aviationstack/lx14_partial_fields.json
git commit -m "feat: add Aviationstack response parser with field-presence tracking"
```

---

## Task 5: Static ZRH airport guidance and `get_airport_guidance` tool

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/zrh/__init__.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/zrh/guidance.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/get_airport_guidance.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_airport_guidance.py`

**Interfaces:**
- Consumes: nothing external.
- Produces: `GUIDANCE_TOPICS: dict[str, GuidanceRecord]` in
  `sources/zrh/guidance.py`, where `GuidanceRecord` is a small
  `NamedTuple(text: str, source: str, source_url: str)`, for topics
  `arrival_process`, `transfers`, `baggage`, `airport_rail_access`,
  `flight_status_verification`. And
  `get_airport_guidance(topic: str) -> AirportGuidanceResult` in
  `tools/get_airport_guidance.py`. Used by Task 9 (`server.py`).

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_airport_guidance.py
from swiss_grounding_mcp.tools.get_airport_guidance import get_airport_guidance

_VALID_TOPICS = [
    "arrival_process",
    "transfers",
    "baggage",
    "airport_rail_access",
    "flight_status_verification",
]


def test_every_valid_topic_returns_answered_with_zrh_citation():
    for topic in _VALID_TOPICS:
        result = get_airport_guidance(topic)

        assert result.status == "answered", topic
        assert result.guidance
        assert "flughafen-zuerich.ch" in result.source_url
        assert result.applicable_airport == "ZRH / LSZH"
        assert result.retrieved_at is not None


def test_unknown_topic_returns_out_of_scope():
    result = get_airport_guidance("visa_requirements")

    assert result.status == "out_of_scope"
    assert result.guidance is None
    assert "visa_requirements" in result.message


def test_empty_topic_returns_needs_context():
    result = get_airport_guidance("")

    assert result.status == "needs_context"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_airport_guidance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.tools.get_airport_guidance'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/zrh/__init__.py
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/zrh/guidance.py
from __future__ import annotations

from typing import NamedTuple


class GuidanceRecord(NamedTuple):
    text: str
    source: str
    source_url: str
    limitations: str


GUIDANCE_TOPICS: dict[str, GuidanceRecord] = {
    "arrival_process": GuidanceRecord(
        text=(
            "After landing at Zurich Airport, follow signs to Arrivals. Passengers "
            "arriving from outside the Schengen area go through passport control "
            "before baggage claim; passengers arriving within Schengen go directly "
            "to baggage claim. From Arrivals you can reach trains, buses, trams, "
            "taxis, and the car parks."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers",
        limitations=(
            "Passport/visa requirements depend on nationality and are set by "
            "Swiss federal authorities, not the airport; verify with the FDFA or "
            "your airline."
        ),
    ),
    "transfers": GuidanceRecord(
        text=(
            "If you already have a boarding pass for your connecting flight, "
            "check the departure time and gate on the flight information screens "
            "or the Zurich Airport website; your gate is shown at least 60 "
            "minutes before departure. If you do not have a boarding pass, "
            "collect it from your departure gate or a Transfer Desk (located in "
            "gate areas A, B, D and E). Self-connecting passengers whose baggage "
            "is not checked through to the final destination must leave the "
            "transit area and recheck their luggage, and should allow extra time "
            "and check current entry regulations for Switzerland."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers/fly/all-about-the-flight/transfer",
        limitations="Airline-specific transfer and rebooking rules are out of scope; verify with your airline.",
    ),
    "baggage": GuidanceRecord(
        text=(
            "Baggage trolleys are available free of charge at airport entrances "
            "and exits. Porter and concierge escort services (CGS) can assist "
            "with baggage on departure, arrival, or transfer; pre-booking is "
            "recommended. A home baggage collection and check-in service is "
            "available for selected airlines and Swiss addresses, with luggage "
            "collected the day before or the day of departure."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers/practical/services/services-for-travellers/baggageservices",
        limitations=(
            "Checked-baggage allowances, fees, and lost-baggage claims are set "
            "by individual airlines and are out of scope; verify with your "
            "airline."
        ),
    ),
    "airport_rail_access": GuidanceRecord(
        text=(
            "Zurich Airport has its own railway station (Zürich Flughafen) "
            "directly beneath the terminal, served by SBB trains including "
            "direct connections to Zürich HB and onward across Switzerland. "
            "From Arrivals, follow signage to the SBB platforms; step-free "
            "access is available via the car-park elevators to Check-in Level 3."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers/practical/parking-and-transport",
        limitations=(
            "For live train times and connections beyond Zürich HB, use this "
            "server's train-connections tool, which is grounded in "
            "opentransportdata.swiss OJP 2.0."
        ),
    ),
    "flight_status_verification": GuidanceRecord(
        text=(
            "To verify the latest scheduled, estimated, or actual time for a "
            "specific flight, use this server's flight-lookup tool, or check "
            "the official Zurich Airport arrivals/departures pages directly."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers/fly/flightinformation/arrivals",
        limitations=(
            "This server's own flight-lookup tool is sourced from "
            "aviationstack.com, a third-party aggregator, not from Zurich "
            "Airport's operational systems; always treat times as estimates "
            "until confirmed by the airline or airport display."
        ),
    ),
}
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/get_airport_guidance.py
from __future__ import annotations

from datetime import datetime, timezone

from swiss_grounding_mcp.domain.models import AirportGuidanceResult
from swiss_grounding_mcp.sources.zrh.guidance import GUIDANCE_TOPICS


def get_airport_guidance(topic: str) -> AirportGuidanceResult:
    if not topic or not topic.strip():
        return AirportGuidanceResult(
            status="needs_context",
            topic=topic,
            message="Please specify a guidance topic.",
        )

    record = GUIDANCE_TOPICS.get(topic)
    if record is None:
        return AirportGuidanceResult(
            status="out_of_scope",
            topic=topic,
            message=(
                f"'{topic}' is not a supported guidance topic. Supported topics: "
                + ", ".join(sorted(GUIDANCE_TOPICS))
            ),
        )

    return AirportGuidanceResult(
        status="answered",
        topic=topic,
        guidance=record.text,
        source=record.source,
        source_url=record.source_url,
        retrieved_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        applicable_airport="ZRH / LSZH",
        limitations=record.limitations,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_airport_guidance.py -v`
Expected: PASS (3 tests, the first parametrized loop covering 5 topics).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/zrh \
        swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/get_airport_guidance.py \
        swiss-grounding-mcp/server/tests/unit/test_airport_guidance.py
git commit -m "feat: add ZRH static airport guidance tool"
```

---

## Task 6: `find_flight_by_number` tool

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/evidence/aviation_provenance.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/find_flight_by_number.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_find_flight_by_number.py`

**Interfaces:**
- Consumes: `AviationstackClient.get_flights(params) -> dict`,
  `AviationstackSourceError`, `parse_flights`, `flight_field_presence`
  (Tasks 3, 4), `Settings` (Task 1), `FlightLookupResult`,
  `AviationProvenance` (Task 2).
- Produces: `build_aviation_provenance(settings, *, applicable_date,
  retrieved_at=None) -> AviationProvenance` in
  `evidence/aviation_provenance.py`; and
  `find_flight_by_number(flight_number: str, flight_date: str, direction:
  str | None, *, client, settings) -> FlightLookupResult` in
  `tools/find_flight_by_number.py`. Used by Task 9 (`server.py`) and
  Task 8 (`connect_flight_to_train`, which calls this function directly).

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_find_flight_by_number.py
from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackSourceError
from swiss_grounding_mcp.tools.find_flight_by_number import find_flight_by_number

_LX14_BODY = {
    "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 1},
    "data": [
        {
            "flight_date": "2026-09-25",
            "flight_status": "scheduled",
            "departure": {
                "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH", "icao": "LSZH",
                "terminal": "1", "gate": "A12", "delay": 5,
                "scheduled": "2026-09-25T10:20:00+00:00",
                "estimated": "2026-09-25T10:25:00+00:00", "actual": None,
            },
            "arrival": {
                "airport": "JFK", "timezone": "America/New_York", "iata": "JFK", "icao": "KJFK",
                "terminal": "4", "gate": "B22", "delay": None,
                "scheduled": "2026-09-25T13:10:00+00:00",
                "estimated": "2026-09-25T13:05:00+00:00", "actual": None,
            },
            "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
            "flight": {"number": "14", "iata": "LX14", "icao": "SWR14", "codeshared": None},
            "aircraft": None,
            "live": None,
        }
    ],
}

_EMPTY_BODY = {"pagination": {"limit": 1, "offset": 0, "count": 0, "total": 0}, "data": []}


class StubAviationstackClient:
    def __init__(self, body=None, raise_error=None):
        self.body = body
        self.raise_error = raise_error
        self.calls = []

    def get_flights(self, params):
        self.calls.append(params)
        if self.raise_error is not None:
            raise self.raise_error
        return self.body


def _settings() -> Settings:
    return Settings.from_env({"AVIATIONSTACK_BASE_URL": "https://example.test/v1"})


def test_missing_flight_number_returns_needs_context():
    client = StubAviationstackClient(body=_LX14_BODY)

    result = find_flight_by_number("", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "needs_context"
    assert client.calls == []


def test_missing_flight_date_returns_needs_context():
    client = StubAviationstackClient(body=_LX14_BODY)

    result = find_flight_by_number("LX14", "", None, client=client, settings=_settings())

    assert result.status == "needs_context"


def test_found_flight_returns_answered_with_provenance_and_field_lists():
    client = StubAviationstackClient(body=_LX14_BODY)

    result = find_flight_by_number("LX14", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "answered"
    assert result.flight.flight_number == "LX14"
    assert "departure.scheduled" in result.fields_present
    assert "departure.actual" in result.fields_missing
    assert result.provenance.source == "aviationstack.com"
    assert result.provenance.applicable_date == "2026-09-25"
    assert result.provenance.timezone == "Europe/Zurich"
    assert client.calls[0]["flight_iata"] == "LX14"
    assert client.calls[0]["flight_date"] == "2026-09-25"


def test_flight_number_is_normalized_before_query():
    client = StubAviationstackClient(body=_LX14_BODY)

    find_flight_by_number("lx 14", "2026-09-25", None, client=client, settings=_settings())

    assert client.calls[0]["flight_iata"] == "LX14"


def test_direction_arrival_filters_by_zrh_arrival():
    client = StubAviationstackClient(body=_LX14_BODY)

    find_flight_by_number("LX14", "2026-09-25", "arrival", client=client, settings=_settings())

    assert client.calls[0]["arr_iata"] == "ZRH"


def test_direction_departure_filters_by_zrh_departure():
    client = StubAviationstackClient(body=_LX14_BODY)

    find_flight_by_number("LX14", "2026-09-25", "departure", client=client, settings=_settings())

    assert client.calls[0]["dep_iata"] == "ZRH"


def test_no_matching_flight_returns_insufficient_evidence():
    client = StubAviationstackClient(body=_EMPTY_BODY)

    result = find_flight_by_number("XX9999", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "insufficient_evidence"
    assert result.flight is None


def test_source_failure_returns_source_unavailable():
    client = StubAviationstackClient(raise_error=AviationstackSourceError("quota exceeded"))

    result = find_flight_by_number("LX14", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "source_unavailable"
    assert "quota exceeded" in result.message
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_find_flight_by_number.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.tools.find_flight_by_number'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/evidence/aviation_provenance.py
from __future__ import annotations

from datetime import datetime, timezone

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import AviationProvenance


def build_aviation_provenance(
    settings: Settings, *, applicable_date: str, retrieved_at: datetime | None = None
) -> AviationProvenance:
    timestamp = retrieved_at or datetime.now(timezone.utc)
    return AviationProvenance(
        source="aviationstack.com",
        source_url=f"{settings.aviationstack_base_url}/flights",
        retrieved_at=timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        applicable_date=applicable_date,
        timezone="Europe/Zurich",
    )
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/find_flight_by_number.py
from __future__ import annotations

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FlightLookupResult
from swiss_grounding_mcp.evidence.aviation_provenance import build_aviation_provenance
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackSourceError
from swiss_grounding_mcp.sources.aviationstack.parser import (
    flight_field_presence,
    parse_flights,
)


def _normalize_flight_number(value: str) -> str:
    return value.strip().upper().replace(" ", "")


def find_flight_by_number(
    flight_number: str,
    flight_date: str,
    direction: str | None,
    *,
    client,
    settings: Settings,
) -> FlightLookupResult:
    if not flight_number or not flight_number.strip():
        return FlightLookupResult(
            status="needs_context",
            message="Please provide a flight number, e.g. 'LX14'.",
        )
    if not flight_date or not flight_date.strip():
        return FlightLookupResult(
            status="needs_context",
            message="Please provide a flight date in YYYY-MM-DD format.",
        )

    normalized_number = _normalize_flight_number(flight_number)
    params: dict[str, str] = {"flight_iata": normalized_number, "flight_date": flight_date}
    if direction == "arrival":
        params["arr_iata"] = "ZRH"
    elif direction == "departure":
        params["dep_iata"] = "ZRH"

    try:
        body = client.get_flights(params)
    except AviationstackSourceError as exc:
        return FlightLookupResult(status="source_unavailable", message=str(exc))

    raw_flights = body.get("data", [])
    if not raw_flights:
        return FlightLookupResult(
            status="insufficient_evidence",
            message=f"No flight found for '{flight_number}' on {flight_date}.",
        )

    flights = parse_flights(body)
    fields_present, fields_missing = flight_field_presence(raw_flights[0])

    return FlightLookupResult(
        status="answered",
        flight=flights[0],
        fields_present=fields_present,
        fields_missing=fields_missing,
        provenance=build_aviation_provenance(settings, applicable_date=flight_date),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_find_flight_by_number.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/evidence/aviation_provenance.py \
        swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/find_flight_by_number.py \
        swiss-grounding-mcp/server/tests/unit/test_find_flight_by_number.py
git commit -m "feat: add find_flight_by_number tool"
```

---

## Task 7: `search_airport_flights` tool

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/search_airport_flights.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_search_airport_flights.py`

**Interfaces:**
- Consumes: same as Task 6 (`AviationstackClient`, `parse_flights`,
  `build_aviation_provenance`, `FlightSearchResult`).
- Produces: `search_airport_flights(direction: str, flight_date: str,
  airport_iata: str | None, airport_icao: str | None, airline_iata: str |
  None, limit: int, *, client, settings) -> FlightSearchResult`. Used by
  Task 9 (`server.py`).

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_search_airport_flights.py
from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackSourceError
from swiss_grounding_mcp.tools.search_airport_flights import search_airport_flights

_TWO_FLIGHTS_BODY = {
    "pagination": {"limit": 10, "offset": 0, "count": 2, "total": 2},
    "data": [
        {
            "flight_date": "2026-09-25", "flight_status": "scheduled",
            "departure": {
                "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH", "icao": "LSZH",
                "terminal": "1", "gate": "A12", "delay": None,
                "scheduled": "2026-09-25T10:20:00+00:00", "estimated": None, "actual": None,
            },
            "arrival": {
                "airport": "JFK", "timezone": "America/New_York", "iata": "JFK", "icao": "KJFK",
                "terminal": "4", "gate": None, "delay": None,
                "scheduled": "2026-09-25T13:10:00+00:00", "estimated": None, "actual": None,
            },
            "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
            "flight": {"number": "14", "iata": "LX14", "icao": "SWR14", "codeshared": None},
            "aircraft": None, "live": None,
        },
        {
            "flight_date": "2026-09-25", "flight_status": "scheduled",
            "departure": {
                "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH", "icao": "LSZH",
                "terminal": "1", "gate": "A14", "delay": None,
                "scheduled": "2026-09-25T18:00:00+00:00", "estimated": None, "actual": None,
            },
            "arrival": {
                "airport": "JFK", "timezone": "America/New_York", "iata": "JFK", "icao": "KJFK",
                "terminal": "4", "gate": None, "delay": None,
                "scheduled": "2026-09-25T21:00:00+00:00", "estimated": None, "actual": None,
            },
            "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
            "flight": {"number": "16", "iata": "LX16", "icao": "SWR16", "codeshared": None},
            "aircraft": None, "live": None,
        },
    ],
}

_EMPTY_BODY = {"pagination": {"limit": 10, "offset": 0, "count": 0, "total": 0}, "data": []}


class StubAviationstackClient:
    def __init__(self, body=None, raise_error=None):
        self.body = body
        self.raise_error = raise_error
        self.calls = []

    def get_flights(self, params):
        self.calls.append(params)
        if self.raise_error is not None:
            raise self.raise_error
        return self.body


def _settings() -> Settings:
    return Settings.from_env({"AVIATIONSTACK_BASE_URL": "https://example.test/v1"})


def test_missing_direction_returns_needs_context():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "", "2026-09-25", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"


def test_missing_flight_date_returns_needs_context():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "departure", "", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"


def test_departure_search_filters_by_zrh_and_destination_airport():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert len(result.flights) == 2
    assert client.calls[0]["dep_iata"] == "ZRH"
    assert client.calls[0]["arr_iata"] == "JFK"


def test_arrival_search_filters_by_zrh_and_origin_airport():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    search_airport_flights(
        "arrival", "2026-09-25", "JFK", None, None, 10, client=client, settings=_settings()
    )

    assert client.calls[0]["arr_iata"] == "ZRH"
    assert client.calls[0]["dep_iata"] == "JFK"


def test_no_airport_code_and_no_airline_returns_needs_context():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "departure", "2026-09-25", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"
    assert "airport" in result.message.lower()
    assert client.calls == []


def test_airline_only_filter_is_accepted_without_airport_code():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "departure", "2026-09-25", None, None, "LX", 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert client.calls[0]["airline_iata"] == "LX"


def test_no_matching_flights_returns_insufficient_evidence():
    client = StubAviationstackClient(body=_EMPTY_BODY)

    result = search_airport_flights(
        "departure", "2026-09-25", "XXX", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "insufficient_evidence"
    assert result.flights == []


def test_source_failure_returns_source_unavailable():
    client = StubAviationstackClient(raise_error=AviationstackSourceError("network down"))

    result = search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "source_unavailable"


def test_limit_is_clamped_to_valid_range():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 0, client=client, settings=_settings()
    )
    assert client.calls[0]["limit"] == 1

    search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 1000, client=client, settings=_settings()
    )
    assert client.calls[1]["limit"] == 100
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_search_airport_flights.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.tools.search_airport_flights'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/search_airport_flights.py
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_search_airport_flights.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/search_airport_flights.py \
        swiss-grounding-mcp/server/tests/unit/test_search_airport_flights.py
git commit -m "feat: add search_airport_flights tool"
```

---

## Task 8: `connect_flight_to_train` tool

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/connect_flight_to_train.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_connect_flight_to_train.py`

**Interfaces:**
- Consumes: `find_flight_by_number` (Task 6), `find_train_connections`
  (existing, `tools/find_connections.py`), `FlightToTrainResult` (Task
  2).
- Produces: `connect_flight_to_train(flight_number: str | None,
  flight_date: str | None, confirmed_arrival_time: str | None,
  destination_station: str, transfer_buffer_minutes: int, rail_results:
  int, *, aviation_client, ojp_client, settings) -> FlightToTrainResult`.
  Used by Task 9 (`server.py`).

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_connect_flight_to_train.py
from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Connection, StopCandidate
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackSourceError
from swiss_grounding_mcp.tools.connect_flight_to_train import connect_flight_to_train

_LX14_ARRIVAL_BODY = {
    "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 1},
    "data": [
        {
            "flight_date": "2026-09-25", "flight_status": "scheduled",
            "departure": {
                "airport": "JFK", "timezone": "America/New_York", "iata": "JFK", "icao": "KJFK",
                "terminal": None, "gate": None, "delay": None,
                "scheduled": "2026-09-25T09:00:00+00:00", "estimated": None, "actual": None,
            },
            "arrival": {
                "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH", "icao": "LSZH",
                "terminal": "2", "gate": None, "delay": None,
                "scheduled": "2026-09-25T22:00:00+00:00", "estimated": "2026-09-25T22:10:00+00:00",
                "actual": None,
            },
            "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
            "flight": {"number": "15", "iata": "LX15", "icao": "SWR15", "codeshared": None},
            "aircraft": None, "live": None,
        }
    ],
}


class StubAviationstackClient:
    def __init__(self, body=None, raise_error=None):
        self.body = body
        self.raise_error = raise_error

    def get_flights(self, params):
        if self.raise_error is not None:
            raise self.raise_error
        return self.body


class StubOjpClient:
    def __init__(self):
        self.trip_calls = []

    def location_information(self, name):
        return [StopCandidate(name=name, stop_ref=f"ch:1:sloid:{abs(hash(name)) % 9999}", probability=1.0)]

    def trip_request(self, origin_ref, destination_ref, **kwargs):
        self.trip_calls.append({"origin_ref": origin_ref, "destination_ref": destination_ref, **kwargs})
        return [
            Connection(
                departure="2026-09-25T23:10:00Z",
                arrival="2026-09-26T00:03:00Z",
                duration_minutes=53,
                changes=0,
                legs=[],
            )
        ]


def _settings() -> Settings:
    return Settings.from_env({"AVIATIONSTACK_BASE_URL": "https://example.test/v1"})


def test_missing_destination_returns_needs_context():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "", 60, 3,
        aviation_client=StubAviationstackClient(body=_LX14_ARRIVAL_BODY),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"


def test_buffer_below_minimum_returns_needs_context():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 5, 3,
        aviation_client=StubAviationstackClient(body=_LX14_ARRIVAL_BODY),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"
    assert "buffer" in result.message.lower()


def test_missing_flight_and_confirmed_time_returns_needs_context():
    result = connect_flight_to_train(
        None, None, None, "Bern", 60, 3,
        aviation_client=StubAviationstackClient(body=_LX14_ARRIVAL_BODY),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"


def test_flight_lookup_success_computes_buffered_departure_and_calls_ojp():
    ojp_client = StubOjpClient()
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAviationstackClient(body=_LX14_ARRIVAL_BODY),
        ojp_client=ojp_client,
        settings=_settings(),
    )

    assert result.status == "answered"
    assert result.flight.flight_number == "LX15"
    assert len(result.train_connections) == 1
    assert result.flight_provenance.source == "aviationstack.com"
    assert result.rail_provenance is not None
    assert result.rail_provenance is not result.flight_provenance
    assert ojp_client.trip_calls[0]["departure_time"] == "2026-09-25T23:10:00+00:00"


def test_confirmed_arrival_time_skips_flight_lookup():
    ojp_client = StubOjpClient()
    result = connect_flight_to_train(
        None, None, "2026-09-25T22:00:00+00:00", "Bern", 30, 3,
        aviation_client=StubAviationstackClient(raise_error=AviationstackSourceError("should not be called")),
        ojp_client=ojp_client,
        settings=_settings(),
    )

    assert result.status == "answered"
    assert result.flight is None
    assert ojp_client.trip_calls[0]["departure_time"] == "2026-09-25T22:30:00+00:00"


def test_flight_lookup_source_unavailable_asks_for_confirmed_time():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAviationstackClient(raise_error=AviationstackSourceError("quota exceeded")),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"
    assert "confirmed_arrival_time" in result.message


def test_flight_not_found_returns_insufficient_evidence():
    empty_body = {"pagination": {"limit": 1, "offset": 0, "count": 0, "total": 0}, "data": []}

    result = connect_flight_to_train(
        "XX999", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAviationstackClient(body=empty_body),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "insufficient_evidence"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_connect_flight_to_train.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.tools.connect_flight_to_train'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/connect_flight_to_train.py
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_connect_flight_to_train.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/connect_flight_to_train.py \
        swiss-grounding-mcp/server/tests/unit/test_connect_flight_to_train.py
git commit -m "feat: add connect_flight_to_train tool"
```

---

## Task 9: Register aviation tools on the MCP server

**Files:**
- Modify: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/server.py`
- Modify: `swiss-grounding-mcp/server/tests/unit/test_server_registration.py`

**Interfaces:**
- Consumes: `AviationstackClient` (Task 3), all four tool functions
  (Tasks 5, 6, 7, 8), existing `OjpClient`/`get_client()`.
- Produces: four new `@mcp.tool()`-registered functions:
  `find_flight_by_number`, `search_airport_flights`,
  `get_airport_guidance`, `connect_flight_to_train`, discoverable and
  callable by any MCP client connected to `mcp`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_server_registration.py`:

```python
from swiss_grounding_mcp.domain.models import (
    AirlineInfo,
    AirportInfo,
    Flight,
    FlightEndpoint,
)


class StubAviationstackClient:
    def get_flights(self, params):
        return {
            "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 1},
            "data": [
                {
                    "flight_date": params.get("flight_date", "2026-09-25"),
                    "flight_status": "scheduled",
                    "departure": {
                        "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH",
                        "icao": "LSZH", "terminal": "1", "gate": "A12", "delay": None,
                        "scheduled": "2026-09-25T10:20:00+00:00", "estimated": None, "actual": None,
                    },
                    "arrival": {
                        "airport": "JFK", "timezone": "America/New_York", "iata": "JFK",
                        "icao": "KJFK", "terminal": "4", "gate": None, "delay": None,
                        "scheduled": "2026-09-25T13:10:00+00:00", "estimated": None, "actual": None,
                    },
                    "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
                    "flight": {"number": "14", "iata": "LX14", "icao": "SWR14", "codeshared": None},
                    "aircraft": None,
                    "live": None,
                }
            ],
        }


def test_aviation_tools_are_registered_and_callable(monkeypatch):
    monkeypatch.setattr(server_module, "get_client", lambda: StubClient())
    monkeypatch.setattr(server_module, "get_aviation_client", lambda: StubAviationstackClient())

    async def run():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools.tools]
            for expected in [
                "find_flight_by_number",
                "search_airport_flights",
                "get_airport_guidance",
                "connect_flight_to_train",
            ]:
                assert expected in names

            flight_result = await client.call_tool(
                "find_flight_by_number", {"flight_number": "LX14", "flight_date": "2026-09-25"}
            )
            assert flight_result.structured_content["status"] == "answered"

            guidance_result = await client.call_tool(
                "get_airport_guidance", {"topic": "transfers"}
            )
            assert guidance_result.structured_content["status"] == "answered"

            connect_result = await client.call_tool(
                "connect_flight_to_train",
                {
                    "flight_number": None,
                    "flight_date": None,
                    "confirmed_arrival_time": "2026-09-25T22:00:00+00:00",
                    "destination_station": "Bern",
                    "transfer_buffer_minutes": 30,
                    "rail_results": 3,
                },
            )
            assert connect_result.structured_content["status"] == "answered"

    asyncio.run(run())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_server_registration.py -v`
Expected: FAIL — the new tool names are not registered yet.

- [ ] **Step 3: Register the tools in `server.py`**

Modify `src/swiss_grounding_mcp/server.py`:

```python
from __future__ import annotations

import argparse

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import (
    AirportGuidanceResult,
    ConnectionSearchResult,
    FlightLookupResult,
    FlightSearchResult,
    FlightToTrainResult,
)
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackClient
from swiss_grounding_mcp.sources.ojp.client import OjpClient
from swiss_grounding_mcp.tools.connect_flight_to_train import connect_flight_to_train as _connect_flight_to_train
from swiss_grounding_mcp.tools.find_connections import find_train_connections
from swiss_grounding_mcp.tools.find_flight_by_number import find_flight_by_number as _find_flight_by_number
from swiss_grounding_mcp.tools.get_airport_guidance import get_airport_guidance as _get_airport_guidance
from swiss_grounding_mcp.tools.search_airport_flights import search_airport_flights as _search_airport_flights

load_dotenv()

settings = Settings.from_env()
mcp = MCPServer("Swiss Grounding MCP")

_client: OjpClient | None = None
_aviation_client: AviationstackClient | None = None


def get_client() -> OjpClient:
    global _client
    if _client is None:
        _client = OjpClient(settings)
    return _client


def get_aviation_client() -> AviationstackClient:
    global _aviation_client
    if _aviation_client is None:
        _aviation_client = AviationstackClient(settings)
    return _aviation_client


@mcp.tool()
def find_connections(
    origin: str,
    destination: str,
    departure_time: str | None = None,
    arrival_time: str | None = None,
    results: int = 3,
) -> ConnectionSearchResult:
    """Find Swiss passenger-train connections between two stations.

    Scope: the current Swiss public-transport timetable only, via OJP 2.0
    (opentransportdata.swiss). Covers origin-to-destination connection
    search with an optional departure or arrival time. Does not cover
    fares, single-stop departure boards, disruption feeds, or non-Swiss
    travel. If the origin or destination is outside Switzerland, is not a
    recognizable station, or the question is unrelated to travel, this
    tool will say so rather than guess.
    """
    return find_train_connections(
        origin,
        destination,
        departure_time,
        arrival_time,
        results,
        client=get_client(),
        settings=settings,
    )


@mcp.tool()
def find_flight_by_number(
    flight_number: str,
    flight_date: str,
    direction: str | None = None,
) -> FlightLookupResult:
    """Look up a flight at Zurich Airport (ZRH) by flight number and date.

    Scope: scheduled/estimated/actual times, terminal, gate, and delay as
    reported by aviationstack.com, a third-party aggregator (not the
    airport operator). Only fields present in the response are returned.
    direction, if given, is 'arrival' or 'departure' at ZRH. Does not
    cover fares, visas, or airline-specific rules.
    """
    return _find_flight_by_number(
        flight_number, flight_date, direction, client=get_aviation_client(), settings=settings
    )


@mcp.tool()
def search_airport_flights(
    direction: str,
    flight_date: str,
    airport_iata: str | None = None,
    airport_icao: str | None = None,
    airline_iata: str | None = None,
    limit: int = 10,
) -> FlightSearchResult:
    """Search ZRH arrivals or departures for a date.

    direction is 'arrival' or 'departure'. Filter by the exact IATA/ICAO
    code of the other airport (a city or country name is not accepted;
    the tool will ask for the precise airport code) and/or an airline
    IATA code. Data via aviationstack.com.
    """
    return _search_airport_flights(
        direction,
        flight_date,
        airport_iata,
        airport_icao,
        airline_iata,
        limit,
        client=get_aviation_client(),
        settings=settings,
    )


@mcp.tool()
def get_airport_guidance(topic: str) -> AirportGuidanceResult:
    """Cited Zurich Airport passenger guidance.

    Topics: arrival_process, transfers, baggage, airport_rail_access,
    flight_status_verification. Every answer cites an official Zurich
    Airport (flughafen-zuerich.ch) page. Does not cover visa/immigration
    rules or airline-specific policies.
    """
    return _get_airport_guidance(topic)


@mcp.tool()
def connect_flight_to_train(
    destination_station: str,
    transfer_buffer_minutes: int,
    flight_number: str | None = None,
    flight_date: str | None = None,
    confirmed_arrival_time: str | None = None,
    rail_results: int = 3,
) -> FlightToTrainResult:
    """Connect a ZRH arrival to onward Swiss train travel.

    Provide either flight_number + flight_date (looked up via
    aviationstack.com) or a confirmed_arrival_time. transfer_buffer_minutes
    (minimum 15) is added to the arrival time before searching trains via
    OJP 2.0 from Zürich Flughafen. Never assumes a train is reachable
    without this explicit buffer.
    """
    return _connect_flight_to_train(
        flight_number,
        flight_date,
        confirmed_arrival_time,
        destination_station,
        transfer_buffer_minutes,
        rail_results,
        aviation_client=get_aviation_client(),
        ojp_client=get_client(),
        settings=settings,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Swiss Grounding MCP server")
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http"], default="stdio"
    )
    parser.add_argument("--host", default=settings.mcp_http_host)
    parser.add_argument("--port", type=int, default=settings.mcp_http_port)
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_server_registration.py -v`
Expected: PASS (both the original and new test).

- [ ] **Step 5: Run the full test suite**

Run: `cd swiss-grounding-mcp/server && uv run pytest -v`
Expected: PASS (all tests across every module).

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/server.py \
        swiss-grounding-mcp/server/tests/unit/test_server_registration.py
git commit -m "feat: register aviation tools on the MCP server"
```

---

## Task 10: README updates and manual verification checklist

**Files:**
- Modify: `swiss-grounding-mcp/server/README.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: updated README sections; no code interfaces.

- [ ] **Step 1: Update the declared scope section**

In `swiss-grounding-mcp/server/README.md`, update the title and
"Declared scope" section to add the aviation module:

```markdown
# Swiss Grounding MCP — Train Connections & ZRH Aviation Server

An MCP server that answers Swiss passenger-train connection questions
using live data from [OJP 2.0](https://opentransportdata.swiss/en/cookbook/open-journey-planner-ojp-landing-page/)
(`opentransportdata.swiss`, operated under a Federal Office of Transport
mandate), and Zurich Airport (ZRH) flight and passenger-guidance
questions using [Aviationstack](https://aviationstack.com/) and official
Zurich Airport (`flughafen-zuerich.ch`) pages.

## Declared scope

**Train connections:**
- **Topics:** Swiss passenger-train connection lookups between two named
  stations, for a given (optional) date/time.
- **Geography:** all stations reachable via the OJP 2.0 network (all of
  Switzerland).
- **Reference period:** live/current OJP timetable data at query time; no
  historical timetable queries.

**ZRH aviation:**
- **Topics:** flight lookup by flight number and date; arrivals/departures
  search by airport code and date; cited passenger guidance for arrival
  process, transfers, baggage, airport rail access, and flight-status
  verification; connecting a ZRH arrival to onward Swiss train travel.
- **Geography:** Zurich Airport (ZRH / LSZH) only. Flight data covers any
  route to/from ZRH that Aviationstack indexes.
- **Reference period:** live/current flight data via Aviationstack. No
  historical flight queries.
- **Data quality note:** Aviationstack is a commercial flight-data
  aggregator, not the airport operator or a Swiss aviation authority.
  Times, gates, and delays are reported only when present in the
  provider's response; the server never infers or guesses a value.
  Static airport guidance is sourced directly from official
  `flughafen-zuerich.ch` pages.

**Out of scope (both modules):** fares, departure boards beyond what's
described above, visas/immigration rules, airline-specific policies,
non-Swiss/non-ZRH topics, and every other challenge topic area (taxes,
health insurance, waste collection, etc). Out-of-scope questions get an
honest response, never a guess.
```

- [ ] **Step 2: Add Aviationstack to "Required credentials"**

Update the "Required credentials" section:

```markdown
## Required credentials

- `OJP_API_TOKEN`: a free API token for OJP 2.0. Register an app and
  subscribe to the "OJP 2.0" product at
  <https://api-manager.opentransportdata.swiss/>. Free tier limits: 50
  requests/minute, 20,000/day.
- `AVIATIONSTACK_API_KEY`: an API key for [Aviationstack](https://aviationstack.com/).
  Sign up for the free plan (~100–500 requests/month, personal-use
  license) or a paid plan for higher volume and a commercial license.
  Without this key, the aviation flight-lookup and flight-search tools
  return `source_unavailable`; the airport-guidance tool still works
  (it uses static, pre-written content, not a live API call).

No other credentials or API keys are required. The server makes no LLM
calls itself.
```

- [ ] **Step 3: Document the new tools**

Add a new section after "The `find_connections` tool":

```markdown
## The aviation tools

All four tools return a structured object with a `status` of `answered`,
`needs_context`, `insufficient_evidence`, `out_of_scope`, or
`source_unavailable` — distinct from the train tool's status set above.

### `find_flight_by_number`

Input: `flight_number` (str, e.g. `LX14`), `flight_date` (str,
`YYYY-MM-DD`), `direction` (optional, `arrival` or `departure` at ZRH).

Output includes `flight` (only for `answered`), `fields_present` /
`fields_missing` (which time/gate/terminal fields the provider actually
supplied), and `provenance` (source, source_url, retrieved_at,
applicable_date, timezone).

### `search_airport_flights`

Input: `direction` (`arrival`/`departure`, required), `flight_date`
(required), `airport_iata`/`airport_icao` (the other airport's exact
code — a city or country name is rejected with `needs_context`),
`airline_iata` (optional), `limit` (default 10, max 100).

### `get_airport_guidance`

Input: `topic`, one of `arrival_process`, `transfers`, `baggage`,
`airport_rail_access`, `flight_status_verification`. Returns
pre-written, cited guidance with a `flughafen-zuerich.ch` source URL.
Does not call any external API.

### `connect_flight_to_train`

Input: `destination_station` and `transfer_buffer_minutes` (minimum 15,
required); plus either `flight_number` + `flight_date`, or
`confirmed_arrival_time`; `rail_results` (default 3, max 5).

Looks up the ZRH arrival time (or uses the confirmed time), adds the
transfer buffer, and searches Swiss train connections from Zürich
Flughafen via the existing OJP-based logic. The response carries
separate `flight_provenance` and `rail_provenance` blocks. If flight
lookup fails, the tool asks for `confirmed_arrival_time` instead of
guessing.
```

- [ ] **Step 4: Extend the manual verification checklist**

Append to "Manual verification checklist":

```markdown
6. Call `find_flight_by_number` with a real ZRH flight number and
   today's or tomorrow's date; confirm an `answered` response with a
   `provenance.source_url` under `aviationstack.com`.
7. Call `get_airport_guidance` with `topic="transfers"`; confirm the
   `source_url` is under `flughafen-zuerich.ch`.
8. Call `search_airport_flights` with `direction="departure"` and no
   `airport_iata`/`airport_icao`/`airline_iata`; confirm `needs_context`.
9. Call `find_flight_by_number` with a nonexistent flight number;
   confirm `insufficient_evidence`, not a guessed answer.
10. Temporarily set `AVIATIONSTACK_API_KEY` to an empty value and call
    `find_flight_by_number`; confirm `source_unavailable`, and that
    `get_airport_guidance` still returns `answered` (it needs no API key).
11. Call `connect_flight_to_train` with a real flight number, date, a
    destination station, and `transfer_buffer_minutes=45`; confirm
    separate `flight_provenance` and `rail_provenance` blocks and that
    the train search departure time is the flight's arrival time plus
    the buffer.
```

- [ ] **Step 5: Update "Limitations"**

```markdown
## Limitations

- Milestone 1 (train) only covers connection search; no fares, departure
  boards, disruption feeds, or non-rail modes.
- Station name resolution uses OJP's own fuzzy matching; extremely
  ambiguous or misspelled names may require a follow-up clarification.
- The aviation module covers ZRH only, is backed by a third-party
  aggregator (Aviationstack) rather than the airport operator, and does
  not cover historical flights, fares, visas, or airline-specific rules.
- The Aviationstack free tier has a small monthly request quota; the
  client caches identical requests for `AVIATIONSTACK_CACHE_SECONDS`
  (default 60s) to conserve it, but sustained heavy use requires a paid
  plan.
```

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/server/README.md
git commit -m "docs: document ZRH aviation tools, credentials, and verification steps"
```

---

## Task 11: Full verification pass

**Files:** none (verification only).

**Interfaces:** none.

- [ ] **Step 1: Run the full unit test suite**

Run: `cd swiss-grounding-mcp/server && uv run pytest -v`
Expected: PASS, all tests across `test_settings.py`,
`test_aviation_domain_models.py`, `test_aviationstack_client.py`,
`test_aviationstack_parser.py`, `test_airport_guidance.py`,
`test_find_flight_by_number.py`, `test_search_airport_flights.py`,
`test_connect_flight_to_train.py`, `test_server_registration.py`, and
all pre-existing OJP/train tests.

- [ ] **Step 2: Manual MCP Inspector check with a live Aviationstack key**

With `AVIATIONSTACK_API_KEY` set in `.env` to the user's real key, run:

```bash
cd swiss-grounding-mcp/server
uv run swiss-grounding-mcp
```

In another terminal:

```bash
uv run mcp dev src/swiss_grounding_mcp/server.py
```

In MCP Inspector, list tools and confirm all six tools appear
(`find_connections`, `find_flight_by_number`, `search_airport_flights`,
`get_airport_guidance`, `connect_flight_to_train`). Call
`find_flight_by_number` with a real current/near-term ZRH flight number
and date; record whether it returns `answered` (live check passed) or
`insufficient_evidence`/`source_unavailable` (record the reason —
e.g., free-tier quota, no such flight today).

- [ ] **Step 3: Report results**

Document in the PR/commit message or session notes: which checks were
run automatically (unit tests, fixture-based), which were run manually
against the live Aviationstack API (and their outcome), and any
remaining source-dependent limitations (e.g., free-tier quota
exhaustion, fields the provider didn't supply for the tested flight).

- [ ] **Step 4: Final commit if any fixups were needed**

```bash
git add -A
git commit -m "test: verify ZRH aviation module end to end"
```

(Skip this commit if Steps 1–3 required no code changes.)
