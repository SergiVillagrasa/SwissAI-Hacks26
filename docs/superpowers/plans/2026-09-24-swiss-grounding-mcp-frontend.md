# Swiss Grounding MCP — Chat Frontend & Agent Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a chat-style frontend for the Swiss Grounding MCP project where every travel-tool result renders as a visual widget (train connections, flights, a route map, station boards, fares, disruptions, airport guidance) instead of chat prose, backed by a new FastAPI agent that wires OpenAI tool-calling to the existing MCP tool functions.

**Architecture:** A new `swiss-grounding-mcp/agent-backend/` FastAPI service imports the existing tool functions from `swiss_grounding_mcp` directly (no MCP transport hop), runs an OpenAI tool-calling loop, and streams Server-Sent Events (`token` / `widget` / `done`) over `POST /api/chat`. A new `swiss-grounding-mcp/frontend/` Vite + React + TypeScript SPA renders an Apple-like empty-state composer that collapses into a scrolling thread; each assistant turn shows a short text line plus one widget card per tool call, with a shared `StatusBanner` for every non-success status and a Mapbox route map for resolvable journeys.

**Tech Stack:** Python 3.10+, FastAPI, `openai` Python SDK, `httpx`, `pytest`; Node 22 / npm 10, Vite, React 18, TypeScript, Tailwind CSS 3, `mapbox-gl`, Vitest + `@testing-library/react`.

**Spec:** `docs/superpowers/specs/2026-09-24-swiss-grounding-mcp-frontend-design.md`

## Global Constraints

- Python `>=3.10` (matches `swiss-grounding-mcp/server`'s declared floor).
- `agent-backend` depends on `swiss_grounding_mcp` via a local editable path dependency on `../server`, and never re-implements OJP/AeroDataBox logic.
- `agent-backend` loads OJP/AeroDataBox credentials from `swiss-grounding-mcp/server/.env` (via `Settings.from_env()`); it does not duplicate those values in its own `.env`.
- No fabricated data: every widget renders only fields present in the tool's Pydantic result; anything in a result's `fields_missing` (or otherwise absent) is shown as "not reported by source," never blanked or guessed.
- Every non-`ok`/non-`answered`/non-`success` status (`needs_clarification`, `not_found`, `out_of_scope`, `source_error`, `source_unavailable`, `fallback_link` outside the fares widget) renders `StatusBanner`, never a widget-specific card with invented content.
- No auth, no server-side persistence across reloads, no multi-conversation sidebar, no voice input, no literal rail-track polyline on the map (endpoints + straight connecting line only) — all explicitly deferred per the spec.
- No LangGraph / React Flow code in this plan — future work, deferred per the user's explicit instruction.

## Review Focus

- **`needs_clarification` candidates:** clicking a candidate chip must resend the clarified value as the next user message, not just display it — a user stuck re-typing the whole question is a broken flow. (Task 14)
- **Missing flight fields:** `fields_missing` entries (e.g. `departure.actual`) must render as an explicit "not reported by source" label, not a blank cell that looks like a bug. (Task 12)
- **Mid-stream connection failure:** if the SSE fetch throws or the stream ends without a `done` event, the composer must re-enable and show an error state — not leave the UI stuck "thinking" forever. (Task 10)
- **Unresolvable map locations:** `RouteMap` must degrade to a "map unavailable for this location" message when Mapbox geocoding returns zero results, not throw or render a blank map. (Task 15)
- **Multi-tool-call turns:** a compound request (e.g. `connect_flight_to_train`, which internally represents both a flight and onward trains) must render its widgets in the order the backend emits them, not reordered or batched at the end of the turn. (Tasks 7 and 10)

---

## Task 1: Agent Backend Scaffold and Settings

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/pyproject.toml`
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/__init__.py`
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/settings.py`
- Create: `swiss-grounding-mcp/agent-backend/.env.example`
- Test: `swiss-grounding-mcp/agent-backend/tests/test_settings.py`

**Interfaces:**
- Consumes: `swiss_grounding_mcp.config.settings.Settings.from_env()` (existing, in `../server/src/swiss_grounding_mcp/config/settings.py`).
- Produces: `AgentSettings` dataclass with fields `openai_api_key: str`, `openai_model: str`, `host: str`, `port: int`, `cors_allowed_origin: str`, `mcp_settings: Settings`, and classmethod `AgentSettings.from_env() -> AgentSettings`. Every later backend task imports `AgentSettings` from `agent_backend.settings`.

- [ ] **Step 1: Create the package skeleton and pyproject**

```toml
# swiss-grounding-mcp/agent-backend/pyproject.toml
[project]
name = "swiss-grounding-mcp-agent-backend"
version = "0.1.0"
description = "Chat agent backend wiring OpenAI tool-calling to the Swiss Grounding MCP tools."
requires-python = ">=3.10"
dependencies = [
    "swiss-grounding-mcp @ file:../server",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "openai>=1.40",
    "python-dotenv>=1.0.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_backend"]

[dependency-groups]
dev = ["pytest>=8.0", "httpx>=0.27"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```python
# swiss-grounding-mcp/agent-backend/src/agent_backend/__init__.py
```

```bash
mkdir -p swiss-grounding-mcp/agent-backend/src/agent_backend
mkdir -p swiss-grounding-mcp/agent-backend/tests
```

- [ ] **Step 2: Write the failing test for `AgentSettings.from_env`**

```python
# swiss-grounding-mcp/agent-backend/tests/test_settings.py
from agent_backend.settings import AgentSettings


def test_from_env_reads_agent_specific_vars(monkeypatch, tmp_path):
    # Point at an empty server .env so the test never depends on real
    # OJP/AeroDataBox credentials being present on the machine.
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("AGENT_BACKEND_HOST", "0.0.0.0")
    monkeypatch.setenv("AGENT_BACKEND_PORT", "9090")
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN", "http://localhost:5173")

    settings = AgentSettings.from_env()

    assert settings.openai_api_key == "sk-test"
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.host == "0.0.0.0"
    assert settings.port == 9090
    assert settings.cors_allowed_origin == "http://localhost:5173"
    assert settings.mcp_settings.ojp_api_token == ""


def test_from_env_defaults_model_when_unset(monkeypatch, tmp_path):
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    settings = AgentSettings.from_env()

    assert settings.openai_model == "gpt-4o-mini"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/agent-backend && uv venv && uv pip install -e . --group dev && uv run pytest tests/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_backend.settings'`

- [ ] **Step 4: Implement `AgentSettings`**

```python
# swiss-grounding-mcp/agent-backend/src/agent_backend/settings.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from swiss_grounding_mcp.config.settings import Settings as MCPSettings

_SERVER_ENV_PATH = Path(__file__).resolve().parents[3] / "server" / ".env"


@dataclass(frozen=True)
class AgentSettings:
    openai_api_key: str
    openai_model: str
    host: str
    port: int
    cors_allowed_origin: str
    mcp_settings: MCPSettings

    @classmethod
    def from_env(cls) -> "AgentSettings":
        # Load the MCP server's own .env first so OJP_API_TOKEN and
        # AERODATABOX_API_KEY are available without duplicating them here.
        load_dotenv(_SERVER_ENV_PATH)
        load_dotenv()  # this package's own .env, if present
        return cls(
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            host=os.environ.get("AGENT_BACKEND_HOST", "127.0.0.1"),
            port=int(os.environ.get("AGENT_BACKEND_PORT", "8080")),
            cors_allowed_origin=os.environ.get(
                "CORS_ALLOWED_ORIGIN", "http://localhost:5173"
            ),
            mcp_settings=MCPSettings.from_env(),
        )
```

```bash
# swiss-grounding-mcp/agent-backend/.env.example
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
AGENT_BACKEND_HOST=127.0.0.1
AGENT_BACKEND_PORT=8080
CORS_ALLOWED_ORIGIN=http://localhost:5173
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_settings.py -v`
Expected: PASS (2/2)

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/agent-backend
git commit -m "feat(agent-backend): scaffold project and AgentSettings"
```

---

## Task 2: OJP/AeroDataBox Client Factories

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/clients.py`
- Test: `swiss-grounding-mcp/agent-backend/tests/test_clients.py`

**Interfaces:**
- Consumes: `AgentSettings` (Task 1); `swiss_grounding_mcp.sources.ojp.client.OjpClient`, `swiss_grounding_mcp.sources.aerodatabox.client.AerodataboxClient` (existing).
- Produces: `build_ojp_client(settings: AgentSettings) -> OjpClient`, `build_aviation_client(settings: AgentSettings) -> AerodataboxClient`. Task 8 calls these once at startup.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/agent-backend/tests/test_clients.py
from agent_backend import clients
from agent_backend.settings import AgentSettings
from swiss_grounding_mcp.config.settings import Settings as MCPSettings


def _agent_settings() -> AgentSettings:
    return AgentSettings(
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
        host="127.0.0.1",
        port=8080,
        cors_allowed_origin="http://localhost:5173",
        mcp_settings=MCPSettings(),
    )


def test_build_ojp_client_passes_mcp_settings(monkeypatch):
    captured = {}

    class FakeOjpClient:
        def __init__(self, settings):
            captured["settings"] = settings

    monkeypatch.setattr(clients, "OjpClient", FakeOjpClient)

    settings = _agent_settings()
    client = clients.build_ojp_client(settings)

    assert isinstance(client, FakeOjpClient)
    assert captured["settings"] is settings.mcp_settings


def test_build_aviation_client_passes_mcp_settings(monkeypatch):
    captured = {}

    class FakeAerodataboxClient:
        def __init__(self, settings):
            captured["settings"] = settings

    monkeypatch.setattr(clients, "AerodataboxClient", FakeAerodataboxClient)

    settings = _agent_settings()
    client = clients.build_aviation_client(settings)

    assert isinstance(client, FakeAerodataboxClient)
    assert captured["settings"] is settings.mcp_settings
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_clients.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_backend.clients'`

- [ ] **Step 3: Implement the factories**

```python
# swiss-grounding-mcp/agent-backend/src/agent_backend/clients.py
from __future__ import annotations

from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxClient
from swiss_grounding_mcp.sources.ojp.client import OjpClient

from agent_backend.settings import AgentSettings


def build_ojp_client(settings: AgentSettings) -> OjpClient:
    return OjpClient(settings.mcp_settings)


def build_aviation_client(settings: AgentSettings) -> AerodataboxClient:
    return AerodataboxClient(settings.mcp_settings)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_clients.py -v`
Expected: PASS (2/2)

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/clients.py swiss-grounding-mcp/agent-backend/tests/test_clients.py
git commit -m "feat(agent-backend): add OJP/AeroDataBox client factories"
```

---

## Task 3: OpenAI Tool Schemas

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/tools_registry.py`
- Test: `swiss-grounding-mcp/agent-backend/tests/test_tools_registry.py`

**Interfaces:**
- Produces: `TOOL_SCHEMAS: list[dict]` (OpenAI `tools=` format) and `TOOL_NAMES: frozenset[str]` containing the 8 names below. Task 7 passes `TOOL_SCHEMAS` to the OpenAI SDK; Task 4's dispatch table must accept exactly the names in `TOOL_NAMES`.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/agent-backend/tests/test_tools_registry.py
from agent_backend.tools_registry import TOOL_NAMES, TOOL_SCHEMAS

_EXPECTED_NAMES = {
    "find_connections",
    "find_disruptions",
    "get_station_board",
    "check_public_transport_fares",
    "find_flight_by_number",
    "search_airport_flights",
    "get_airport_guidance",
    "connect_flight_to_train",
}


def test_tool_names_match_expected_set():
    assert TOOL_NAMES == _EXPECTED_NAMES


def test_every_schema_is_well_formed_openai_function_tool():
    assert len(TOOL_SCHEMAS) == len(_EXPECTED_NAMES)
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        function = schema["function"]
        assert function["name"] in _EXPECTED_NAMES
        assert function["description"]
        assert function["parameters"]["type"] == "object"
        assert "properties" in function["parameters"]


def test_find_connections_requires_origin_and_destination():
    schema = next(
        s for s in TOOL_SCHEMAS if s["function"]["name"] == "find_connections"
    )
    assert set(schema["function"]["parameters"]["required"]) == {
        "origin",
        "destination",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tools_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_backend.tools_registry'`

- [ ] **Step 3: Implement the tool schemas**

```python
# swiss-grounding-mcp/agent-backend/src/agent_backend/tools_registry.py
from __future__ import annotations

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "find_connections",
            "description": (
                "Find Swiss passenger-train connections between two stations. "
                "Scope: the current Swiss public-transport timetable only, via "
                "OJP 2.0 (opentransportdata.swiss). Does not cover fares, "
                "single-stop departure boards, disruption feeds, or purely "
                "non-Swiss travel."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Origin station name."},
                    "destination": {"type": "string", "description": "Destination station name."},
                    "departure_time": {"type": "string", "description": "ISO 8601 departure time; defaults to now."},
                    "arrival_time": {"type": "string", "description": "ISO 8601 arrival time; ignored if departure_time is also given."},
                    "results": {"type": "integer", "description": "Number of connections to return (max 5).", "default": 3},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_disruptions",
            "description": (
                "Find current public-transport disruptions affecting a Swiss "
                "station, using real-time OJP 2.0 stop-event information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "stop": {"type": "string", "description": "Station name."},
                },
                "required": ["stop"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_station_board",
            "description": (
                "Show upcoming departures or arrivals at a Swiss "
                "public-transport stop via OJP 2.0. Stations outside "
                "Switzerland are refused as out of scope."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "station": {"type": "string", "description": "Station name."},
                    "mode": {"type": "string", "enum": ["departures", "arrivals"], "default": "departures"},
                    "when": {"type": "string", "description": "ISO 8601 timestamp; defaults to now."},
                    "results": {"type": "integer", "description": "Number of events (max 10).", "default": 5},
                },
                "required": ["station"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_public_transport_fares",
            "description": (
                "Check public-transport fares between two Swiss stations via "
                "the OJP Fare Beta endpoint. If live fare data is unavailable, "
                "returns an SBB booking deep link instead of a guessed price. "
                "International routes are refused rather than guessed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "departure_time": {"type": "string", "description": "ISO 8601; defaults to now."},
                    "travel_class": {"type": "string", "default": "2"},
                    "discount_card": {"type": "string", "description": "e.g. 'Halbtax'."},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_flight_by_number",
            "description": (
                "Look up a flight at Zurich Airport (ZRH) by flight number and "
                "date, via AeroDataBox. Only fields present in the response "
                "are returned; never infers gates, delays, or status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number": {"type": "string", "description": "IATA flight number, e.g. 'LX14'."},
                    "flight_date": {"type": "string", "description": "YYYY-MM-DD."},
                    "direction": {"type": "string", "enum": ["arrival", "departure"]},
                },
                "required": ["flight_number", "flight_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_airport_flights",
            "description": (
                "Search ZRH arrivals or departures for a date via AeroDataBox. "
                "Requires the exact IATA/ICAO code of the other airport; a "
                "city or country name alone is not accepted."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["arrival", "departure"]},
                    "flight_date": {"type": "string", "description": "YYYY-MM-DD."},
                    "airport_iata": {"type": "string"},
                    "airport_icao": {"type": "string"},
                    "airline_iata": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["direction", "flight_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_airport_guidance",
            "description": (
                "Cited Zurich Airport passenger guidance. Topics: "
                "arrival_process, transfers, baggage, airport_rail_access, "
                "flight_status_verification."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": [
                            "arrival_process",
                            "transfers",
                            "baggage",
                            "airport_rail_access",
                            "flight_status_verification",
                        ],
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "connect_flight_to_train",
            "description": (
                "Connect a ZRH arrival to onward Swiss train travel. Provide "
                "either flight_number + flight_date or confirmed_arrival_time. "
                "transfer_buffer_minutes (minimum 15) is required and added to "
                "the arrival time before searching trains."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination_station": {"type": "string"},
                    "transfer_buffer_minutes": {"type": "integer", "minimum": 15},
                    "flight_number": {"type": "string"},
                    "flight_date": {"type": "string", "description": "YYYY-MM-DD."},
                    "confirmed_arrival_time": {"type": "string", "description": "ISO 8601 datetime at ZRH."},
                    "rail_results": {"type": "integer", "default": 3},
                },
                "required": ["destination_station", "transfer_buffer_minutes"],
            },
        },
    },
]

TOOL_NAMES: frozenset[str] = frozenset(schema["function"]["name"] for schema in TOOL_SCHEMAS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tools_registry.py -v`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/tools_registry.py swiss-grounding-mcp/agent-backend/tests/test_tools_registry.py
git commit -m "feat(agent-backend): add OpenAI tool schemas for the 8 MCP tools"
```

---

## Task 4: Tool Dispatch

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/dispatch.py`
- Test: `swiss-grounding-mcp/agent-backend/tests/test_dispatch.py`

**Interfaces:**
- Consumes: `TOOL_NAMES` (Task 3); the 8 existing tool functions from `swiss_grounding_mcp.tools.*` (signatures confirmed by reading their source: `find_train_connections`, `find_station_disruptions`, `get_station_board`, `check_public_transport_fares`, `find_flight_by_number`, `search_airport_flights`, `get_airport_guidance`, `connect_flight_to_train`).
- Produces: `dispatch(tool_name: str, arguments: dict, *, ojp_client, aviation_client, settings) -> BaseModel` and `class UnknownToolError(Exception)`. Task 7's agent loop calls `dispatch` and catches `UnknownToolError`.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/agent-backend/tests/test_dispatch.py
import pytest

from agent_backend import dispatch as dispatch_module
from agent_backend.dispatch import UnknownToolError, dispatch


class _Sentinel:
    """Marker object so tests can assert exact identity was forwarded."""


def test_find_connections_forwards_arguments_and_clients(monkeypatch):
    captured = {}

    def fake_find_train_connections(origin, destination, departure_time, arrival_time, results, *, client, settings):
        captured.update(
            origin=origin, destination=destination, departure_time=departure_time,
            arrival_time=arrival_time, results=results, client=client, settings=settings,
        )
        return "connections-result"

    monkeypatch.setattr(dispatch_module, "find_train_connections", fake_find_train_connections)

    ojp_client, aviation_client, settings = _Sentinel(), _Sentinel(), _Sentinel()
    result = dispatch(
        "find_connections",
        {"origin": "Bern", "destination": "Zürich HB", "results": 2},
        ojp_client=ojp_client, aviation_client=aviation_client, settings=settings,
    )

    assert result == "connections-result"
    assert captured["origin"] == "Bern"
    assert captured["destination"] == "Zürich HB"
    assert captured["departure_time"] is None
    assert captured["arrival_time"] is None
    assert captured["results"] == 2
    assert captured["client"] is ojp_client
    assert captured["settings"] is settings


def test_find_flight_by_number_uses_aviation_client(monkeypatch):
    captured = {}

    def fake_find_flight_by_number(flight_number, flight_date, direction, *, client, settings):
        captured.update(flight_number=flight_number, flight_date=flight_date, direction=direction, client=client)
        return "flight-result"

    monkeypatch.setattr(dispatch_module, "find_flight_by_number", fake_find_flight_by_number)

    aviation_client = _Sentinel()
    result = dispatch(
        "find_flight_by_number",
        {"flight_number": "LX14", "flight_date": "2026-09-25"},
        ojp_client=_Sentinel(), aviation_client=aviation_client, settings=_Sentinel(),
    )

    assert result == "flight-result"
    assert captured["flight_number"] == "LX14"
    assert captured["direction"] is None
    assert captured["client"] is aviation_client


def test_connect_flight_to_train_uses_both_clients(monkeypatch):
    captured = {}

    def fake_connect_flight_to_train(
        flight_number, flight_date, confirmed_arrival_time, destination_station,
        transfer_buffer_minutes, rail_results, *, aviation_client, ojp_client, settings,
    ):
        captured.update(
            destination_station=destination_station,
            transfer_buffer_minutes=transfer_buffer_minutes,
            aviation_client=aviation_client,
            ojp_client=ojp_client,
        )
        return "flight-to-train-result"

    monkeypatch.setattr(dispatch_module, "connect_flight_to_train", fake_connect_flight_to_train)

    ojp_client, aviation_client = _Sentinel(), _Sentinel()
    result = dispatch(
        "connect_flight_to_train",
        {"destination_station": "Luzern", "transfer_buffer_minutes": 45, "flight_number": "LX14", "flight_date": "2026-09-25"},
        ojp_client=ojp_client, aviation_client=aviation_client, settings=_Sentinel(),
    )

    assert result == "flight-to-train-result"
    assert captured["destination_station"] == "Luzern"
    assert captured["transfer_buffer_minutes"] == 45
    assert captured["ojp_client"] is ojp_client
    assert captured["aviation_client"] is aviation_client


def test_unknown_tool_raises():
    with pytest.raises(UnknownToolError):
        dispatch("not_a_real_tool", {}, ojp_client=None, aviation_client=None, settings=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_backend.dispatch'`

- [ ] **Step 3: Implement dispatch**

```python
# swiss-grounding-mcp/agent-backend/src/agent_backend/dispatch.py
from __future__ import annotations

from typing import Any

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.tools.connect_flight_to_train import connect_flight_to_train
from swiss_grounding_mcp.tools.fares import check_public_transport_fares
from swiss_grounding_mcp.tools.find_connections import find_train_connections
from swiss_grounding_mcp.tools.find_disruptions import find_station_disruptions
from swiss_grounding_mcp.tools.find_flight_by_number import find_flight_by_number
from swiss_grounding_mcp.tools.get_airport_guidance import get_airport_guidance
from swiss_grounding_mcp.tools.search_airport_flights import search_airport_flights
from swiss_grounding_mcp.tools.station_timetable import get_station_board


class UnknownToolError(Exception):
    def __init__(self, tool_name: str):
        super().__init__(f"Unknown tool: {tool_name}")
        self.tool_name = tool_name


def dispatch(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    ojp_client,
    aviation_client,
    settings: Settings,
):
    if tool_name == "find_connections":
        return find_train_connections(
            arguments["origin"],
            arguments["destination"],
            arguments.get("departure_time"),
            arguments.get("arrival_time"),
            arguments.get("results", 3),
            client=ojp_client,
            settings=settings,
        )
    if tool_name == "find_disruptions":
        return find_station_disruptions(
            arguments["stop"], client=ojp_client, settings=settings
        )
    if tool_name == "get_station_board":
        return get_station_board(
            arguments["station"],
            arguments.get("mode", "departures"),
            arguments.get("when"),
            arguments.get("results", 5),
            client=ojp_client,
            settings=settings,
        )
    if tool_name == "check_public_transport_fares":
        return check_public_transport_fares(
            arguments["origin"],
            arguments["destination"],
            departure_time=arguments.get("departure_time"),
            travel_class=arguments.get("travel_class", "2"),
            discount_card=arguments.get("discount_card"),
            client=ojp_client,
            settings=settings,
        )
    if tool_name == "find_flight_by_number":
        return find_flight_by_number(
            arguments["flight_number"],
            arguments["flight_date"],
            arguments.get("direction"),
            client=aviation_client,
            settings=settings,
        )
    if tool_name == "search_airport_flights":
        return search_airport_flights(
            arguments["direction"],
            arguments["flight_date"],
            arguments.get("airport_iata"),
            arguments.get("airport_icao"),
            arguments.get("airline_iata"),
            arguments.get("limit", 10),
            client=aviation_client,
            settings=settings,
        )
    if tool_name == "get_airport_guidance":
        return get_airport_guidance(arguments["topic"])
    if tool_name == "connect_flight_to_train":
        return connect_flight_to_train(
            arguments.get("flight_number"),
            arguments.get("flight_date"),
            arguments.get("confirmed_arrival_time"),
            arguments["destination_station"],
            arguments["transfer_buffer_minutes"],
            arguments.get("rail_results", 3),
            aviation_client=aviation_client,
            ojp_client=ojp_client,
            settings=settings,
        )
    raise UnknownToolError(tool_name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/dispatch.py swiss-grounding-mcp/agent-backend/tests/test_dispatch.py
git commit -m "feat(agent-backend): dispatch tool calls to the existing MCP tool functions"
```

---

## Task 5: Widget Mapper

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/widget_mapper.py`
- Test: `swiss-grounding-mcp/agent-backend/tests/test_widget_mapper.py`

**Interfaces:**
- Consumes: `TOOL_NAMES` (Task 3); the domain models in `swiss_grounding_mcp.domain.models` (`ConnectionSearchResult`, `StationBoardResult`, `FareSearchResult`, `DisruptionSearchResult`, `FlightLookupResult`, `FlightSearchResult`, `AirportGuidanceResult`, `FlightToTrainResult`).
- Produces: `WIDGET_TYPES: dict[str, str]` (tool name -> widget type) and `map_result(tool_name: str, result) -> dict` returning `{"widget_type": str, "status": str, "data": dict}`. Task 7 calls `map_result` on every tool's return value; the frontend's `lib/types.ts` (Task 9) mirrors this exact shape.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/agent-backend/tests/test_widget_mapper.py
import pytest
from swiss_grounding_mcp.domain.models import (
    ConnectionSearchResult,
    FareSearchResult,
    FlightLookupResult,
    StopCandidate,
)

from agent_backend.widget_mapper import WIDGET_TYPES, map_result
from agent_backend.dispatch import UnknownToolError


def test_widget_types_cover_all_eight_tools():
    assert set(WIDGET_TYPES) == {
        "find_connections",
        "find_disruptions",
        "get_station_board",
        "check_public_transport_fares",
        "find_flight_by_number",
        "search_airport_flights",
        "get_airport_guidance",
        "connect_flight_to_train",
    }
    assert WIDGET_TYPES["find_connections"] == "train_connections"
    assert WIDGET_TYPES["check_public_transport_fares"] == "fares"
    assert WIDGET_TYPES["find_flight_by_number"] == "flight"
    assert WIDGET_TYPES["connect_flight_to_train"] == "flight_to_train"


def test_map_result_ok_connections():
    result = ConnectionSearchResult(status="ok", connections=[])
    mapped = map_result("find_connections", result)

    assert mapped["widget_type"] == "train_connections"
    assert mapped["status"] == "ok"
    assert mapped["data"]["connections"] == []


def test_map_result_needs_clarification_with_candidates():
    result = ConnectionSearchResult(
        status="needs_clarification",
        message="Which Fribourg?",
        candidates=[StopCandidate(name="Fribourg/Freiburg", stop_ref="8504100")],
    )
    mapped = map_result("find_connections", result)

    assert mapped["status"] == "needs_clarification"
    assert mapped["data"]["candidates"][0]["name"] == "Fribourg/Freiburg"


def test_map_result_fares_fallback_link():
    result = FareSearchResult(status="fallback_link", booking_url="https://sbb.ch/x")
    mapped = map_result("check_public_transport_fares", result)

    assert mapped["widget_type"] == "fares"
    assert mapped["status"] == "fallback_link"
    assert mapped["data"]["booking_url"] == "https://sbb.ch/x"


def test_map_result_flight_source_unavailable():
    result = FlightLookupResult(status="source_unavailable", message="quota exceeded")
    mapped = map_result("find_flight_by_number", result)

    assert mapped["widget_type"] == "flight"
    assert mapped["status"] == "source_unavailable"
    assert mapped["data"]["flight"] is None


def test_map_result_unknown_tool_raises():
    with pytest.raises(UnknownToolError):
        map_result("not_a_real_tool", ConnectionSearchResult(status="ok"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_widget_mapper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_backend.widget_mapper'`

- [ ] **Step 3: Implement the mapper**

```python
# swiss-grounding-mcp/agent-backend/src/agent_backend/widget_mapper.py
from __future__ import annotations

from pydantic import BaseModel

from agent_backend.dispatch import UnknownToolError

WIDGET_TYPES: dict[str, str] = {
    "find_connections": "train_connections",
    "find_disruptions": "disruptions",
    "get_station_board": "station_board",
    "check_public_transport_fares": "fares",
    "find_flight_by_number": "flight",
    "search_airport_flights": "flight_search",
    "get_airport_guidance": "airport_guidance",
    "connect_flight_to_train": "flight_to_train",
}


def map_result(tool_name: str, result: BaseModel) -> dict:
    widget_type = WIDGET_TYPES.get(tool_name)
    if widget_type is None:
        raise UnknownToolError(tool_name)
    return {
        "widget_type": widget_type,
        "status": result.status,
        "data": result.model_dump(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_widget_mapper.py -v`
Expected: PASS (6/6)

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/widget_mapper.py swiss-grounding-mcp/agent-backend/tests/test_widget_mapper.py
git commit -m "feat(agent-backend): map tool results to frontend widget events"
```

---

## Task 6: SSE Frame Formatting

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/sse.py`
- Test: `swiss-grounding-mcp/agent-backend/tests/test_sse.py`

**Interfaces:**
- Produces: `format_sse(event: dict) -> str`, returning a single `text/event-stream` frame (`"data: <json>\n\n"`). Task 8's `/api/chat` endpoint calls this for every event yielded by Task 7's `run_chat`.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/agent-backend/tests/test_sse.py
import json

from agent_backend.sse import format_sse


def test_format_sse_wraps_json_payload_in_data_frame():
    frame = format_sse({"type": "token", "text": "hi"})

    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    payload = json.loads(frame[len("data: "):].strip())
    assert payload == {"type": "token", "text": "hi"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_backend.sse'`

- [ ] **Step 3: Implement**

```python
# swiss-grounding-mcp/agent-backend/src/agent_backend/sse.py
from __future__ import annotations

import json


def format_sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sse.py -v`
Expected: PASS (1/1)

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/sse.py swiss-grounding-mcp/agent-backend/tests/test_sse.py
git commit -m "feat(agent-backend): add SSE frame formatting"
```

---

## Task 7: Agent Tool-Calling Loop

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/agent_loop.py`
- Test: `swiss-grounding-mcp/agent-backend/tests/test_agent_loop.py`

**Interfaces:**
- Consumes: `TOOL_SCHEMAS` (Task 3), `dispatch`/`UnknownToolError` (Task 4), `map_result` (Task 5).
- Produces: `run_chat(messages: list[dict], *, openai_client, ojp_client, aviation_client, settings, model: str) -> Iterator[dict]`, yielding `{"type": "token", "text": str}`, `{"type": "widget", "tool": str | None, "status": str, "data": dict}`, and finally `{"type": "done"}`. Task 8's `/api/chat` endpoint consumes this generator.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/agent-backend/tests/test_agent_loop.py
from types import SimpleNamespace

from swiss_grounding_mcp.domain.models import ConnectionSearchResult

from agent_backend import agent_loop
from agent_backend.agent_loop import run_chat


def _tool_call(call_id, name, arguments_json):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments_json),
    )


class _FakeOpenAI:
    """Returns one canned response per call, in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        self.calls = []

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _text_response(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=[]))]
    )


def _tool_call_response(tool_calls):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=tool_calls))]
    )


def test_plain_text_reply_emits_token_then_done():
    fake_openai = _FakeOpenAI([_text_response("Hello there.")])

    events = list(run_chat(
        [{"role": "user", "content": "hi"}],
        openai_client=fake_openai, ojp_client=None, aviation_client=None,
        settings=None, model="gpt-4o-mini",
    ))

    assert events == [
        {"type": "token", "text": "Hello there."},
        {"type": "done"},
    ]


def test_single_tool_call_emits_widget_before_final_text(monkeypatch):
    def fake_dispatch(tool_name, arguments, *, ojp_client, aviation_client, settings):
        assert tool_name == "find_connections"
        assert arguments == {"origin": "Bern", "destination": "Zürich HB"}
        return ConnectionSearchResult(status="ok", connections=[])

    monkeypatch.setattr(agent_loop, "dispatch", fake_dispatch)

    fake_openai = _FakeOpenAI([
        _tool_call_response([_tool_call("call_1", "find_connections", '{"origin": "Bern", "destination": "Zürich HB"}')]),
        _text_response("Here are your options."),
    ])

    events = list(run_chat(
        [{"role": "user", "content": "trains from Bern to Zürich"}],
        openai_client=fake_openai, ojp_client="ojp", aviation_client="aviation",
        settings="settings", model="gpt-4o-mini",
    ))

    assert events[0] == {"type": "widget", "tool": "find_connections", "status": "ok", "data": {"widget_type": "train_connections", "status": "ok", "data": events[0]["data"]["data"]}}["type"] and False or True
    widget_events = [event for event in events if event["type"] == "widget"]
    assert len(widget_events) == 1
    assert widget_events[0]["tool"] == "find_connections"
    assert widget_events[0]["status"] == "ok"
    assert events[-2] == {"type": "token", "text": "Here are your options."}
    assert events[-1] == {"type": "done"}
    # the widget must appear before the follow-up text (ordering matters for the UI)
    assert events.index(widget_events[0]) < len(events) - 2


def test_openai_failure_emits_source_error_widget_and_done():
    class _FailingOpenAI:
        chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=SimpleNamespace(
                    __call__=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
                )
            )
        )

    events = list(run_chat(
        [{"role": "user", "content": "hi"}],
        openai_client=_FailingOpenAI(), ojp_client=None, aviation_client=None,
        settings=None, model="gpt-4o-mini",
    ))

    assert events[0]["type"] == "widget"
    assert events[0]["status"] == "source_error"
    assert events[-1] == {"type": "done"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agent_loop.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_backend.agent_loop'`

- [ ] **Step 3: Implement the loop**

```python
# swiss-grounding-mcp/agent-backend/src/agent_backend/agent_loop.py
from __future__ import annotations

import json
from collections.abc import Iterator

from agent_backend.dispatch import UnknownToolError, dispatch
from agent_backend.tools_registry import TOOL_SCHEMAS
from agent_backend.widget_mapper import map_result

_SYSTEM_PROMPT = (
    "You are the Swiss Grounding travel assistant. Use the provided tools "
    "for any question about Swiss train connections, station boards, "
    "fares, disruptions, or Zurich Airport (ZRH) flights. Never answer a "
    "travel question from memory; always call the matching tool. For "
    "anything outside these topics, say honestly that it is not covered. "
    "Keep your own reply to one short sentence: the tool result is shown "
    "to the user as a visual card, so do not restate its details."
)

_MAX_TOOL_ROUNDS = 4


def run_chat(
    messages: list[dict],
    *,
    openai_client,
    ojp_client,
    aviation_client,
    settings,
    model: str,
) -> Iterator[dict]:
    chat_messages = [{"role": "system", "content": _SYSTEM_PROMPT}, *messages]

    for _ in range(_MAX_TOOL_ROUNDS):
        try:
            response = openai_client.chat.completions.create(
                model=model,
                messages=chat_messages,
                tools=TOOL_SCHEMAS,
            )
        except Exception as exc:  # SDK network/auth/rate-limit failure
            yield {
                "type": "widget",
                "tool": None,
                "status": "source_error",
                "data": {"message": f"The assistant service is unavailable: {exc}"},
            }
            yield {"type": "done"}
            return

        choice_message = response.choices[0].message
        tool_calls = list(choice_message.tool_calls or [])

        if choice_message.content:
            yield {"type": "token", "text": choice_message.content}

        if not tool_calls:
            yield {"type": "done"}
            return

        chat_messages.append(
            {
                "role": "assistant",
                "content": choice_message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.function.name, "arguments": call.function.arguments},
                    }
                    for call in tool_calls
                ],
            }
        )

        for tool_call in tool_calls:
            name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}

            try:
                result = dispatch(
                    name,
                    arguments,
                    ojp_client=ojp_client,
                    aviation_client=aviation_client,
                    settings=settings,
                )
                mapped = map_result(name, result)
            except UnknownToolError:
                mapped = {
                    "widget_type": None,
                    "status": "source_error",
                    "data": {"message": f"Unknown tool requested: {name}"},
                }
            except Exception as exc:
                mapped = {
                    "widget_type": None,
                    "status": "source_error",
                    "data": {"message": f"{name} failed: {exc}"},
                }

            yield {
                "type": "widget",
                "tool": name,
                "status": mapped["status"],
                "data": mapped["data"],
            }

            chat_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(mapped["data"]),
                }
            )

    yield {"type": "token", "text": "I've reached the maximum number of steps for this request."}
    yield {"type": "done"}
```

- [ ] **Step 4: Simplify the flaky assertion in the test and run**

The first assertion line in `test_single_tool_call_emits_widget_before_final_text` above is deliberately convoluted scaffolding from drafting — replace it with a direct check before running:

```python
# Replace this line in test_agent_loop.py:
#   assert events[0] == {...}["type"] == "widget" ... or True
# with:
    assert events[0]["type"] == "widget"
```

Run: `uv run pytest tests/test_agent_loop.py -v`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/agent_loop.py swiss-grounding-mcp/agent-backend/tests/test_agent_loop.py
git commit -m "feat(agent-backend): implement OpenAI tool-calling loop with SSE events"
```

---

## Task 8: FastAPI App and `/api/chat` Endpoint

**Files:**
- Create: `swiss-grounding-mcp/agent-backend/src/agent_backend/main.py`
- Create: `swiss-grounding-mcp/agent-backend/README.md`
- Test: `swiss-grounding-mcp/agent-backend/tests/test_main.py`

**Interfaces:**
- Consumes: `AgentSettings` (Task 1), `build_ojp_client`/`build_aviation_client` (Task 2), `run_chat` (Task 7), `format_sse` (Task 6).
- Produces: `app: FastAPI` importable as `agent_backend.main:app`, exposing `GET /api/health` and `POST /api/chat`. The frontend (Task 9+) targets these two routes.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/agent-backend/tests/test_main.py
from fastapi.testclient import TestClient

from agent_backend import main as main_module


def test_health_endpoint_returns_ok():
    client = TestClient(main_module.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_streams_events_from_run_chat(monkeypatch):
    def fake_run_chat(messages, **kwargs):
        assert messages == [{"role": "user", "content": "hi"}]
        yield {"type": "token", "text": "hello"}
        yield {"type": "done"}

    monkeypatch.setattr(main_module, "run_chat", fake_run_chat)

    client = TestClient(main_module.app)
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"type": "token", "text": "hello"}' in response.text
    assert 'data: {"type": "done"}' in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_backend.main'`

- [ ] **Step 3: Implement the FastAPI app**

```python
# swiss-grounding-mcp/agent-backend/src/agent_backend/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from agent_backend.agent_loop import run_chat
from agent_backend.clients import build_aviation_client, build_ojp_client
from agent_backend.settings import AgentSettings
from agent_backend.sse import format_sse

settings = AgentSettings.from_env()
app = FastAPI(title="Swiss Grounding MCP Agent Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_allowed_origin],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

_openai_client = OpenAI(api_key=settings.openai_api_key)
_ojp_client = build_ojp_client(settings)
_aviation_client = build_aviation_client(settings)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    def event_stream():
        messages = [message.model_dump() for message in request.messages]
        for event in run_chat(
            messages,
            openai_client=_openai_client,
            ojp_client=_ojp_client,
            aviation_client=_aviation_client,
            settings=settings.mcp_settings,
            model=settings.openai_model,
        ):
            yield format_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

```markdown
<!-- swiss-grounding-mcp/agent-backend/README.md -->
# Swiss Grounding MCP — Agent Backend

FastAPI service that wires OpenAI tool-calling to the Swiss Grounding
MCP tool functions (imported directly from `../server`, no MCP
transport hop) and streams the results to the chat frontend as
Server-Sent Events.

## Setup

```bash
cd swiss-grounding-mcp/agent-backend
uv venv
uv pip install -e . --group dev
cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

The OJP and AeroDataBox credentials are read from
`swiss-grounding-mcp/server/.env` — configure them there per that
project's README, not here.

## Running

```bash
uv run uvicorn agent_backend.main:app --reload --port 8080
```

## Endpoints

- `GET /api/health` — liveness check.
- `POST /api/chat` — `{"messages": [{"role": "user", "content": "..."}]}`,
  returns a `text/event-stream` of `{"type": "token"|"widget"|"done", ...}`
  events. See the design spec at
  `docs/superpowers/specs/2026-09-24-swiss-grounding-mcp-frontend-design.md`
  for the full event/widget schema.

## Running the checks

```bash
uv run pytest -v
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS (2/2). Note: this test only runs correctly once `.env` has been copied per the README, since `AgentSettings.from_env()` runs at import time; an empty/missing `OPENAI_API_KEY` is fine for this test (the OpenAI client is never actually called because `run_chat` is monkeypatched).

- [ ] **Step 5: Run the full backend suite**

Run: `uv run pytest -v`
Expected: PASS (all tests from Tasks 1-8)

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/agent-backend/src/agent_backend/main.py swiss-grounding-mcp/agent-backend/README.md swiss-grounding-mcp/agent-backend/tests/test_main.py
git commit -m "feat(agent-backend): add FastAPI app with /api/chat SSE endpoint"
```

---

## Task 9: Frontend Scaffold, Design Tokens, and Shared Types

**Files:**
- Create: `swiss-grounding-mcp/frontend/` (Vite scaffold: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/main.tsx`)
- Create: `swiss-grounding-mcp/frontend/tailwind.config.js`, `swiss-grounding-mcp/frontend/postcss.config.js`, `swiss-grounding-mcp/frontend/src/styles/index.css`
- Create: `swiss-grounding-mcp/frontend/src/lib/types.ts`
- Create: `swiss-grounding-mcp/frontend/src/lib/sse.ts`
- Create: `swiss-grounding-mcp/frontend/.env.example`
- Test: `swiss-grounding-mcp/frontend/src/lib/sse.test.ts`

**Interfaces:**
- Produces: TypeScript types `ChatMessage`, `WidgetEvent`, `TokenEvent`, `DoneEvent`, `AgentEvent` (exported from `lib/types.ts`), and `streamChat(backendUrl: string, messages: ChatMessage[]): AsyncGenerator<AgentEvent>` (exported from `lib/sse.ts`). Every later frontend task imports these types; `streamChat`'s event shapes must match Task 7/8's backend output exactly (`{type: "token", text}`, `{type: "widget", tool, status, data}`, `{type: "done"}`).

- [ ] **Step 1: Scaffold the Vite project**

```bash
cd swiss-grounding-mcp
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss@^3 postcss autoprefixer vitest @testing-library/react @testing-library/jest-dom jsdom
npm install mapbox-gl
npx tailwindcss init -p
```

- [ ] **Step 2: Configure Tailwind and base styles**

```js
// swiss-grounding-mcp/frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: "#0A84FF",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Inter", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
```

```css
/* swiss-grounding-mcp/frontend/src/styles/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  @apply bg-neutral-50 text-neutral-900 font-sans antialiased;
}
```

```ts
// swiss-grounding-mcp/frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Configure Vitest in `vite.config.ts`:

```ts
// swiss-grounding-mcp/frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
  },
});
```

Add to `package.json` `"scripts"`: `"test": "vitest run"`.

```bash
# swiss-grounding-mcp/frontend/.env.example
VITE_AGENT_BACKEND_URL=http://127.0.0.1:8080
VITE_MAPBOX_TOKEN=
```

- [ ] **Step 3: Write shared types**

```ts
// swiss-grounding-mcp/frontend/src/lib/types.ts
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface TokenEvent {
  type: "token";
  text: string;
}

export interface WidgetEvent {
  type: "widget";
  tool: string | null;
  status: string;
  data: Record<string, unknown>;
}

export interface DoneEvent {
  type: "done";
}

export type AgentEvent = TokenEvent | WidgetEvent | DoneEvent;
```

- [ ] **Step 4: Write the failing test for the SSE parser**

```ts
// swiss-grounding-mcp/frontend/src/lib/sse.test.ts
import { describe, expect, it, vi, afterEach } from "vitest";
import { streamChat } from "./sse";
import type { ChatMessage } from "./types";

function fakeStreamResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("streamChat", () => {
  it("yields parsed events in order across chunk boundaries", async () => {
    const frames = [
      'data: {"type": "token", "text": "hi"}\n\n',
      'data: {"type": "widget", "tool": "find_connections", "status": "ok", "data": {}}\n\n',
      'data: {"type": "done"}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeStreamResponse(frames)));

    const messages: ChatMessage[] = [{ role: "user", content: "hi" }];
    const events = [];
    for await (const event of streamChat("http://backend", messages)) {
      events.push(event);
    }

    expect(events).toEqual([
      { type: "token", text: "hi" },
      { type: "widget", tool: "find_connections", status: "ok", data: {} },
      { type: "done" },
    ]);
  });

  it("throws when the backend responds with a non-OK status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 500 }))
    );

    const generator = streamChat("http://backend", [{ role: "user", content: "hi" }]);

    await expect(generator.next()).rejects.toThrow("Agent backend responded with 500");
  });
});
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd swiss-grounding-mcp/frontend && npm run test`
Expected: FAIL — `Cannot find module './sse'`

- [ ] **Step 6: Implement the SSE parser**

```ts
// swiss-grounding-mcp/frontend/src/lib/sse.ts
import type { AgentEvent, ChatMessage } from "./types";

export async function* streamChat(
  backendUrl: string,
  messages: ChatMessage[]
): AsyncGenerator<AgentEvent> {
  const response = await fetch(`${backendUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Agent backend responded with ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice("data:".length).trim();
      if (!payload) continue;
      yield JSON.parse(payload) as AgentEvent;
    }
  }
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `npm run test`
Expected: PASS (2/2)

- [ ] **Step 8: Commit**

```bash
git add swiss-grounding-mcp/frontend
git commit -m "feat(frontend): scaffold Vite/React/Tailwind app with SSE client"
```

---

## Task 10: App Shell — Hero, Composer, and Turn Streaming

**Files:**
- Create: `swiss-grounding-mcp/frontend/src/components/Composer.tsx`
- Create: `swiss-grounding-mcp/frontend/src/components/ChatThread.tsx`
- Create: `swiss-grounding-mcp/frontend/src/components/AssistantTurn.tsx`
- Modify: `swiss-grounding-mcp/frontend/src/App.tsx`
- Test: `swiss-grounding-mcp/frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `streamChat` (Task 9), `AgentEvent`/`ChatMessage`/`WidgetEvent` (Task 9).
- Produces: `interface Turn { id: string; role: "user" | "assistant"; text: string; widgets: WidgetEvent[] }` (defined in `App.tsx`, exported for Task 14's tests) and `<AssistantTurn turn={Turn} onClarify={(value: string) => void} />`. Task 14 replaces `AssistantTurn`'s interim raw-JSON widget rendering with real widget components via a registry, without changing this props interface.

- [ ] **Step 1: Write the failing test**

```tsx
// swiss-grounding-mcp/frontend/src/App.test.tsx
import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./App";

function fakeStreamResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame));
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("shows the empty-state hero before any message is sent", () => {
    render(<App />);
    expect(screen.getByPlaceholderText(/ask about your journey/i)).toBeInTheDocument();
  });

  it("collapses the hero and renders the streamed reply after submitting", async () => {
    const frames = [
      'data: {"type": "token", "text": "Here is what I found."}\n\n',
      'data: {"type": "widget", "tool": "find_connections", "status": "ok", "data": {"connections": []}}\n\n',
      'data: {"type": "done"}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeStreamResponse(frames)));

    render(<App />);
    const input = screen.getByPlaceholderText(/ask about your journey/i);
    fireEvent.change(input, { target: { value: "Trains from Bern to Zürich" } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByText("Trains from Bern to Zürich")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("Here is what I found.")).toBeInTheDocument()
    );
    expect(screen.getByTestId("widget-find_connections")).toBeInTheDocument();
  });

  it("re-enables the composer and shows an error turn when the stream fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 500 })));

    render(<App />);
    const input = screen.getByPlaceholderText(/ask about your journey/i);
    fireEvent.change(input, { target: { value: "hi" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() =>
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    );
    expect(input).not.toBeDisabled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test`
Expected: FAIL — placeholder text / submit behavior not implemented in the default Vite template's `App.tsx`.

- [ ] **Step 3: Implement `Composer`, `AssistantTurn`, `ChatThread`, and wire `App`**

```tsx
// swiss-grounding-mcp/frontend/src/components/Composer.tsx
import { FormEvent, useState } from "react";

interface ComposerProps {
  disabled: boolean;
  onSubmit: (text: string) => void;
}

export function Composer({ disabled, onSubmit }: ComposerProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl">
      <div className="flex items-center gap-3 rounded-full border border-neutral-200 bg-white px-5 py-3 shadow-sm">
        <input
          className="flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400 disabled:opacity-50"
          placeholder="Ask about your journey"
          value={value}
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </form>
  );
}
```

```tsx
// swiss-grounding-mcp/frontend/src/components/AssistantTurn.tsx
import type { Turn } from "../App";

interface AssistantTurnProps {
  turn: Turn;
  onClarify: (value: string) => void;
}

export function AssistantTurn({ turn }: AssistantTurnProps) {
  return (
    <div className="space-y-3">
      {turn.text && <p className="text-neutral-700">{turn.text}</p>}
      {turn.widgets.map((widget, index) => (
        <div
          key={index}
          data-testid={`widget-${widget.tool ?? "unknown"}`}
          className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm"
        >
          <pre className="whitespace-pre-wrap text-xs text-neutral-500">
            {JSON.stringify(widget, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}
```

```tsx
// swiss-grounding-mcp/frontend/src/components/ChatThread.tsx
import type { Turn } from "../App";
import { AssistantTurn } from "./AssistantTurn";

interface ChatThreadProps {
  turns: Turn[];
  onClarify: (value: string) => void;
}

export function ChatThread({ turns, onClarify }: ChatThreadProps) {
  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 py-8">
      {turns.map((turn) =>
        turn.role === "user" ? (
          <p key={turn.id} className="ml-auto w-fit rounded-2xl bg-accent px-4 py-2 text-white">
            {turn.text}
          </p>
        ) : (
          <AssistantTurn key={turn.id} turn={turn} onClarify={onClarify} />
        )
      )}
    </div>
  );
}
```

```tsx
// swiss-grounding-mcp/frontend/src/App.tsx
import { useState } from "react";
import { Composer } from "./components/Composer";
import { ChatThread } from "./components/ChatThread";
import { streamChat } from "./lib/sse";
import type { ChatMessage, WidgetEvent } from "./lib/types";

export interface Turn {
  id: string;
  role: "user" | "assistant";
  text: string;
  widgets: WidgetEvent[];
}

const BACKEND_URL = import.meta.env.VITE_AGENT_BACKEND_URL ?? "http://127.0.0.1:8080";

function makeId(): string {
  return Math.random().toString(36).slice(2);
}

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);

  async function handleSubmit(text: string) {
    const userTurn: Turn = { id: makeId(), role: "user", text, widgets: [] };
    const assistantTurn: Turn = { id: makeId(), role: "assistant", text: "", widgets: [] };
    const nextHistory: ChatMessage[] = [...history, { role: "user", content: text }];

    setTurns((current) => [...current, userTurn, assistantTurn]);
    setHistory(nextHistory);
    setPending(true);

    let assistantText = "";
    try {
      for await (const event of streamChat(BACKEND_URL, nextHistory)) {
        if (event.type === "token") {
          assistantText += event.text;
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantTurn.id ? { ...turn, text: assistantText } : turn
            )
          );
        } else if (event.type === "widget") {
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantTurn.id
                ? { ...turn, widgets: [...turn.widgets, event] }
                : turn
            )
          );
        }
      }
      setHistory((current) => [...current, { role: "assistant", content: assistantText }]);
    } catch (error) {
      setTurns((current) =>
        current.map((turn) =>
          turn.id === assistantTurn.id
            ? { ...turn, text: "Something went wrong reaching the assistant. Please try again." }
            : turn
        )
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center">
      {turns.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-8">
          <h1 className="text-3xl font-medium text-neutral-800">Where are you headed?</h1>
          <Composer disabled={pending} onSubmit={handleSubmit} />
        </div>
      ) : (
        <>
          <ChatThread turns={turns} onClarify={handleSubmit} />
          <div className="sticky bottom-0 w-full bg-gradient-to-t from-neutral-50 py-6">
            <div className="flex justify-center">
              <Composer disabled={pending} onSubmit={handleSubmit} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test`
Expected: PASS (3/3 in `App.test.tsx`, plus the existing `sse.test.ts` suite)

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/frontend/src
git commit -m "feat(frontend): hero-to-thread chat shell with streaming turns"
```

---

## Task 11: List-Style Widgets — Train Connections, Station Board, Disruptions

**Files:**
- Create: `swiss-grounding-mcp/frontend/src/components/widgets/TrainConnectionsCard.tsx`
- Create: `swiss-grounding-mcp/frontend/src/components/widgets/StationBoardCard.tsx`
- Create: `swiss-grounding-mcp/frontend/src/components/widgets/DisruptionsCard.tsx`
- Test: `swiss-grounding-mcp/frontend/src/components/widgets/TrainConnectionsCard.test.tsx`
- Test: `swiss-grounding-mcp/frontend/src/components/widgets/StationBoardCard.test.tsx`
- Test: `swiss-grounding-mcp/frontend/src/components/widgets/DisruptionsCard.test.tsx`

**Interfaces:**
- Produces: `<TrainConnectionsCard data={ConnectionSearchData} onSelect={(connection) => void} />`, `<StationBoardCard data={StationBoardData} />`, `<DisruptionsCard data={DisruptionSearchData} />`, each a plain React function component taking only its tool's `data` object (mirroring the backend's `ConnectionSearchResult`/`StationBoardResult`/`DisruptionSearchResult` shapes from `swiss_grounding_mcp.domain.models`). Task 14's widget registry imports all three by name.

- [ ] **Step 1: Write the failing tests**

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/TrainConnectionsCard.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TrainConnectionsCard } from "./TrainConnectionsCard";

const sampleData = {
  connections: [
    {
      departure: "2026-09-24T18:04:00Z",
      arrival: "2026-09-24T19:47:00Z",
      duration_minutes: 103,
      changes: 1,
      legs: [
        { mode: "rail", line: "IC 8", from_name: "Bern", to_name: "Zürich HB", departure: "2026-09-24T18:04:00Z", arrival: "2026-09-24T18:57:00Z" },
      ],
    },
  ],
  provenance: { source: "opentransportdata.swiss OJP 2.0", source_url: "https://opentransportdata.swiss", retrieved_at: "2026-09-24T18:03:12Z" },
};

describe("TrainConnectionsCard", () => {
  it("renders one selectable option per connection with its citation", () => {
    render(<TrainConnectionsCard data={sampleData} onSelect={() => {}} />);

    expect(screen.getByText(/103 min/)).toBeInTheDocument();
    expect(screen.getByText(/1 change/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /opentransportdata.swiss/i })).toHaveAttribute(
      "href",
      "https://opentransportdata.swiss"
    );
  });

  it("calls onSelect with the chosen connection", () => {
    const onSelect = vi.fn();
    render(<TrainConnectionsCard data={sampleData} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: /103 min/ }));

    expect(onSelect).toHaveBeenCalledWith(sampleData.connections[0]);
  });
});
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/StationBoardCard.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StationBoardCard } from "./StationBoardCard";

describe("StationBoardCard", () => {
  it("renders the station name and each event's line, direction, and time", () => {
    render(
      <StationBoardCard
        data={{
          station_name: "Bern",
          event_type: "departure",
          events: [
            { line: "IC 8", mode: "rail", direction_name: "Zürich HB", planned_time: "2026-09-24T18:04:00Z", estimated_time: null, platform: "3", delay_minutes: null },
          ],
        }}
      />
    );

    expect(screen.getByText("Bern")).toBeInTheDocument();
    expect(screen.getByText("IC 8")).toBeInTheDocument();
    expect(screen.getByText(/Zürich HB/)).toBeInTheDocument();
    expect(screen.getByText(/Platform 3/)).toBeInTheDocument();
  });
});
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/DisruptionsCard.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DisruptionsCard } from "./DisruptionsCard";

describe("DisruptionsCard", () => {
  it("renders each disruption's title, severity, and affected lines", () => {
    render(
      <DisruptionsCard
        data={{
          disruptions: [
            {
              id: "1",
              title: "Track work",
              description: "Reduced service between Bern and Thun.",
              severity: "moderate",
              start_time: "2026-09-24T06:00:00Z",
              end_time: "2026-09-24T20:00:00Z",
              status: "active",
              affected_lines: ["S1"],
              affected_stops: ["Bern"],
            },
          ],
        }}
      />
    );

    expect(screen.getByText("Track work")).toBeInTheDocument();
    expect(screen.getByText(/moderate/i)).toBeInTheDocument();
    expect(screen.getByText("S1")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test`
Expected: FAIL — the three widget modules don't exist yet.

- [ ] **Step 3: Implement the three cards**

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/TrainConnectionsCard.tsx
interface Leg {
  mode: string;
  line: string | null;
  from_name: string;
  to_name: string;
  departure: string | null;
  arrival: string | null;
}

interface Connection {
  departure: string;
  arrival: string;
  duration_minutes: number;
  changes: number;
  legs: Leg[];
}

interface Provenance {
  source: string;
  source_url: string;
  retrieved_at: string;
}

export interface ConnectionSearchData {
  connections: Connection[];
  provenance?: Provenance | null;
}

interface TrainConnectionsCardProps {
  data: ConnectionSearchData;
  onSelect: (connection: Connection) => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function TrainConnectionsCard({ data, onSelect }: TrainConnectionsCardProps) {
  return (
    <div className="space-y-2">
      {data.connections.map((connection, index) => (
        <button
          key={index}
          type="button"
          onClick={() => onSelect(connection)}
          className="w-full rounded-xl border border-neutral-200 p-3 text-left hover:border-accent"
        >
          <div className="flex items-center justify-between text-sm font-medium">
            <span>{formatTime(connection.departure)} → {formatTime(connection.arrival)}</span>
            <span>{connection.duration_minutes} min</span>
          </div>
          <div className="text-xs text-neutral-500">
            {connection.changes === 0 ? "Direct" : `${connection.changes} change${connection.changes > 1 ? "s" : ""}`}
          </div>
        </button>
      ))}
      {data.provenance && (
        <a
          href={data.provenance.source_url}
          target="_blank"
          rel="noreferrer"
          className="block text-xs text-neutral-400 hover:underline"
        >
          Source: {data.provenance.source}
        </a>
      )}
    </div>
  );
}
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/StationBoardCard.tsx
interface StopEvent {
  line: string | null;
  mode: string | null;
  direction_name: string | null;
  planned_time: string | null;
  estimated_time: string | null;
  platform: string | null;
  delay_minutes: number | null;
}

export interface StationBoardData {
  station_name: string | null;
  event_type: string | null;
  events: StopEvent[];
}

export function StationBoardCard({ data }: { data: StationBoardData }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{data.station_name}</h3>
      <ul className="space-y-1">
        {data.events.map((event, index) => (
          <li key={index} className="flex items-center justify-between text-sm">
            <span className="font-medium">{event.line ?? "—"}</span>
            <span className="text-neutral-500">to {event.direction_name ?? "not reported by source"}</span>
            <span>{event.planned_time ? new Date(event.planned_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "not reported by source"}</span>
            <span className="text-xs text-neutral-400">{event.platform ? `Platform ${event.platform}` : "not reported by source"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/DisruptionsCard.tsx
interface Disruption {
  id: string;
  title: string | null;
  description: string | null;
  severity: string | null;
  start_time: string | null;
  end_time: string | null;
  status: string | null;
  affected_lines: string[];
  affected_stops: string[];
}

export interface DisruptionSearchData {
  disruptions: Disruption[];
}

export function DisruptionsCard({ data }: { data: DisruptionSearchData }) {
  return (
    <ul className="space-y-2">
      {data.disruptions.map((disruption) => (
        <li key={disruption.id} className="rounded-xl border border-amber-200 bg-amber-50 p-3">
          <div className="flex items-center justify-between">
            <span className="font-medium">{disruption.title ?? "Disruption"}</span>
            <span className="text-xs uppercase text-amber-700">{disruption.severity ?? "not reported by source"}</span>
          </div>
          {disruption.description && <p className="text-sm text-neutral-600">{disruption.description}</p>}
          {disruption.affected_lines.length > 0 && (
            <p className="text-xs text-neutral-500">{disruption.affected_lines.join(", ")}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test`
Expected: PASS (all previous suites + 4 new tests across the three widget files)

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/frontend/src/components/widgets
git commit -m "feat(frontend): train connections, station board, and disruptions widgets"
```

---

## Task 12: Fares and Flight Widgets

**Files:**
- Create: `swiss-grounding-mcp/frontend/src/components/widgets/FaresCard.tsx`
- Create: `swiss-grounding-mcp/frontend/src/components/widgets/FlightCard.tsx`
- Test: `swiss-grounding-mcp/frontend/src/components/widgets/FaresCard.test.tsx`
- Test: `swiss-grounding-mcp/frontend/src/components/widgets/FlightCard.test.tsx`

**Interfaces:**
- Produces: `<FaresCard data={FareSearchData} />` (renders `fares[]` when present, otherwise a `booking_url` deep-link button) and `<FlightCard data={FlightSearchData} onSelect={(flight) => void} />` (accepts either a single `flight` object or a `flights[]` array — used for both `find_flight_by_number` and `search_airport_flights`). Task 14's registry maps `widget_type: "flight"` and `"flight_search"` both to `FlightCard`.

- [ ] **Step 1: Write the failing tests**

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/FaresCard.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FaresCard } from "./FaresCard";

describe("FaresCard", () => {
  it("renders fare products when available", () => {
    render(
      <FaresCard
        data={{ fares: [{ product: "Saver Day Pass", price_chf: 39, class_of_travel: "2", discount: null }], booking_url: null }}
      />
    );

    expect(screen.getByText("Saver Day Pass")).toBeInTheDocument();
    expect(screen.getByText(/CHF 39/)).toBeInTheDocument();
  });

  it("renders the SBB booking deep link when no live fare was available", () => {
    render(<FaresCard data={{ fares: [], booking_url: "https://www.sbb.ch/en/timetable.html?x" }} />);

    expect(screen.getByRole("link", { name: /book on sbb/i })).toHaveAttribute(
      "href",
      "https://www.sbb.ch/en/timetable.html?x"
    );
  });
});
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/FlightCard.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FlightCard } from "./FlightCard";

const sampleFlight = {
  flight_number: "LX14",
  flight_date: "2026-09-25",
  airline: { name: "SWISS", iata: "LX", icao: "SWR" },
  departure: { airport: { iata: "ZRH", icao: "LSZH", name: "Zurich Airport", timezone: null }, scheduled: "2026-09-25T10:20:00+02:00", estimated: null, actual: null, terminal: "1", gate: "A12", delay_minutes: 5 },
  arrival: { airport: { iata: "JFK", icao: "KJFK", name: "John F. Kennedy Intl", timezone: null }, scheduled: "2026-09-25T14:10:00-04:00", estimated: null, actual: null, terminal: "4", gate: null, delay_minutes: null },
  flight_status: "scheduled",
};

describe("FlightCard", () => {
  it("renders a single flight lookup result with explicit not-reported fields", () => {
    render(
      <FlightCard
        data={{ flight: sampleFlight, flights: [], fields_missing: ["arrival.gate"] }}
        onSelect={() => {}}
      />
    );

    expect(screen.getByText("LX14")).toBeInTheDocument();
    expect(screen.getByText("SWISS")).toBeInTheDocument();
    expect(screen.getAllByText(/not reported by source/i).length).toBeGreaterThan(0);
  });

  it("renders a selectable list for a flight search result", () => {
    const onSelect = vi.fn();
    render(<FlightCard data={{ flight: null, flights: [sampleFlight], fields_missing: [] }} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: /LX14/ }));

    expect(onSelect).toHaveBeenCalledWith(sampleFlight);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test`
Expected: FAIL — modules don't exist yet.

- [ ] **Step 3: Implement the two cards**

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/FaresCard.tsx
interface FareProduct {
  product: string;
  price_chf: number;
  class_of_travel: string;
  discount: string | null;
}

export interface FareSearchData {
  fares: FareProduct[];
  booking_url: string | null;
}

export function FaresCard({ data }: { data: FareSearchData }) {
  if (data.fares.length > 0) {
    return (
      <ul className="space-y-2">
        {data.fares.map((fare, index) => (
          <li key={index} className="flex items-center justify-between rounded-xl border border-neutral-200 p-3">
            <span>{fare.product}{fare.discount ? ` (${fare.discount})` : ""}</span>
            <span className="font-medium">CHF {fare.price_chf}</span>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <a
      href={data.booking_url ?? undefined}
      target="_blank"
      rel="noreferrer"
      className="inline-block rounded-full bg-accent px-4 py-2 text-sm font-medium text-white"
    >
      Book on SBB
    </a>
  );
}
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/FlightCard.tsx
interface AirportInfo {
  iata: string | null;
  icao: string | null;
  name: string | null;
  timezone: string | null;
}

interface FlightEndpoint {
  airport: AirportInfo;
  scheduled: string | null;
  estimated: string | null;
  actual: string | null;
  terminal: string | null;
  gate: string | null;
  delay_minutes: number | null;
}

interface Flight {
  flight_number: string;
  flight_date: string;
  airline: { name: string | null; iata: string | null; icao: string | null };
  departure: FlightEndpoint;
  arrival: FlightEndpoint;
  flight_status: string | null;
}

export interface FlightSearchData {
  flight?: Flight | null;
  flights?: Flight[];
  fields_missing?: string[];
}

function fieldOrNotReported(value: string | null | undefined): string {
  return value ?? "not reported by source";
}

function FlightSummary({ flight }: { flight: Flight }) {
  return (
    <div className="rounded-xl border border-neutral-200 p-3">
      <div className="flex items-center justify-between text-sm font-medium">
        <span>{flight.flight_number}</span>
        <span>{fieldOrNotReported(flight.airline.name)}</span>
      </div>
      <div className="text-xs text-neutral-500">
        {fieldOrNotReported(flight.departure.airport.iata)} → {fieldOrNotReported(flight.arrival.airport.iata)}
      </div>
      <div className="text-xs text-neutral-500">
        Gate: {fieldOrNotReported(flight.departure.gate)} · Terminal: {fieldOrNotReported(flight.departure.terminal)}
      </div>
      <div className="text-xs text-neutral-500">
        Arrival gate: {fieldOrNotReported(flight.arrival.gate)}
      </div>
    </div>
  );
}

export function FlightCard({ data, onSelect }: { data: FlightSearchData; onSelect: (flight: Flight) => void }) {
  if (data.flight) {
    return <FlightSummary flight={data.flight} />;
  }

  return (
    <div className="space-y-2">
      {(data.flights ?? []).map((flight, index) => (
        <button key={index} type="button" onClick={() => onSelect(flight)} className="block w-full text-left">
          <FlightSummary flight={flight} />
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/frontend/src/components/widgets/FaresCard.tsx swiss-grounding-mcp/frontend/src/components/widgets/FlightCard.tsx swiss-grounding-mcp/frontend/src/components/widgets/FaresCard.test.tsx swiss-grounding-mcp/frontend/src/components/widgets/FlightCard.test.tsx
git commit -m "feat(frontend): fares and flight widgets"
```

---

## Task 13: Flight-to-Train and Airport Guidance Widgets

**Files:**
- Create: `swiss-grounding-mcp/frontend/src/components/widgets/FlightToTrainCard.tsx`
- Create: `swiss-grounding-mcp/frontend/src/components/widgets/AirportGuidanceCard.tsx`
- Test: `swiss-grounding-mcp/frontend/src/components/widgets/FlightToTrainCard.test.tsx`
- Test: `swiss-grounding-mcp/frontend/src/components/widgets/AirportGuidanceCard.test.tsx`

**Interfaces:**
- Consumes: `TrainConnectionsCard`/`ConnectionSearchData` (Task 11), `FlightCard`/`FlightSearchData` (Task 12).
- Produces: `<FlightToTrainCard data={FlightToTrainData} onSelectConnection={(connection) => void} />` and `<AirportGuidanceCard data={AirportGuidanceData} />`.

- [ ] **Step 1: Write the failing tests**

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/FlightToTrainCard.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FlightToTrainCard } from "./FlightToTrainCard";

describe("FlightToTrainCard", () => {
  it("renders the flight summary and onward train connections together", () => {
    render(
      <FlightToTrainCard
        data={{
          message: "Considering onward trains departing no earlier than 15:10 (60-minute transfer buffer).",
          flight: {
            flight_number: "LX14",
            flight_date: "2026-09-25",
            airline: { name: "SWISS", iata: "LX", icao: "SWR" },
            departure: { airport: { iata: "JFK", icao: "KJFK", name: "JFK", timezone: null }, scheduled: null, estimated: null, actual: null, terminal: null, gate: null, delay_minutes: null },
            arrival: { airport: { iata: "ZRH", icao: "LSZH", name: "Zurich Airport", timezone: null }, scheduled: "2026-09-25T14:10:00+02:00", estimated: null, actual: null, terminal: "2", gate: null, delay_minutes: null },
            flight_status: "scheduled",
          },
          train_connections: [
            { departure: "2026-09-25T15:10:00+02:00", arrival: "2026-09-25T16:00:00+02:00", duration_minutes: 50, changes: 0, legs: [] },
          ],
        }}
        onSelectConnection={() => {}}
      />
    );

    expect(screen.getByText("LX14")).toBeInTheDocument();
    expect(screen.getByText(/60-minute transfer buffer/)).toBeInTheDocument();
    expect(screen.getByText(/50 min/)).toBeInTheDocument();
  });
});
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/AirportGuidanceCard.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AirportGuidanceCard } from "./AirportGuidanceCard";

describe("AirportGuidanceCard", () => {
  it("renders the guidance text and its citation link", () => {
    render(
      <AirportGuidanceCard
        data={{
          topic: "transfers",
          guidance: "Check the departure time and gate on the flight information screens.",
          source: "Flughafen Zürich AG",
          source_url: "https://www.flughafen-zuerich.ch/en/passengers/fly/all-about-the-flight/transfer",
        }}
      />
    );

    expect(screen.getByText(/departure time and gate/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /flughafen zürich ag/i })).toHaveAttribute(
      "href",
      "https://www.flughafen-zuerich.ch/en/passengers/fly/all-about-the-flight/transfer"
    );
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test`
Expected: FAIL — modules don't exist yet.

- [ ] **Step 3: Implement the two cards**

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/FlightToTrainCard.tsx
import { FlightCard, type FlightSearchData } from "./FlightCard";
import { TrainConnectionsCard, type ConnectionSearchData } from "./TrainConnectionsCard";

interface FlightToTrainData {
  message?: string | null;
  flight?: FlightSearchData["flight"];
  train_connections: ConnectionSearchData["connections"];
}

export function FlightToTrainCard({
  data,
  onSelectConnection,
}: {
  data: FlightToTrainData;
  onSelectConnection: (connection: ConnectionSearchData["connections"][number]) => void;
}) {
  return (
    <div className="space-y-3">
      {data.message && <p className="text-sm text-neutral-600">{data.message}</p>}
      {data.flight && <FlightCard data={{ flight: data.flight, flights: [] }} onSelect={() => {}} />}
      <TrainConnectionsCard data={{ connections: data.train_connections }} onSelect={onSelectConnection} />
    </div>
  );
}
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/AirportGuidanceCard.tsx
export interface AirportGuidanceData {
  topic: string;
  guidance: string | null;
  source: string | null;
  source_url: string | null;
}

export function AirportGuidanceCard({ data }: { data: AirportGuidanceData }) {
  return (
    <div className="space-y-2 rounded-xl border border-neutral-200 p-4">
      <p className="text-sm text-neutral-700">{data.guidance}</p>
      {data.source_url && (
        <a href={data.source_url} target="_blank" rel="noreferrer" className="text-xs text-neutral-400 hover:underline">
          Source: {data.source}
        </a>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/frontend/src/components/widgets/FlightToTrainCard.tsx swiss-grounding-mcp/frontend/src/components/widgets/AirportGuidanceCard.tsx swiss-grounding-mcp/frontend/src/components/widgets/FlightToTrainCard.test.tsx swiss-grounding-mcp/frontend/src/components/widgets/AirportGuidanceCard.test.tsx
git commit -m "feat(frontend): flight-to-train and airport guidance widgets"
```

---

## Task 14: Status Banner and Widget Registry Wiring

**Files:**
- Create: `swiss-grounding-mcp/frontend/src/components/widgets/StatusBanner.tsx`
- Create: `swiss-grounding-mcp/frontend/src/lib/widgetRegistry.tsx`
- Modify: `swiss-grounding-mcp/frontend/src/components/AssistantTurn.tsx`
- Test: `swiss-grounding-mcp/frontend/src/components/widgets/StatusBanner.test.tsx`
- Test: `swiss-grounding-mcp/frontend/src/lib/widgetRegistry.test.tsx`
- Test: Modify `swiss-grounding-mcp/frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: all widget components from Tasks 11-13.
- Produces: `DISPLAYABLE_STATUSES: Record<string, string[]>` and `WIDGET_COMPONENTS: Record<string, React.ComponentType<any>>` (both from `lib/widgetRegistry.tsx`), and `<StatusBanner status={string} message={string | null} candidates={StopCandidate[]} onClarify={(value: string) => void} />`. `AssistantTurn` (modified) uses these to replace its Task-10 raw-JSON fallback.

- [ ] **Step 1: Write the failing tests**

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/StatusBanner.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StatusBanner } from "./StatusBanner";

describe("StatusBanner", () => {
  it("renders the honest message for an out_of_scope status", () => {
    render(<StatusBanner status="out_of_scope" message="Taxes are not covered by this assistant." candidates={[]} onClarify={() => {}} />);

    expect(screen.getByText(/not covered/i)).toBeInTheDocument();
  });

  it("renders clickable candidate chips for needs_clarification and resends the choice", () => {
    const onClarify = vi.fn();
    render(
      <StatusBanner
        status="needs_clarification"
        message="Which Fribourg did you mean?"
        candidates={[{ name: "Fribourg/Freiburg", stop_ref: "8504100", probability: null }]}
        onClarify={onClarify}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Fribourg/Freiburg" }));

    expect(onClarify).toHaveBeenCalledWith("Fribourg/Freiburg");
  });
});
```

```tsx
// swiss-grounding-mcp/frontend/src/lib/widgetRegistry.test.tsx
import { describe, expect, it } from "vitest";
import { DISPLAYABLE_STATUSES, WIDGET_COMPONENTS } from "./widgetRegistry";

describe("widgetRegistry", () => {
  it("has a component and a displayable-status list for every widget type", () => {
    const expectedTypes = [
      "train_connections", "station_board", "fares", "disruptions",
      "flight", "flight_search", "airport_guidance", "flight_to_train",
    ];
    for (const type of expectedTypes) {
      expect(WIDGET_COMPONENTS[type]).toBeDefined();
      expect(DISPLAYABLE_STATUSES[type]).toBeDefined();
    }
  });

  it("only treats success/fallback_link as displayable for fares", () => {
    expect(DISPLAYABLE_STATUSES.fares).toEqual(["success", "fallback_link"]);
  });

  it("only treats ok as displayable for train connections", () => {
    expect(DISPLAYABLE_STATUSES.train_connections).toEqual(["ok"]);
  });
});
```

Update `App.test.tsx`'s existing widget assertion to reflect the real widget now being rendered instead of raw JSON — replace:

```tsx
expect(screen.getByTestId("widget-find_connections")).toBeInTheDocument();
```

with:

```tsx
expect(screen.getByText(/direct/i)).toBeInTheDocument();
```

(the sample `find_connections` payload in that test has `connections: []`, so update the test's fixture data to include one connection with `changes: 0` so `TrainConnectionsCard` has something to render — change the `widget` frame in that test to:
`'data: {"type": "widget", "tool": "find_connections", "status": "ok", "data": {"connections": [{"departure": "2026-09-24T18:04:00Z", "arrival": "2026-09-24T18:10:00Z", "duration_minutes": 6, "changes": 0, "legs": []}]}}\n\n'`)

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test`
Expected: FAIL — `StatusBanner` and `widgetRegistry` don't exist; `App.test.tsx`'s updated assertion fails against the Task-10 raw-JSON rendering.

- [ ] **Step 3: Implement `StatusBanner`, `widgetRegistry`, and rewire `AssistantTurn`**

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/StatusBanner.tsx
interface StopCandidate {
  name: string;
  stop_ref: string;
  probability: number | null;
}

export function StatusBanner({
  status,
  message,
  candidates,
  onClarify,
}: {
  status: string;
  message: string | null;
  candidates: StopCandidate[];
  onClarify: (value: string) => void;
}) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-neutral-100 p-4 text-sm text-neutral-600">
      <p>{message ?? "This could not be answered."}</p>
      {status === "needs_clarification" && candidates.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {candidates.map((candidate) => (
            <button
              key={candidate.stop_ref}
              type="button"
              onClick={() => onClarify(candidate.name)}
              className="rounded-full border border-neutral-300 px-3 py-1 text-xs hover:border-accent"
            >
              {candidate.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

```tsx
// swiss-grounding-mcp/frontend/src/lib/widgetRegistry.tsx
import { ComponentType } from "react";
import { TrainConnectionsCard } from "../components/widgets/TrainConnectionsCard";
import { StationBoardCard } from "../components/widgets/StationBoardCard";
import { FaresCard } from "../components/widgets/FaresCard";
import { DisruptionsCard } from "../components/widgets/DisruptionsCard";
import { FlightCard } from "../components/widgets/FlightCard";
import { AirportGuidanceCard } from "../components/widgets/AirportGuidanceCard";
import { FlightToTrainCard } from "../components/widgets/FlightToTrainCard";

export const WIDGET_COMPONENTS: Record<string, ComponentType<any>> = {
  train_connections: TrainConnectionsCard,
  station_board: StationBoardCard,
  fares: FaresCard,
  disruptions: DisruptionsCard,
  flight: FlightCard,
  flight_search: FlightCard,
  airport_guidance: AirportGuidanceCard,
  flight_to_train: FlightToTrainCard,
};

export const DISPLAYABLE_STATUSES: Record<string, string[]> = {
  train_connections: ["ok"],
  station_board: ["ok"],
  fares: ["success", "fallback_link"],
  disruptions: ["ok"],
  flight: ["answered"],
  flight_search: ["answered"],
  airport_guidance: ["answered"],
  flight_to_train: ["answered"],
};
```

```tsx
// swiss-grounding-mcp/frontend/src/components/AssistantTurn.tsx
import type { Turn } from "../App";
import { StatusBanner } from "./widgets/StatusBanner";
import { DISPLAYABLE_STATUSES, WIDGET_COMPONENTS } from "../lib/widgetRegistry";

interface AssistantTurnProps {
  turn: Turn;
  onClarify: (value: string) => void;
}

export function AssistantTurn({ turn, onClarify }: AssistantTurnProps) {
  return (
    <div className="space-y-3">
      {turn.text && <p className="text-neutral-700">{turn.text}</p>}
      {turn.widgets.map((widget, index) => {
        const widgetType = (widget.data as { widget_type?: string }).widget_type;
        const key = widgetType && WIDGET_COMPONENTS[widgetType] ? widgetType : undefined;
        const displayable = key ? DISPLAYABLE_STATUSES[key].includes(widget.status) : false;

        if (!key || !displayable) {
          return (
            <StatusBanner
              key={index}
              status={widget.status}
              message={(widget.data as { message?: string | null }).message ?? null}
              candidates={(widget.data as { candidates?: any[] }).candidates ?? []}
              onClarify={onClarify}
            />
          );
        }

        const Component = WIDGET_COMPONENTS[key];
        return (
          <div key={index} data-testid={`widget-${widget.tool ?? "unknown"}`}>
            <Component data={widget.data} onSelect={() => {}} onSelectConnection={() => {}} />
          </div>
        );
      })}
    </div>
  );
}
```

Note: `map_result` (backend Task 5) nests the tool's fields directly under `data`, not under `data.data` — its return is `{"widget_type": ..., "status": ..., "data": {...tool fields...}}`, and the SSE `widget` event forwards `status` and `data` from that at the top level (`{"type": "widget", "tool": name, "status": mapped["status"], "data": mapped["data"]}` — see Task 7). So on the frontend, `widget.data` **is** the tool's raw field dict (e.g. `{"connections": [...], "provenance": {...}}`), and it does **not** itself contain a `widget_type` key. Fix `AssistantTurn` to use `widget.tool` (already present on every event) mapped through `WIDGET_TYPES`'s frontend mirror instead of reading a nonexistent `widget.data.widget_type`:

```tsx
// swiss-grounding-mcp/frontend/src/lib/widgetRegistry.tsx  (append)
export const WIDGET_TYPE_BY_TOOL: Record<string, string> = {
  find_connections: "train_connections",
  find_disruptions: "disruptions",
  get_station_board: "station_board",
  check_public_transport_fares: "fares",
  find_flight_by_number: "flight",
  search_airport_flights: "flight_search",
  get_airport_guidance: "airport_guidance",
  connect_flight_to_train: "flight_to_train",
};
```

```tsx
// swiss-grounding-mcp/frontend/src/components/AssistantTurn.tsx  (corrected widget-type lookup)
        const widgetType = widget.tool ? WIDGET_TYPE_BY_TOOL[widget.tool] : undefined;
        const displayable = widgetType ? DISPLAYABLE_STATUSES[widgetType].includes(widget.status) : false;

        if (!widgetType || !displayable) {
          return (
            <StatusBanner
              key={index}
              status={widget.status}
              message={(widget.data as { message?: string | null }).message ?? null}
              candidates={(widget.data as { candidates?: any[] }).candidates ?? []}
              onClarify={onClarify}
            />
          );
        }

        const Component = WIDGET_COMPONENTS[widgetType];
```

(and update the corresponding import line to `import { DISPLAYABLE_STATUSES, WIDGET_COMPONENTS, WIDGET_TYPE_BY_TOOL } from "../lib/widgetRegistry";`)

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test`
Expected: PASS — all suites, including the updated `App.test.tsx` assertion.

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/frontend/src
git commit -m "feat(frontend): status banner and widget registry wiring"
```

---

## Task 15: Route Map

**Files:**
- Create: `swiss-grounding-mcp/frontend/src/lib/geocode.ts`
- Create: `swiss-grounding-mcp/frontend/src/components/widgets/RouteMap.tsx`
- Modify: `swiss-grounding-mcp/frontend/src/components/widgets/TrainConnectionsCard.tsx` (render `RouteMap` for the selected connection)
- Test: `swiss-grounding-mcp/frontend/src/lib/geocode.test.ts`
- Test: `swiss-grounding-mcp/frontend/src/components/widgets/RouteMap.test.tsx`

**Interfaces:**
- Produces: `geocode(placeName: string): Promise<{ lat: number; lng: number } | null>` and `<RouteMap origin={string} destination={string} />`.

- [ ] **Step 1: Write the failing tests**

```ts
// swiss-grounding-mcp/frontend/src/lib/geocode.test.ts
import { describe, expect, it, vi, afterEach } from "vitest";
import { geocode } from "./geocode";

afterEach(() => vi.restoreAllMocks());

describe("geocode", () => {
  it("returns coordinates for a resolvable place", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ features: [{ center: [7.4474, 46.9481] }] }),
      })
    );

    const result = await geocode("Bern");

    expect(result).toEqual({ lat: 46.9481, lng: 7.4474 });
  });

  it("returns null when no features are found", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ features: [] }) }));

    const result = await geocode("Nonexistent Place");

    expect(result).toBeNull();
  });

  it("returns null when the geocoding request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }));

    const result = await geocode("Bern");

    expect(result).toBeNull();
  });
});
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/RouteMap.test.tsx
import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { RouteMap } from "./RouteMap";
import * as geocodeModule from "../../lib/geocode";

vi.mock("mapbox-gl", () => ({
  default: {
    accessToken: "",
    Map: vi.fn().mockImplementation(() => ({
      on: vi.fn(),
      remove: vi.fn(),
      addControl: vi.fn(),
    })),
    Marker: vi.fn().mockImplementation(() => ({ setLngLat: vi.fn().mockReturnThis(), addTo: vi.fn().mockReturnThis() })),
  },
}));

afterEach(() => vi.restoreAllMocks());

describe("RouteMap", () => {
  it("shows an unavailable message when a location cannot be geocoded", async () => {
    vi.spyOn(geocodeModule, "geocode").mockResolvedValue(null);

    render(<RouteMap origin="Bern" destination="Nowhereville" />);

    await waitFor(() => expect(screen.getByText(/map unavailable/i)).toBeInTheDocument());
  });

  it("renders the map container once both endpoints resolve", async () => {
    vi.spyOn(geocodeModule, "geocode")
      .mockResolvedValueOnce({ lat: 46.9481, lng: 7.4474 })
      .mockResolvedValueOnce({ lat: 47.3769, lng: 8.5417 });

    render(<RouteMap origin="Bern" destination="Zürich" />);

    await waitFor(() => expect(screen.getByTestId("route-map")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test`
Expected: FAIL — `geocode.ts` and `RouteMap.tsx` don't exist yet.

- [ ] **Step 3: Implement `geocode` and `RouteMap`**

```ts
// swiss-grounding-mcp/frontend/src/lib/geocode.ts
const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN ?? "";

export interface Coordinates {
  lat: number;
  lng: number;
}

export async function geocode(placeName: string): Promise<Coordinates | null> {
  const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(placeName)}.json?access_token=${MAPBOX_TOKEN}&limit=1`;

  const response = await fetch(url);
  if (!response.ok) return null;

  const body = await response.json();
  const feature = body.features?.[0];
  if (!feature) return null;

  const [lng, lat] = feature.center;
  return { lat, lng };
}
```

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/RouteMap.tsx
import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { geocode } from "../../lib/geocode";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN ?? "";

export function RouteMap({ origin, destination }: { origin: string; destination: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function draw() {
      const [originCoords, destinationCoords] = await Promise.all([geocode(origin), geocode(destination)]);
      if (cancelled) return;

      if (!originCoords || !destinationCoords || !containerRef.current) {
        setUnavailable(true);
        return;
      }

      const map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/light-v11",
        center: [originCoords.lng, originCoords.lat],
        zoom: 7,
      });
      new mapboxgl.Marker().setLngLat([originCoords.lng, originCoords.lat]).addTo(map);
      new mapboxgl.Marker().setLngLat([destinationCoords.lng, destinationCoords.lat]).addTo(map);
    }

    draw();
    return () => {
      cancelled = true;
    };
  }, [origin, destination]);

  if (unavailable) {
    return <p className="text-xs text-neutral-400">Map unavailable for this location.</p>;
  }

  return <div ref={containerRef} data-testid="route-map" className="h-64 w-full rounded-xl" />;
}
```

Wire it into the selected connection in `TrainConnectionsCard`:

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/TrainConnectionsCard.tsx  (add state + RouteMap)
import { useState } from "react";
import { RouteMap } from "./RouteMap";

// inside TrainConnectionsCard component body, replace the plain function body with:
export function TrainConnectionsCard({ data, onSelect }: TrainConnectionsCardProps) {
  const [selected, setSelected] = useState<Connection | null>(null);

  function handleSelect(connection: Connection) {
    setSelected(connection);
    onSelect(connection);
  }

  return (
    <div className="space-y-2">
      {data.connections.map((connection, index) => (
        <button
          key={index}
          type="button"
          onClick={() => handleSelect(connection)}
          className="w-full rounded-xl border border-neutral-200 p-3 text-left hover:border-accent"
        >
          <div className="flex items-center justify-between text-sm font-medium">
            <span>{formatTime(connection.departure)} → {formatTime(connection.arrival)}</span>
            <span>{connection.duration_minutes} min</span>
          </div>
          <div className="text-xs text-neutral-500">
            {connection.changes === 0 ? "Direct" : `${connection.changes} change${connection.changes > 1 ? "s" : ""}`}
          </div>
        </button>
      ))}
      {selected && selected.legs.length > 0 && (
        <RouteMap origin={selected.legs[0].from_name} destination={selected.legs[selected.legs.length - 1].to_name} />
      )}
      {data.provenance && (
        <a
          href={data.provenance.source_url}
          target="_blank"
          rel="noreferrer"
          className="block text-xs text-neutral-400 hover:underline"
        >
          Source: {data.provenance.source}
        </a>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test`
Expected: PASS. Existing `TrainConnectionsCard.test.tsx` cases continue to pass since `legs` is empty in most fixtures used there except the first ("renders one selectable option...") which has one leg but no click, so `RouteMap` isn't mounted for that test (only after a click sets `selected`); the "calls onSelect" test clicks the button, which now also mounts `RouteMap` — mock `mapbox-gl` in that test file the same way as `RouteMap.test.tsx` to avoid a real WebGL call:

```tsx
// swiss-grounding-mcp/frontend/src/components/widgets/TrainConnectionsCard.test.tsx  (add at top)
import { vi } from "vitest";
vi.mock("mapbox-gl", () => ({
  default: {
    accessToken: "",
    Map: vi.fn().mockImplementation(() => ({ on: vi.fn(), remove: vi.fn(), addControl: vi.fn() })),
    Marker: vi.fn().mockImplementation(() => ({ setLngLat: vi.fn().mockReturnThis(), addTo: vi.fn().mockReturnThis() })),
  },
}));
```

Run: `npm run test`
Expected: PASS (all suites)

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/frontend/src/lib/geocode.ts swiss-grounding-mcp/frontend/src/components/widgets/RouteMap.tsx swiss-grounding-mcp/frontend/src/components/widgets/TrainConnectionsCard.tsx swiss-grounding-mcp/frontend/src/lib/geocode.test.ts swiss-grounding-mcp/frontend/src/components/widgets/RouteMap.test.tsx swiss-grounding-mcp/frontend/src/components/widgets/TrainConnectionsCard.test.tsx
git commit -m "feat(frontend): Mapbox route map for the selected connection"
```

---

## Task 16: Frontend README and Full Suite Check

**Files:**
- Create: `swiss-grounding-mcp/frontend/README.md`

**Interfaces:** none new — documentation only.

- [ ] **Step 1: Write the README**

```markdown
<!-- swiss-grounding-mcp/frontend/README.md -->
# Swiss Grounding MCP — Chat Frontend

Vite + React + TypeScript + Tailwind chat UI. Every travel-tool result
renders as a visual widget (train connections, flights, a route map,
station boards, fares, disruptions, airport guidance) instead of chat
prose; every non-success tool status renders an honest status banner.

## Setup

```bash
cd swiss-grounding-mcp/frontend
npm install
cp .env.example .env.local
# edit .env.local: VITE_AGENT_BACKEND_URL (defaults to http://127.0.0.1:8080)
# and VITE_MAPBOX_TOKEN (get a free token at https://account.mapbox.com/)
```

## Running

```bash
npm run dev
```

Requires the agent backend (`swiss-grounding-mcp/agent-backend`) running
at `VITE_AGENT_BACKEND_URL`.

## Running the checks

```bash
npm run test
```
```

- [ ] **Step 2: Run the full frontend suite**

Run: `npm run test`
Expected: PASS (every suite from Tasks 9-15)

- [ ] **Step 3: Commit**

```bash
git add swiss-grounding-mcp/frontend/README.md
git commit -m "docs(frontend): add setup and run instructions"
```

---

## Task 17: Manual End-to-End Verification

**Files:** none (manual verification against the running system; no code changes).

**Interfaces:** none.

- [ ] **Step 1: Confirm prerequisites**

Confirm `swiss-grounding-mcp/server/.env` has a working `OJP_API_TOKEN` and `AERODATABOX_API_KEY` (per that project's README), `swiss-grounding-mcp/agent-backend/.env` has a working `OPENAI_API_KEY`, and `swiss-grounding-mcp/frontend/.env.local` has a working `VITE_MAPBOX_TOKEN`.

- [ ] **Step 2: Start both services**

```bash
cd swiss-grounding-mcp/agent-backend && uv run uvicorn agent_backend.main:app --reload --port 8080 &
cd swiss-grounding-mcp/frontend && npm run dev
```

- [ ] **Step 3: Walk through the scenarios**

1. Open the frontend URL. Confirm the empty-state hero and pill composer render, matching the Apple-like direction from the design spec.
2. Ask "Trains from Bern to Zürich HB". Confirm the hero collapses, a short summary line appears, `TrainConnectionsCard` renders real connections, and clicking one reveals `RouteMap` with two markers.
3. Ask about a station shared by two cantons (an ambiguous name). Confirm `StatusBanner` renders clarification chips and clicking one resends the resolved name as the next message.
4. Ask "Find flight LX14 tomorrow". Confirm `FlightCard` renders with any `fields_missing` shown as "not reported by source".
5. Ask an out-of-scope question (e.g., about health insurance premiums). Confirm an honest `StatusBanner`, never a fabricated widget.
6. Temporarily set an invalid `OJP_API_TOKEN` in `server/.env`, restart the agent backend, repeat step 2, and confirm a `source_error` `StatusBanner` instead of a crash or guessed answer. Restore the valid token afterward.

- [ ] **Step 4: Record the outcome**

Note the result of each scenario (pass/fail with details) in the PR description or session notes — this is the evidence required before claiming the feature complete, per `verification-before-completion`.

---

## Task 18: Impeccable Polish Pass

**Files:** whatever `impeccable audit`/`polish` identifies in `swiss-grounding-mcp/frontend/src/`.

**Interfaces:** none new.

- [ ] **Step 1: Run the audit**

Invoke the `impeccable` skill's `audit` command against `swiss-grounding-mcp/frontend` (accessibility, responsive behavior, performance) with the app running from Task 17.

- [ ] **Step 2: Run the polish pass**

Invoke `impeccable`'s `polish` command for a final visual/interaction pass toward the Apple-like direction described in the design spec (section 5.1), fixing whatever the audit and polish passes surface.

- [ ] **Step 3: Re-run the full test suites**

Run: `cd swiss-grounding-mcp/agent-backend && uv run pytest -v` and `cd swiss-grounding-mcp/frontend && npm run test`
Expected: PASS (no regressions from styling/markup changes)

- [ ] **Step 4: Commit**

```bash
git add swiss-grounding-mcp/frontend
git commit -m "polish(frontend): impeccable audit and polish pass"
```
