# Swiss Grounding MCP — Milestone 1 (Train Connections) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working MCP server exposing one tool, `find_connections`, that
answers Swiss passenger-train connection questions using live OJP 2.0 data,
with honest structured statuses (ok / needs_clarification / not_found /
out_of_scope / source_error) and source citations on every successful answer.

**Architecture:** A layered Python package under
`swiss-grounding-mcp/server/src/swiss_grounding_mcp/`: `sources/ojp/` builds
and parses OJP 2.0 XML and makes the HTTP call; `domain/` holds the shared
pydantic models; `evidence/` builds citation blocks; `tools/` orchestrates
resolution + querying + status decisions; `server.py` registers the tool on
an `MCPServer` and runs it over stdio or Streamable HTTP.

**Tech Stack:** Python 3.10+, `mcp` SDK v2.x (`MCPServer`, `@mcp.tool()`),
`httpx` for the OJP HTTP call, stdlib `xml.etree.ElementTree` for building
request XML, `defusedxml` for parsing response XML, `python-dotenv` for
loading `.env`, `pytest` for tests, `uv` for dependency/venv management.

**Spec:** `docs/superpowers/specs/2026-09-24-swiss-grounding-mcp-design.md`

## Global Constraints

- Implementation lives under `swiss-grounding-mcp/server/` (spec §4);
  existing challenge material (`swiss-grounding-mcp/README.md`,
  `swiss-grounding-mcp/AGENTS.md`, the briefing PDF) is untouched.
- No LLM calls and no API keys other than `OJP_API_TOKEN` inside the server
  (spec §10).
- No secrets committed; `.env.example` ships with empty values (spec §7).
- OJP endpoint default: `https://api.opentransportdata.swiss/ojp20`, headers
  `Content-Type: application/xml` and `Authorization: Bearer <token>` (spec
  §3).
- Rate limits to respect conceptually (not enforced client-side): 50
  requests/minute, 20,000/day per token (spec §3).
- `RESPECT_ROBOTS_TXT` config flag exists, defaults `true`, is not consulted
  by the OJP adapter, and the README says so explicitly (spec §7).
- Every tool response is a structured object with a `status` field; only
  `ok` populates `connections`, only `needs_clarification` populates
  `candidates` (spec §5).
- `departure_time`/`arrival_time` both optional; omitted means "now"; if
  both given, `departure_time` wins and the response says so (spec §5,
  §6).
- `results` parameter: default 3, max 5 (spec §5).
- Both `stdio` and `streamable-http` transports must work from the same
  tool code (spec §8).

## Review Focus

- **Accented / alternate station names.** "Geneve" (no accent) or "Biel"
  for the official "Biel/Bienne" must still resolve automatically, not
  bounce into `needs_clarification` just because the input string isn't a
  byte-for-byte match. Covered in Task 7's resolution tests.
- **Both `departure_time` and `arrival_time` supplied.** The spec requires
  `departure_time` to win and the response to say so explicitly, not
  silently drop `arrival_time`. Covered in Task 7.
- **`results` outside 1..5.** Must be clamped (e.g. `0`, `-1`, `500`), never
  passed through unchecked to OJP or silently rejected. Covered in Task 7.
- **A 2xx OJP response carrying an embedded OJP-level error/fault
  element.** Must be treated as `source_error`, not parsed as "zero
  connections found" (those are different failure modes with different
  honest messages). Covered in Task 5 (client) and Task 4 (parser fixture).
- **Two genuinely ambiguous stations with close LIR match
  probabilities.** Must trigger `needs_clarification`, not silently pick
  the top-ranked candidate. Covered in Task 7, alongside the dominant-match
  case that should auto-resolve.

---

## Task 1: Project scaffolding and configuration

**Files:**
- Create: `swiss-grounding-mcp/server/pyproject.toml`
- Create: `swiss-grounding-mcp/server/.env.example`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/__init__.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/config/__init__.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/config/settings.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_settings.py`

**Interfaces:**
- Produces: `swiss_grounding_mcp.config.settings.Settings` dataclass with
  fields `ojp_api_token: str`, `ojp_base_url: str`, `ojp_requestor_ref: str`,
  `ojp_timeout_seconds: float`, `respect_robots_txt: bool`,
  `mcp_http_host: str`, `mcp_http_port: int`; classmethod
  `Settings.from_env(env: Mapping[str, str] | None = None) -> Settings`.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_settings.py
from swiss_grounding_mcp.config.settings import Settings


def test_defaults_when_env_empty():
    settings = Settings.from_env({})

    assert settings.ojp_api_token == ""
    assert settings.ojp_base_url == "https://api.opentransportdata.swiss/ojp20"
    assert settings.ojp_requestor_ref == "swiss-grounding-mcp"
    assert settings.ojp_timeout_seconds == 10.0
    assert settings.respect_robots_txt is True
    assert settings.mcp_http_host == "127.0.0.1"
    assert settings.mcp_http_port == 8000


def test_env_overrides_defaults():
    env = {
        "OJP_API_TOKEN": "secret-token",
        "OJP_BASE_URL": "https://example.test/ojp20",
        "OJP_REQUESTOR_REF": "my-app",
        "OJP_TIMEOUT_SECONDS": "5",
        "RESPECT_ROBOTS_TXT": "false",
        "MCP_HTTP_HOST": "0.0.0.0",
        "MCP_HTTP_PORT": "9000",
    }

    settings = Settings.from_env(env)

    assert settings.ojp_api_token == "secret-token"
    assert settings.ojp_base_url == "https://example.test/ojp20"
    assert settings.ojp_requestor_ref == "my-app"
    assert settings.ojp_timeout_seconds == 5.0
    assert settings.respect_robots_txt is False
    assert settings.mcp_http_host == "0.0.0.0"
    assert settings.mcp_http_port == 9000


def test_respect_robots_txt_accepts_common_truthy_strings():
    assert Settings.from_env({"RESPECT_ROBOTS_TXT": "true"}).respect_robots_txt is True
    assert Settings.from_env({"RESPECT_ROBOTS_TXT": "1"}).respect_robots_txt is True
    assert Settings.from_env({"RESPECT_ROBOTS_TXT": "false"}).respect_robots_txt is False
    assert Settings.from_env({"RESPECT_ROBOTS_TXT": "0"}).respect_robots_txt is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && python -m pytest tests/unit/test_settings.py -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'swiss_grounding_mcp'` (package doesn't exist yet).

- [ ] **Step 3: Create the project scaffolding**

```toml
# swiss-grounding-mcp/server/pyproject.toml
[project]
name = "swiss-grounding-mcp"
version = "0.1.0"
description = "MCP server for Swiss passenger-train connections, grounded in OJP 2.0."
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=2.0.1,<3",
    "httpx>=0.27",
    "defusedxml>=0.7.1",
    "python-dotenv>=1.0.1",
]

[project.scripts]
swiss-grounding-mcp = "swiss_grounding_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/swiss_grounding_mcp"]

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```bash
# swiss-grounding-mcp/server/.env.example
OJP_API_TOKEN=
OJP_BASE_URL=https://api.opentransportdata.swiss/ojp20
OJP_REQUESTOR_REF=swiss-grounding-mcp
OJP_TIMEOUT_SECONDS=10
RESPECT_ROBOTS_TXT=true
MCP_HTTP_HOST=127.0.0.1
MCP_HTTP_PORT=8000
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/__init__.py
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/config/__init__.py
```

- [ ] **Step 4: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/config/settings.py
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _parse_bool(value: str, default: bool) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    return default


@dataclass(frozen=True)
class Settings:
    ojp_api_token: str = ""
    ojp_base_url: str = "https://api.opentransportdata.swiss/ojp20"
    ojp_requestor_ref: str = "swiss-grounding-mcp"
    ojp_timeout_seconds: float = 10.0
    respect_robots_txt: bool = True
    mcp_http_host: str = "127.0.0.1"
    mcp_http_port: int = 8000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        defaults = cls()
        return cls(
            ojp_api_token=source.get("OJP_API_TOKEN", defaults.ojp_api_token),
            ojp_base_url=source.get("OJP_BASE_URL", defaults.ojp_base_url),
            ojp_requestor_ref=source.get("OJP_REQUESTOR_REF", defaults.ojp_requestor_ref),
            ojp_timeout_seconds=float(
                source.get("OJP_TIMEOUT_SECONDS", defaults.ojp_timeout_seconds)
            ),
            respect_robots_txt=_parse_bool(
                source.get("RESPECT_ROBOTS_TXT", str(defaults.respect_robots_txt)),
                defaults.respect_robots_txt,
            ),
            mcp_http_host=source.get("MCP_HTTP_HOST", defaults.mcp_http_host),
            mcp_http_port=int(source.get("MCP_HTTP_PORT", defaults.mcp_http_port)),
        )
```

- [ ] **Step 5: Install dependencies and run the test to verify it passes**

Run:
```bash
cd swiss-grounding-mcp/server
uv venv
uv pip install -e ".[dev]" --group dev
uv run pytest tests/unit/test_settings.py -v
```
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/server
git commit -m "feat: scaffold swiss-grounding-mcp server project and settings"
```

---

## Task 2: Domain models

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/domain/__init__.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/domain/models.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_domain_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `swiss_grounding_mcp.domain.models` with `Leg`, `Connection`,
  `StopCandidate`, `Provenance`, `Status` (a `Literal` type alias), and
  `ConnectionSearchResult` — all pydantic `BaseModel`s (except `Status`),
  used by every later task.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_domain_models.py
from swiss_grounding_mcp.domain.models import (
    Connection,
    ConnectionSearchResult,
    Leg,
    Provenance,
    StopCandidate,
)


def test_ok_result_serializes_connections_and_provenance():
    leg = Leg(
        mode="rail",
        line="IC 8",
        from_name="Bern",
        to_name="Zürich HB",
        departure="2026-09-24T18:04:00Z",
        arrival="2026-09-24T18:57:00Z",
    )
    connection = Connection(
        departure="2026-09-24T18:04:00Z",
        arrival="2026-09-24T19:47:00Z",
        duration_minutes=103,
        changes=1,
        legs=[leg],
    )
    provenance = Provenance(
        source="opentransportdata.swiss OJP 2.0",
        source_url="https://api.opentransportdata.swiss/ojp20",
        retrieved_at="2026-09-24T18:03:12Z",
    )

    result = ConnectionSearchResult(
        status="ok",
        connections=[connection],
        provenance=provenance,
    )

    dumped = result.model_dump()
    assert dumped["status"] == "ok"
    assert dumped["connections"][0]["legs"][0]["line"] == "IC 8"
    assert dumped["candidates"] == []
    assert dumped["provenance"]["source_url"] == "https://api.opentransportdata.swiss/ojp20"


def test_needs_clarification_result_carries_candidates_and_no_connections():
    result = ConnectionSearchResult(
        status="needs_clarification",
        message="Multiple stations match 'Fribourg'.",
        candidates=[
            StopCandidate(name="Fribourg/Freiburg", stop_ref="ch:1:sloid:7000"),
            StopCandidate(name="Freiburg im Breisgau Hbf", stop_ref="de:1:sloid:1"),
        ],
    )

    dumped = result.model_dump()
    assert dumped["status"] == "needs_clarification"
    assert dumped["connections"] == []
    assert len(dumped["candidates"]) == 2
    assert dumped["provenance"] is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_domain_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.domain'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/domain/__init__.py
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/domain/models.py
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_domain_models.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/domain swiss-grounding-mcp/server/tests/unit/test_domain_models.py
git commit -m "feat: add domain models for connection search results"
```

---

## Task 3: OJP XML request builder

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/__init__.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/__init__.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/xml_builder.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_xml_builder.py`

**Interfaces:**
- Consumes: nothing (pure XML construction).
- Produces: `build_location_information_request(name, requestor_ref, *,
  number_of_results=5, message_identifier=None, timestamp=None) -> bytes`
  and `build_trip_request(origin_ref, destination_ref, requestor_ref, *,
  origin_name="", destination_name="", departure_time=None,
  arrival_time=None, number_of_results=3, message_identifier=None,
  timestamp=None) -> bytes`, both returning UTF-8-encoded XML documents.
  Used by Task 5 (`client.py`).

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_xml_builder.py
import xml.etree.ElementTree as ET

from swiss_grounding_mcp.sources.ojp.xml_builder import (
    OJP_NS,
    SIRI_NS,
    build_location_information_request,
    build_trip_request,
)

NS = {"ojp": OJP_NS, "siri": SIRI_NS}


def test_location_information_request_contains_escaped_name():
    xml_bytes = build_location_information_request(
        "Zürich <HB> & Co",
        "swiss-grounding-mcp",
        number_of_results=5,
        message_identifier="LIR-1",
        timestamp="2026-09-24T12:00:00Z",
    )

    root = ET.fromstring(xml_bytes)
    name_el = root.find(
        ".//ojp:OJPLocationInformationRequest/ojp:InitialInput/ojp:Name", NS
    )
    assert name_el is not None
    assert name_el.text == "Zürich <HB> & Co"

    requestor_ref = root.find(".//siri:ServiceRequest/siri:RequestorRef", NS)
    assert requestor_ref.text == "swiss-grounding-mcp"

    number_of_results = root.find(
        ".//ojp:OJPLocationInformationRequest/ojp:Restrictions/ojp:NumberOfResults", NS
    )
    assert number_of_results.text == "5"


def test_trip_request_contains_origin_destination_and_departure_time():
    xml_bytes = build_trip_request(
        "ch:1:sloid:7000",
        "ch:1:sloid:8503000",
        "swiss-grounding-mcp",
        origin_name="Bern",
        destination_name="Zürich HB",
        departure_time="2026-09-24T18:00:00Z",
        number_of_results=3,
        message_identifier="TR-1",
        timestamp="2026-09-24T12:00:00Z",
    )

    root = ET.fromstring(xml_bytes)
    origin_ref = root.find(
        ".//ojp:OJPTripRequest/ojp:Origin/ojp:PlaceRef/siri:StopPointRef", NS
    )
    assert origin_ref.text == "ch:1:sloid:7000"

    destination_ref = root.find(
        ".//ojp:OJPTripRequest/ojp:Destination/ojp:PlaceRef/siri:StopPointRef", NS
    )
    assert destination_ref.text == "ch:1:sloid:8503000"

    dep_time = root.find(".//ojp:OJPTripRequest/ojp:Origin/ojp:DepArrTime", NS)
    assert dep_time.text == "2026-09-24T18:00:00Z"

    number_of_results = root.find(
        ".//ojp:OJPTripRequest/ojp:Params/ojp:NumberOfResults", NS
    )
    assert number_of_results.text == "3"


def test_trip_request_with_arrival_time_omits_dep_arr_time_on_origin():
    xml_bytes = build_trip_request(
        "ch:1:sloid:7000",
        "ch:1:sloid:8503000",
        "swiss-grounding-mcp",
        arrival_time="2026-09-24T20:00:00Z",
        timestamp="2026-09-24T12:00:00Z",
    )

    root = ET.fromstring(xml_bytes)
    dep_time = root.find(".//ojp:OJPTripRequest/ojp:Origin/ojp:DepArrTime", NS)
    assert dep_time is None

    arr_time = root.find(".//ojp:OJPTripRequest/ojp:Destination/ojp:DepArrTime", NS)
    assert arr_time.text == "2026-09-24T20:00:00Z"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_xml_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.sources'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/__init__.py
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/__init__.py
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/xml_builder.py
from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

OJP_NS = "http://www.vdv.de/ojp"
SIRI_NS = "http://www.siri.org.uk/siri"

ET.register_namespace("", OJP_NS)
ET.register_namespace("siri", SIRI_NS)


def _ojp(tag: str) -> str:
    return f"{{{OJP_NS}}}{tag}"


def _siri(tag: str) -> str:
    return f"{{{SIRI_NS}}}{tag}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_message_identifier(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _service_request_root(requestor_ref: str, timestamp: str) -> tuple[ET.Element, ET.Element]:
    root = ET.Element(_ojp("OJP"), {"version": "2.0"})
    ojp_request = ET.SubElement(root, _ojp("OJPRequest"))
    service_request = ET.SubElement(ojp_request, _siri("ServiceRequest"))
    ET.SubElement(service_request, _siri("RequestTimestamp")).text = timestamp
    ET.SubElement(service_request, _siri("RequestorRef")).text = requestor_ref
    return root, service_request


def _serialize(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_location_information_request(
    name: str,
    requestor_ref: str,
    *,
    number_of_results: int = 5,
    message_identifier: str | None = None,
    timestamp: str | None = None,
) -> bytes:
    timestamp = timestamp or _now_iso()
    root, service_request = _service_request_root(requestor_ref, timestamp)

    lir = ET.SubElement(service_request, _ojp("OJPLocationInformationRequest"))
    ET.SubElement(lir, _siri("RequestTimestamp")).text = timestamp
    ET.SubElement(lir, _siri("MessageIdentifier")).text = (
        message_identifier or _new_message_identifier("LIR")
    )

    initial_input = ET.SubElement(lir, _ojp("InitialInput"))
    ET.SubElement(initial_input, _ojp("Name")).text = name

    restrictions = ET.SubElement(lir, _ojp("Restrictions"))
    ET.SubElement(restrictions, _ojp("Type")).text = "stop"
    ET.SubElement(restrictions, _ojp("NumberOfResults")).text = str(number_of_results)

    return _serialize(root)


def build_trip_request(
    origin_ref: str,
    destination_ref: str,
    requestor_ref: str,
    *,
    origin_name: str = "",
    destination_name: str = "",
    departure_time: str | None = None,
    arrival_time: str | None = None,
    number_of_results: int = 3,
    message_identifier: str | None = None,
    timestamp: str | None = None,
) -> bytes:
    timestamp = timestamp or _now_iso()
    root, service_request = _service_request_root(requestor_ref, timestamp)

    trip_request = ET.SubElement(service_request, _ojp("OJPTripRequest"))
    ET.SubElement(trip_request, _siri("RequestTimestamp")).text = timestamp
    ET.SubElement(trip_request, _siri("MessageIdentifier")).text = (
        message_identifier or _new_message_identifier("TR")
    )

    origin = ET.SubElement(trip_request, _ojp("Origin"))
    origin_place_ref = ET.SubElement(origin, _ojp("PlaceRef"))
    ET.SubElement(origin_place_ref, _siri("StopPointRef")).text = origin_ref
    ET.SubElement(ET.SubElement(origin_place_ref, _ojp("Name")), _ojp("Text")).text = (
        origin_name or origin_ref
    )
    if departure_time is not None:
        ET.SubElement(origin, _ojp("DepArrTime")).text = departure_time

    destination = ET.SubElement(trip_request, _ojp("Destination"))
    destination_place_ref = ET.SubElement(destination, _ojp("PlaceRef"))
    ET.SubElement(destination_place_ref, _siri("StopPointRef")).text = destination_ref
    ET.SubElement(
        ET.SubElement(destination_place_ref, _ojp("Name")), _ojp("Text")
    ).text = (destination_name or destination_ref)
    if departure_time is None and arrival_time is not None:
        ET.SubElement(destination, _ojp("DepArrTime")).text = arrival_time

    params = ET.SubElement(trip_request, _ojp("Params"))
    ET.SubElement(params, _ojp("NumberOfResults")).text = str(number_of_results)
    ET.SubElement(params, _ojp("IncludeIntermediateStops")).text = "false"

    return _serialize(root)
```

Note: when both `departure_time` and `arrival_time` are given, `departure_time`
wins per the Global Constraints — the orchestration layer (Task 7) is
responsible for deciding which one to pass in and for saying so in the
response message; this builder simply emits whichever single time value it's
given.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_xml_builder.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources swiss-grounding-mcp/server/tests/unit/test_xml_builder.py
git commit -m "feat: add OJP 2.0 XML request builder"
```

---

## Task 4: OJP XML response parser

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/xml_parser.py`
- Create: `swiss-grounding-mcp/server/tests/fixtures/ojp/lir_response_single_match.xml`
- Create: `swiss-grounding-mcp/server/tests/fixtures/ojp/lir_response_multi_match.xml`
- Create: `swiss-grounding-mcp/server/tests/fixtures/ojp/lir_response_no_match.xml`
- Create: `swiss-grounding-mcp/server/tests/fixtures/ojp/lir_response_error.xml`
- Create: `swiss-grounding-mcp/server/tests/fixtures/ojp/trip_response_two_trips.xml`
- Test: `swiss-grounding-mcp/server/tests/unit/test_xml_parser.py`

**Interfaces:**
- Consumes: nothing beyond raw XML bytes (decoupled from Task 3 and Task 5).
- Produces: `parse_location_information_response(xml_bytes: bytes) ->
  list[StopCandidate]`, `parse_trip_response(xml_bytes: bytes) ->
  list[Connection]`, and `has_service_delivery_error(xml_bytes: bytes) ->
  str | None` (returns the OJP-reported error message if the response's
  `siri:ServiceDelivery` carries an error element, else `None`). Used by
  Task 5 (`client.py`).

- [ ] **Step 1: Create the fixture files**

```xml
<!-- swiss-grounding-mcp/server/tests/fixtures/ojp/lir_response_single_match.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<OJP version="2.0" xmlns:siri="http://www.siri.org.uk/siri" xmlns="http://www.vdv.de/ojp">
    <OJPResponse>
        <siri:ServiceDelivery>
            <siri:ResponseTimestamp>2026-09-24T17:03:09Z</siri:ResponseTimestamp>
            <siri:ProducerRef>MENTZ</siri:ProducerRef>
            <OJPLocationInformationDelivery>
                <siri:ResponseTimestamp>2026-09-24T17:03:09Z</siri:ResponseTimestamp>
                <siri:RequestMessageRef>LIR-1</siri:RequestMessageRef>
                <CalcTime>2</CalcTime>
                <PlaceResult>
                    <Place>
                        <StopPlace>
                            <StopPlaceRef>ch:1:sloid:7000</StopPlaceRef>
                            <StopPlaceName>
                                <Text xml:lang="de">Bern</Text>
                            </StopPlaceName>
                        </StopPlace>
                        <Name>
                            <Text xml:lang="de">Bern</Text>
                        </Name>
                    </Place>
                    <Complete>true</Complete>
                    <Probability>1</Probability>
                </PlaceResult>
            </OJPLocationInformationDelivery>
        </siri:ServiceDelivery>
    </OJPResponse>
</OJP>
```

```xml
<!-- swiss-grounding-mcp/server/tests/fixtures/ojp/lir_response_multi_match.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<OJP version="2.0" xmlns:siri="http://www.siri.org.uk/siri" xmlns="http://www.vdv.de/ojp">
    <OJPResponse>
        <siri:ServiceDelivery>
            <siri:ResponseTimestamp>2026-09-24T17:03:09Z</siri:ResponseTimestamp>
            <siri:ProducerRef>MENTZ</siri:ProducerRef>
            <OJPLocationInformationDelivery>
                <siri:ResponseTimestamp>2026-09-24T17:03:09Z</siri:ResponseTimestamp>
                <siri:RequestMessageRef>LIR-2</siri:RequestMessageRef>
                <CalcTime>3</CalcTime>
                <PlaceResult>
                    <Place>
                        <StopPlace>
                            <StopPlaceRef>ch:1:sloid:7100</StopPlaceRef>
                            <StopPlaceName>
                                <Text xml:lang="fr">Fribourg/Freiburg</Text>
                            </StopPlaceName>
                        </StopPlace>
                        <Name>
                            <Text xml:lang="fr">Fribourg/Freiburg</Text>
                        </Name>
                    </Place>
                    <Complete>true</Complete>
                    <Probability>0.62</Probability>
                </PlaceResult>
                <PlaceResult>
                    <Place>
                        <StopPlace>
                            <StopPlaceRef>de:1:sloid:1</StopPlaceRef>
                            <StopPlaceName>
                                <Text xml:lang="de">Freiburg(Breisgau) Hbf</Text>
                            </StopPlaceName>
                        </StopPlace>
                        <Name>
                            <Text xml:lang="de">Freiburg(Breisgau) Hbf</Text>
                        </Name>
                    </Place>
                    <Complete>true</Complete>
                    <Probability>0.58</Probability>
                </PlaceResult>
            </OJPLocationInformationDelivery>
        </siri:ServiceDelivery>
    </OJPResponse>
</OJP>
```

```xml
<!-- swiss-grounding-mcp/server/tests/fixtures/ojp/lir_response_no_match.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<OJP version="2.0" xmlns:siri="http://www.siri.org.uk/siri" xmlns="http://www.vdv.de/ojp">
    <OJPResponse>
        <siri:ServiceDelivery>
            <siri:ResponseTimestamp>2026-09-24T17:03:09Z</siri:ResponseTimestamp>
            <siri:ProducerRef>MENTZ</siri:ProducerRef>
            <OJPLocationInformationDelivery>
                <siri:ResponseTimestamp>2026-09-24T17:03:09Z</siri:ResponseTimestamp>
                <siri:RequestMessageRef>LIR-3</siri:RequestMessageRef>
                <CalcTime>1</CalcTime>
            </OJPLocationInformationDelivery>
        </siri:ServiceDelivery>
    </OJPResponse>
</OJP>
```

```xml
<!-- swiss-grounding-mcp/server/tests/fixtures/ojp/lir_response_error.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<OJP version="2.0" xmlns:siri="http://www.siri.org.uk/siri" xmlns="http://www.vdv.de/ojp">
    <OJPResponse>
        <siri:ServiceDelivery>
            <siri:ResponseTimestamp>2026-09-24T17:03:09Z</siri:ResponseTimestamp>
            <siri:ProducerRef>MENTZ</siri:ProducerRef>
            <siri:ErrorCondition>
                <siri:OtherError>
                    <siri:ErrorText>Invalid API token</siri:ErrorText>
                </siri:OtherError>
            </siri:ErrorCondition>
            <OJPLocationInformationDelivery>
                <siri:ResponseTimestamp>2026-09-24T17:03:09Z</siri:ResponseTimestamp>
                <siri:RequestMessageRef>LIR-4</siri:RequestMessageRef>
            </OJPLocationInformationDelivery>
        </siri:ServiceDelivery>
    </OJPResponse>
</OJP>
```

```xml
<!-- swiss-grounding-mcp/server/tests/fixtures/ojp/trip_response_two_trips.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<OJP version="2.0" xmlns:siri="http://www.siri.org.uk/siri" xmlns="http://www.vdv.de/ojp">
    <OJPResponse>
        <siri:ServiceDelivery>
            <siri:ResponseTimestamp>2026-09-24T18:03:12Z</siri:ResponseTimestamp>
            <siri:ProducerRef>MENTZ</siri:ProducerRef>
            <OJPTripDelivery>
                <siri:ResponseTimestamp>2026-09-24T18:03:12Z</siri:ResponseTimestamp>
                <siri:RequestMessageRef>TR-1</siri:RequestMessageRef>
                <TripResponseContext>
                    <Places>
                        <Place>
                            <StopPoint>
                                <siri:StopPointRef>ch:1:sloid:7000:0:1</siri:StopPointRef>
                                <StopPointName>
                                    <Text xml:lang="de">Bern</Text>
                                </StopPointName>
                            </StopPoint>
                        </Place>
                    </Places>
                </TripResponseContext>
                <TripResult>
                    <Id>ID-TRIP-1</Id>
                    <Trip>
                        <Id>ID-TRIP-1</Id>
                        <Duration>PT53M0S</Duration>
                        <StartTime>2026-09-24T18:04:00Z</StartTime>
                        <EndTime>2026-09-24T18:57:00Z</EndTime>
                        <Leg>
                            <Id>1</Id>
                            <Duration>PT53M0S</Duration>
                            <TimedLeg>
                                <LegBoard>
                                    <siri:StopPointRef>ch:1:sloid:7000:0:1</siri:StopPointRef>
                                    <StopPointName>
                                        <Text xml:lang="de">Bern</Text>
                                    </StopPointName>
                                    <ServiceDeparture>
                                        <TimetabledTime>2026-09-24T18:04:00Z</TimetabledTime>
                                    </ServiceDeparture>
                                </LegBoard>
                                <LegAlight>
                                    <siri:StopPointRef>ch:1:sloid:8503000:0:1</siri:StopPointRef>
                                    <StopPointName>
                                        <Text xml:lang="de">Zürich HB</Text>
                                    </StopPointName>
                                    <ServiceArrival>
                                        <TimetabledTime>2026-09-24T18:57:00Z</TimetabledTime>
                                    </ServiceArrival>
                                </LegAlight>
                                <Service>
                                    <Mode>
                                        <PtMode>rail</PtMode>
                                    </Mode>
                                    <PublishedServiceName>
                                        <Text xml:lang="de">IC 8</Text>
                                    </PublishedServiceName>
                                </Service>
                            </TimedLeg>
                        </Leg>
                    </Trip>
                </TripResult>
                <TripResult>
                    <Id>ID-TRIP-2</Id>
                    <Trip>
                        <Id>ID-TRIP-2</Id>
                        <Duration>PT1H43M0S</Duration>
                        <StartTime>2026-09-24T18:34:00Z</StartTime>
                        <EndTime>2026-09-24T20:17:00Z</EndTime>
                        <Leg>
                            <Id>1</Id>
                            <Duration>PT26M0S</Duration>
                            <TimedLeg>
                                <LegBoard>
                                    <siri:StopPointRef>ch:1:sloid:7000:0:2</siri:StopPointRef>
                                    <StopPointName>
                                        <Text xml:lang="de">Bern</Text>
                                    </StopPointName>
                                    <ServiceDeparture>
                                        <TimetabledTime>2026-09-24T18:34:00Z</TimetabledTime>
                                    </ServiceDeparture>
                                </LegBoard>
                                <LegAlight>
                                    <siri:StopPointRef>ch:1:sloid:8500218:0:1</siri:StopPointRef>
                                    <StopPointName>
                                        <Text xml:lang="de">Olten</Text>
                                    </StopPointName>
                                    <ServiceArrival>
                                        <TimetabledTime>2026-09-24T19:00:00Z</TimetabledTime>
                                    </ServiceArrival>
                                </LegAlight>
                                <Service>
                                    <Mode>
                                        <PtMode>rail</PtMode>
                                    </Mode>
                                    <PublishedServiceName>
                                        <Text xml:lang="de">IR 15</Text>
                                    </PublishedServiceName>
                                </Service>
                            </TimedLeg>
                        </Leg>
                        <Leg>
                            <Id>2</Id>
                            <Duration>PT1H17M0S</Duration>
                            <TimedLeg>
                                <LegBoard>
                                    <siri:StopPointRef>ch:1:sloid:8500218:0:2</siri:StopPointRef>
                                    <StopPointName>
                                        <Text xml:lang="de">Olten</Text>
                                    </StopPointName>
                                    <ServiceDeparture>
                                        <TimetabledTime>2026-09-24T19:00:00Z</TimetabledTime>
                                    </ServiceDeparture>
                                </LegBoard>
                                <LegAlight>
                                    <siri:StopPointRef>ch:1:sloid:8503000:0:2</siri:StopPointRef>
                                    <StopPointName>
                                        <Text xml:lang="de">Zürich HB</Text>
                                    </StopPointName>
                                    <ServiceArrival>
                                        <TimetabledTime>2026-09-24T20:17:00Z</TimetabledTime>
                                    </ServiceArrival>
                                </LegAlight>
                                <Service>
                                    <Mode>
                                        <PtMode>rail</PtMode>
                                    </Mode>
                                    <PublishedServiceName>
                                        <Text xml:lang="de">S8</Text>
                                    </PublishedServiceName>
                                </Service>
                            </TimedLeg>
                        </Leg>
                    </Trip>
                </TripResult>
            </OJPTripDelivery>
        </siri:ServiceDelivery>
    </OJPResponse>
</OJP>
```

- [ ] **Step 2: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_xml_parser.py
from pathlib import Path

from swiss_grounding_mcp.sources.ojp.xml_parser import (
    has_service_delivery_error,
    parse_location_information_response,
    parse_trip_response,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ojp"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parse_location_information_single_match():
    candidates = parse_location_information_response(
        _read("lir_response_single_match.xml")
    )

    assert len(candidates) == 1
    assert candidates[0].name == "Bern"
    assert candidates[0].stop_ref == "ch:1:sloid:7000"
    assert candidates[0].probability == 1.0


def test_parse_location_information_multi_match_preserves_order_and_probability():
    candidates = parse_location_information_response(
        _read("lir_response_multi_match.xml")
    )

    assert [c.name for c in candidates] == ["Fribourg/Freiburg", "Freiburg(Breisgau) Hbf"]
    assert candidates[0].probability == 0.62
    assert candidates[1].probability == 0.58


def test_parse_location_information_no_match_returns_empty_list():
    candidates = parse_location_information_response(_read("lir_response_no_match.xml"))

    assert candidates == []


def test_has_service_delivery_error_detects_error_condition():
    message = has_service_delivery_error(_read("lir_response_error.xml"))

    assert message == "Invalid API token"


def test_has_service_delivery_error_returns_none_for_healthy_response():
    message = has_service_delivery_error(_read("lir_response_single_match.xml"))

    assert message is None


def test_parse_trip_response_returns_two_connections_with_legs_and_changes():
    connections = parse_trip_response(_read("trip_response_two_trips.xml"))

    assert len(connections) == 2

    direct = connections[0]
    assert direct.departure == "2026-09-24T18:04:00Z"
    assert direct.arrival == "2026-09-24T18:57:00Z"
    assert direct.duration_minutes == 53
    assert direct.changes == 0
    assert len(direct.legs) == 1
    assert direct.legs[0].line == "IC 8"
    assert direct.legs[0].from_name == "Bern"
    assert direct.legs[0].to_name == "Zürich HB"

    with_change = connections[1]
    assert with_change.duration_minutes == 103
    assert with_change.changes == 1
    assert len(with_change.legs) == 2
    assert with_change.legs[0].line == "IR 15"
    assert with_change.legs[1].line == "S8"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_xml_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.sources.ojp.xml_parser'`.

- [ ] **Step 4: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/xml_parser.py
from __future__ import annotations

import re
from datetime import timedelta

from defusedxml import ElementTree as SafeET

from swiss_grounding_mcp.domain.models import Connection, Leg, StopCandidate
from swiss_grounding_mcp.sources.ojp.xml_builder import OJP_NS, SIRI_NS

NS = {"ojp": OJP_NS, "siri": SIRI_NS}

_ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def _parse_iso_duration_minutes(value: str) -> int:
    match = _ISO_DURATION_RE.match(value)
    if not match:
        return 0
    parts = {k: float(v) if v else 0.0 for k, v in match.groupdict().items()}
    delta = timedelta(
        days=parts["days"],
        hours=parts["hours"],
        minutes=parts["minutes"],
        seconds=parts["seconds"],
    )
    return round(delta.total_seconds() / 60)


def _text_of(element, path: str) -> str | None:
    found = element.find(path, NS)
    return found.text if found is not None else None


def parse_location_information_response(xml_bytes: bytes) -> list[StopCandidate]:
    root = SafeET.fromstring(xml_bytes)
    candidates: list[StopCandidate] = []

    for place_result in root.findall(".//ojp:PlaceResult", NS):
        name = _text_of(place_result, "ojp:Place/ojp:Name/ojp:Text")
        stop_ref = _text_of(place_result, "ojp:Place/ojp:StopPlace/ojp:StopPlaceRef")
        if name is None or stop_ref is None:
            continue

        probability_text = _text_of(place_result, "ojp:Probability")
        probability = float(probability_text) if probability_text is not None else None

        candidates.append(StopCandidate(name=name, stop_ref=stop_ref, probability=probability))

    return candidates


def has_service_delivery_error(xml_bytes: bytes) -> str | None:
    root = SafeET.fromstring(xml_bytes)
    error_text = root.find(
        ".//siri:ServiceDelivery/siri:ErrorCondition//siri:ErrorText", NS
    )
    return error_text.text if error_text is not None else None


def _parse_leg(leg_element) -> Leg | None:
    timed_leg = leg_element.find("ojp:TimedLeg", NS)
    if timed_leg is not None:
        board = timed_leg.find("ojp:LegBoard", NS)
        alight = timed_leg.find("ojp:LegAlight", NS)
        service = timed_leg.find("ojp:Service", NS)

        from_name = _text_of(board, "ojp:StopPointName/ojp:Text") or ""
        to_name = _text_of(alight, "ojp:StopPointName/ojp:Text") or ""
        departure = _text_of(
            board, "ojp:ServiceDeparture/ojp:EstimatedTime"
        ) or _text_of(board, "ojp:ServiceDeparture/ojp:TimetabledTime")
        arrival = _text_of(
            alight, "ojp:ServiceArrival/ojp:EstimatedTime"
        ) or _text_of(alight, "ojp:ServiceArrival/ojp:TimetabledTime")
        mode = _text_of(service, "ojp:Mode/ojp:PtMode") or "unknown"
        line = _text_of(service, "ojp:PublishedServiceName/ojp:Text")

        return Leg(
            mode=mode,
            line=line,
            from_name=from_name,
            to_name=to_name,
            departure=departure,
            arrival=arrival,
        )

    continuous_leg = leg_element.find("ojp:ContinuousLeg", NS)
    if continuous_leg is not None:
        start = continuous_leg.find("ojp:LegStart", NS)
        end = continuous_leg.find("ojp:LegEnd", NS)
        service = continuous_leg.find("ojp:Service", NS)

        from_name = _text_of(start, "ojp:Name/ojp:Text") or ""
        to_name = _text_of(end, "ojp:Name/ojp:Text") or ""
        mode = _text_of(service, "ojp:PersonalMode") or "walk"

        return Leg(mode=mode, line=None, from_name=from_name, to_name=to_name)

    return None


def parse_trip_response(xml_bytes: bytes) -> list[Connection]:
    root = SafeET.fromstring(xml_bytes)
    connections: list[Connection] = []

    for trip_result in root.findall(".//ojp:TripResult", NS):
        trip = trip_result.find("ojp:Trip", NS)
        if trip is None:
            continue

        start_time = _text_of(trip, "ojp:StartTime") or ""
        end_time = _text_of(trip, "ojp:EndTime") or ""
        duration_text = _text_of(trip, "ojp:Duration") or "PT0S"
        duration_minutes = _parse_iso_duration_minutes(duration_text)

        legs = [
            leg
            for leg_element in trip.findall("ojp:Leg", NS)
            if (leg := _parse_leg(leg_element)) is not None
        ]
        timed_leg_count = sum(1 for leg in legs if leg.mode != "walk" and leg.mode != "foot")
        changes = max(0, timed_leg_count - 1)

        connections.append(
            Connection(
                departure=start_time,
                arrival=end_time,
                duration_minutes=duration_minutes,
                changes=changes,
                legs=legs,
            )
        )

    return connections
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_xml_parser.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/xml_parser.py swiss-grounding-mcp/server/tests/fixtures swiss-grounding-mcp/server/tests/unit/test_xml_parser.py
git commit -m "feat: add OJP 2.0 XML response parser with fixtures"
```

---

## Task 5: OJP HTTP client

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/client.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_ojp_client.py`

**Interfaces:**
- Consumes: `Settings` (Task 1); `build_location_information_request`,
  `build_trip_request` (Task 3); `parse_location_information_response`,
  `parse_trip_response`, `has_service_delivery_error` (Task 4);
  `StopCandidate`, `Connection` (Task 2).
- Produces: `class OjpClient` with `__init__(self, settings: Settings)`,
  `location_information(self, name: str) -> list[StopCandidate]`,
  `trip_request(self, origin_ref: str, destination_ref: str, *,
  origin_name: str = "", destination_name: str = "",
  departure_time: str | None = None, arrival_time: str | None = None,
  number_of_results: int = 3) -> list[Connection]`; and
  `class OjpSourceError(Exception)`. Used by Task 7 (`find_connections.py`).

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_ojp_client.py
from pathlib import Path

import httpx
import pytest

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.ojp.client import OjpClient, OjpSourceError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ojp"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _settings() -> Settings:
    return Settings.from_env(
        {"OJP_API_TOKEN": "test-token", "OJP_BASE_URL": "https://example.test/ojp20"}
    )


def _client_with_transport(handler) -> OjpClient:
    transport = httpx.MockTransport(handler)
    client = OjpClient(_settings())
    client._http = httpx.Client(transport=transport)
    return client


def test_location_information_returns_parsed_candidates():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.headers["content-type"] == "application/xml"
        return httpx.Response(200, content=_read("lir_response_single_match.xml"))

    client = _client_with_transport(handler)

    candidates = client.location_information("Bern")

    assert len(candidates) == 1
    assert candidates[0].name == "Bern"


def test_trip_request_returns_parsed_connections():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_read("trip_response_two_trips.xml"))

    client = _client_with_transport(handler)

    connections = client.trip_request("ch:1:sloid:7000", "ch:1:sloid:8503000")

    assert len(connections) == 2


def test_non_2xx_response_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"service unavailable")

    client = _client_with_transport(handler)

    with pytest.raises(OjpSourceError):
        client.location_information("Bern")


def test_embedded_service_delivery_error_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_read("lir_response_error.xml"))

    client = _client_with_transport(handler)

    with pytest.raises(OjpSourceError, match="Invalid API token"):
        client.location_information("Bern")


def test_network_error_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client_with_transport(handler)

    with pytest.raises(OjpSourceError):
        client.location_information("Bern")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_ojp_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.sources.ojp.client'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/client.py
from __future__ import annotations

import httpx

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Connection, StopCandidate
from swiss_grounding_mcp.sources.ojp.xml_builder import (
    build_location_information_request,
    build_trip_request,
)
from swiss_grounding_mcp.sources.ojp.xml_parser import (
    has_service_delivery_error,
    parse_location_information_response,
    parse_trip_response,
)


class OjpSourceError(Exception):
    """Raised when the OJP API cannot be reached or reports a failure."""


class OjpClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.Client(timeout=settings.ojp_timeout_seconds)

    def _post(self, body: bytes) -> bytes:
        headers = {
            "Content-Type": "application/xml",
            "Authorization": f"Bearer {self._settings.ojp_api_token}",
        }
        try:
            response = self._http.post(
                self._settings.ojp_base_url, content=body, headers=headers
            )
        except httpx.HTTPError as exc:
            raise OjpSourceError(f"OJP request failed: {exc}") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise OjpSourceError(
                f"OJP returned HTTP {response.status_code}: {response.text[:200]}"
            )

        error_message = has_service_delivery_error(response.content)
        if error_message is not None:
            raise OjpSourceError(f"OJP reported an error: {error_message}")

        return response.content

    def location_information(self, name: str) -> list[StopCandidate]:
        request_body = build_location_information_request(
            name, self._settings.ojp_requestor_ref
        )
        response_body = self._post(request_body)
        return parse_location_information_response(response_body)

    def trip_request(
        self,
        origin_ref: str,
        destination_ref: str,
        *,
        origin_name: str = "",
        destination_name: str = "",
        departure_time: str | None = None,
        arrival_time: str | None = None,
        number_of_results: int = 3,
    ) -> list[Connection]:
        request_body = build_trip_request(
            origin_ref,
            destination_ref,
            self._settings.ojp_requestor_ref,
            origin_name=origin_name,
            destination_name=destination_name,
            departure_time=departure_time,
            arrival_time=arrival_time,
            number_of_results=number_of_results,
        )
        response_body = self._post(request_body)
        return parse_trip_response(response_body)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_ojp_client.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/sources/ojp/client.py swiss-grounding-mcp/server/tests/unit/test_ojp_client.py
git commit -m "feat: add OJP HTTP client with source-error handling"
```

---

## Task 6: Provenance / citation builder

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/evidence/__init__.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/evidence/provenance.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_provenance.py`

**Interfaces:**
- Consumes: `Settings` (Task 1), `Provenance` (Task 2).
- Produces: `build_provenance(settings: Settings, *, retrieved_at:
  datetime | None = None) -> Provenance`. Used by Task 7.

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_provenance.py
from datetime import datetime, timezone

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.evidence.provenance import build_provenance


def test_build_provenance_uses_source_url_from_settings_and_given_timestamp():
    settings = Settings.from_env({"OJP_BASE_URL": "https://example.test/ojp20"})
    retrieved_at = datetime(2026, 9, 24, 18, 3, 12, tzinfo=timezone.utc)

    provenance = build_provenance(settings, retrieved_at=retrieved_at)

    assert provenance.source == "opentransportdata.swiss OJP 2.0"
    assert provenance.source_url == "https://example.test/ojp20"
    assert provenance.retrieved_at == "2026-09-24T18:03:12Z"


def test_build_provenance_defaults_retrieved_at_to_now():
    settings = Settings.from_env({})

    provenance = build_provenance(settings)

    assert provenance.retrieved_at.endswith("Z")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_provenance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.evidence'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/evidence/__init__.py
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/evidence/provenance.py
from __future__ import annotations

from datetime import datetime, timezone

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Provenance


def build_provenance(settings: Settings, *, retrieved_at: datetime | None = None) -> Provenance:
    timestamp = retrieved_at or datetime.now(timezone.utc)
    return Provenance(
        source="opentransportdata.swiss OJP 2.0",
        source_url=settings.ojp_base_url,
        retrieved_at=timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_provenance.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/evidence swiss-grounding-mcp/server/tests/unit/test_provenance.py
git commit -m "feat: add provenance/citation builder"
```

---

## Task 7: `find_train_connections` orchestration

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/__init__.py`
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/find_connections.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_find_connections.py`

**Interfaces:**
- Consumes: `OjpClient`, `OjpSourceError` (Task 5); `Settings` (Task 1);
  `build_provenance` (Task 6); `ConnectionSearchResult`, `StopCandidate`
  (Task 2).
- Produces: `find_train_connections(origin: str, destination: str,
  departure_time: str | None, arrival_time: str | None, results: int, *,
  client: OjpClient, settings: Settings) -> ConnectionSearchResult`. Used by
  Task 8 (`server.py`).

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_find_connections.py
from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Connection, StopCandidate
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.find_connections import find_train_connections


class StubOjpClient:
    def __init__(self, *, candidates_by_name=None, connections=None, raise_on_trip=None):
        self.candidates_by_name = candidates_by_name or {}
        self.connections = connections if connections is not None else []
        self.raise_on_trip = raise_on_trip
        self.trip_calls = []

    def location_information(self, name):
        return self.candidates_by_name.get(name, [])

    def trip_request(self, origin_ref, destination_ref, **kwargs):
        self.trip_calls.append({"origin_ref": origin_ref, "destination_ref": destination_ref, **kwargs})
        if self.raise_on_trip is not None:
            raise self.raise_on_trip
        return self.connections


def _settings() -> Settings:
    return Settings.from_env({"OJP_BASE_URL": "https://example.test/ojp20"})


def _connection() -> Connection:
    return Connection(
        departure="2026-09-24T18:04:00Z",
        arrival="2026-09-24T18:57:00Z",
        duration_minutes=53,
        changes=0,
        legs=[],
    )


def test_missing_origin_returns_needs_clarification():
    client = StubOjpClient()

    result = find_train_connections(
        "", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert "origin" in result.message.lower()


def test_valid_stations_return_ok_with_provenance():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Bern", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert len(result.connections) == 1
    assert result.provenance.source_url == "https://example.test/ojp20"
    assert client.trip_calls[0]["origin_ref"] == "ch:1:sloid:7000"
    assert client.trip_calls[0]["destination_ref"] == "ch:1:sloid:8503000"


def test_unresolvable_station_returns_not_found():
    client = StubOjpClient(candidates_by_name={"Atlantis": [], "Bern": [
        StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)
    ]})

    result = find_train_connections(
        "Atlantis", "Bern", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "not_found"


def test_genuinely_ambiguous_station_returns_needs_clarification_with_candidates():
    client = StubOjpClient(
        candidates_by_name={
            "Fribourg": [
                StopCandidate(name="Fribourg/Freiburg", stop_ref="ch:1:sloid:7100", probability=0.62),
                StopCandidate(
                    name="Freiburg(Breisgau) Hbf", stop_ref="de:1:sloid:1", probability=0.58
                ),
            ],
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
        }
    )

    result = find_train_connections(
        "Fribourg", "Bern", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert len(result.candidates) == 2


def test_dominant_match_auto_resolves_despite_multiple_candidates():
    # Query matches neither candidate's name exactly, so this exercises the
    # probability-margin branch specifically (not the exact-match branch).
    client = StubOjpClient(
        candidates_by_name={
            "Bern City": [
                StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0),
                StopCandidate(name="Bern, Bümpliz", stop_ref="ch:1:sloid:7062", probability=0.3),
            ],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Bern City", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert client.trip_calls[0]["origin_ref"] == "ch:1:sloid:7000"


def test_accented_and_alternate_names_resolve_without_clarification():
    # Two close-probability candidates (margin 0.05, below the dominant-match
    # threshold) so only the accent/case-insensitive exact-name match can
    # resolve this without asking for clarification.
    client = StubOjpClient(
        candidates_by_name={
            "Geneve": [
                StopCandidate(name="Genève", stop_ref="ch:1:sloid:9000", probability=0.55),
                StopCandidate(
                    name="Genève-Aéroport", stop_ref="ch:1:sloid:9001", probability=0.50
                ),
            ],
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Geneve", "Bern", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert client.trip_calls[0]["origin_ref"] == "ch:1:sloid:9000"


def test_source_error_from_trip_request_returns_source_error_status():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        raise_on_trip=OjpSourceError("OJP returned HTTP 503"),
    )

    result = find_train_connections(
        "Bern", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "source_error"
    assert result.connections == []
    assert "503" in result.message


def test_both_times_given_departure_time_wins_and_message_says_so():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Bern",
        "Zürich HB",
        "2026-09-24T18:00:00Z",
        "2026-09-24T20:00:00Z",
        3,
        client=client,
        settings=_settings(),
    )

    assert result.status == "ok"
    assert client.trip_calls[0]["departure_time"] == "2026-09-24T18:00:00Z"
    assert client.trip_calls[0]["arrival_time"] is None
    assert "departure_time" in result.message


def test_results_parameter_is_clamped_to_valid_range():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    find_train_connections(
        "Bern", "Zürich HB", None, None, 0, client=client, settings=_settings()
    )
    assert client.trip_calls[0]["number_of_results"] == 1

    find_train_connections(
        "Bern", "Zürich HB", None, None, 500, client=client, settings=_settings()
    )
    assert client.trip_calls[1]["number_of_results"] == 5
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_find_connections.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.tools'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/__init__.py
```

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools/find_connections.py
from __future__ import annotations

import unicodedata

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import ConnectionSearchResult, StopCandidate
from swiss_grounding_mcp.evidence.provenance import build_provenance
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError

_DOMINANT_MATCH_MARGIN = 0.3


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.strip().lower()


def _resolve_station(
    query: str, candidates: list[StopCandidate], field_name: str
) -> tuple[StopCandidate | None, ConnectionSearchResult | None]:
    if not candidates:
        return None, ConnectionSearchResult(
            status="not_found",
            message=f"No Swiss station matches {field_name} '{query}'.",
        )

    if len(candidates) == 1:
        return candidates[0], None

    normalized_query = _normalize(query)
    for candidate in candidates:
        if _normalize(candidate.name) == normalized_query:
            return candidate, None

    ranked = sorted(candidates, key=lambda c: c.probability or 0.0, reverse=True)
    best, second = ranked[0], ranked[1]
    if (best.probability or 0.0) - (second.probability or 0.0) >= _DOMINANT_MATCH_MARGIN:
        return best, None

    return None, ConnectionSearchResult(
        status="needs_clarification",
        message=f"Multiple stations match {field_name} '{query}'. Please pick one.",
        candidates=ranked,
    )


def find_train_connections(
    origin: str,
    destination: str,
    departure_time: str | None,
    arrival_time: str | None,
    results: int,
    *,
    client,
    settings: Settings,
) -> ConnectionSearchResult:
    if not origin.strip():
        return ConnectionSearchResult(
            status="needs_clarification", message="Please provide an origin station."
        )
    if not destination.strip():
        return ConnectionSearchResult(
            status="needs_clarification", message="Please provide a destination station."
        )

    clamped_results = max(1, min(5, results))

    origin_candidates = client.location_information(origin)
    resolved_origin, failure = _resolve_station(origin, origin_candidates, "origin")
    if failure is not None:
        return failure

    destination_candidates = client.location_information(destination)
    resolved_destination, failure = _resolve_station(
        destination, destination_candidates, "destination"
    )
    if failure is not None:
        return failure

    effective_departure_time = departure_time
    effective_arrival_time = arrival_time if departure_time is None else None
    time_note = ""
    if departure_time is not None and arrival_time is not None:
        effective_arrival_time = None
        time_note = " Both departure_time and arrival_time were given; departure_time was used."

    try:
        connections = client.trip_request(
            resolved_origin.stop_ref,
            resolved_destination.stop_ref,
            origin_name=resolved_origin.name,
            destination_name=resolved_destination.name,
            departure_time=effective_departure_time,
            arrival_time=effective_arrival_time,
            number_of_results=clamped_results,
        )
    except OjpSourceError as exc:
        return ConnectionSearchResult(status="source_error", message=str(exc))

    if not connections:
        return ConnectionSearchResult(
            status="not_found",
            message=(
                f"No connections found between '{resolved_origin.name}' and "
                f"'{resolved_destination.name}' for the requested time."
            ),
        )

    return ConnectionSearchResult(
        status="ok",
        message=("Connections found." + time_note) if time_note else None,
        connections=connections,
        provenance=build_provenance(settings),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_find_connections.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/tools swiss-grounding-mcp/server/tests/unit/test_find_connections.py
git commit -m "feat: add find_train_connections orchestration with honest statuses"
```

---

## Task 8: MCP server entrypoint

**Files:**
- Create: `swiss-grounding-mcp/server/src/swiss_grounding_mcp/server.py`
- Test: `swiss-grounding-mcp/server/tests/unit/test_server_registration.py`

**Interfaces:**
- Consumes: `Settings` (Task 1); `OjpClient` (Task 5);
  `find_train_connections` (Task 7); `ConnectionSearchResult` (Task 2).
- Produces: module-level `mcp: MCPServer` instance with the
  `find_connections` tool registered; `main() -> None` CLI entrypoint;
  `get_client() -> OjpClient` (a module-level lazy accessor, monkeypatchable
  by tests).

- [ ] **Step 1: Write the failing test**

```python
# swiss-grounding-mcp/server/tests/unit/test_server_registration.py
import asyncio

from mcp import Client

from swiss_grounding_mcp.domain.models import Connection, StopCandidate
from swiss_grounding_mcp.server import mcp
import swiss_grounding_mcp.server as server_module


class StubClient:
    def location_information(self, name):
        return [StopCandidate(name=name, stop_ref=f"ch:1:sloid:{abs(hash(name)) % 9999}", probability=1.0)]

    def trip_request(self, *args, **kwargs):
        return [
            Connection(
                departure="2026-09-24T18:04:00Z",
                arrival="2026-09-24T18:57:00Z",
                duration_minutes=53,
                changes=0,
                legs=[],
            )
        ]


def test_find_connections_tool_is_registered_and_callable(monkeypatch):
    monkeypatch.setattr(server_module, "get_client", lambda: StubClient())

    async def run():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools.tools]
            assert "find_connections" in names

            result = await client.call_tool(
                "find_connections", {"origin": "Bern", "destination": "Zürich HB"}
            )
            assert result.structured_content["status"] == "ok"
            assert len(result.structured_content["connections"]) == 1

    asyncio.run(run())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd swiss-grounding-mcp/server && uv run pytest tests/unit/test_server_registration.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'swiss_grounding_mcp.server'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swiss-grounding-mcp/server/src/swiss_grounding_mcp/server.py
from __future__ import annotations

import argparse

from dotenv import load_dotenv
from mcp.server import MCPServer

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import ConnectionSearchResult
from swiss_grounding_mcp.sources.ojp.client import OjpClient
from swiss_grounding_mcp.tools.find_connections import find_train_connections

load_dotenv()

settings = Settings.from_env()
mcp = MCPServer("Swiss Grounding MCP")

_client: OjpClient | None = None


def get_client() -> OjpClient:
    global _client
    if _client is None:
        _client = OjpClient(settings)
    return _client


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
Expected: PASS (1 test). If the `mcp.Client(mcp)` in-process constructor
signature differs from this snippet in the installed SDK version, check
`uv run python -c "from mcp import Client; help(Client)"` and adjust the
test's `Client(mcp)` call accordingly — the rest of the assertions
(`list_tools`, `call_tool`, `structured_content`) are stable SDK v2 API.

- [ ] **Step 5: Commit**

```bash
git add swiss-grounding-mcp/server/src/swiss_grounding_mcp/server.py swiss-grounding-mcp/server/tests/unit/test_server_registration.py
git commit -m "feat: register find_connections tool on MCPServer with stdio/HTTP entrypoint"
```

---

## Task 9: README, full test run, and manual verification checklist

**Files:**
- Create: `swiss-grounding-mcp/server/README.md`
- Modify: none (this task documents and verifies what Tasks 1–8 built)

**Interfaces:**
- Consumes: everything from Tasks 1–8.
- Produces: nothing new for other tasks to consume; this is the final task.

- [ ] **Step 1: Write the README**

```markdown
# Swiss Grounding MCP — Train Connections Server

An MCP server that answers Swiss passenger-train connection questions using
live data from [OJP 2.0](https://opentransportdata.swiss/en/cookbook/open-journey-planner-ojp-landing-page/)
(`opentransportdata.swiss`, operated under a Federal Office of Transport
mandate).

## Declared scope

- **Topics:** Swiss passenger-train connection lookups between two named
  stations, for a given (optional) date/time.
- **Geography:** all stations reachable via the OJP 2.0 network (all of
  Switzerland).
- **Reference period:** live/current OJP timetable data at query time; no
  historical timetable queries.
- **Out of scope:** fares, departure boards (single-stop next departures),
  disruption/incident feeds, non-rail modes, and every other challenge
  topic area (taxes, health insurance, waste collection, etc). Out-of-scope
  questions get an honest "not covered" response, never a guess.

## Setup

Requires Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).

```bash
cd swiss-grounding-mcp/server
uv venv
uv pip install -e ".[dev]" --group dev
cp .env.example .env
# edit .env and set OJP_API_TOKEN (see "Required credentials" below)
```

## Required credentials

- `OJP_API_TOKEN`: a free API token for OJP 2.0. Register an app and
  subscribe to the "OJP 2.0" product at
  <https://api-manager.opentransportdata.swiss/>. Free tier limits: 50
  requests/minute, 20,000/day.

No other credentials or API keys are required. The server makes no LLM
calls itself.

## Running the server

Local (stdio), for MCP Inspector or a desktop MCP client:

```bash
uv run swiss-grounding-mcp
```

As a network endpoint (Streamable HTTP), reachable at `http://<host>:<port>/mcp`:

```bash
uv run swiss-grounding-mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

## The `find_connections` tool

Input: `origin` (str), `destination` (str), `departure_time` (ISO 8601,
optional — defaults to "now"), `arrival_time` (ISO 8601, optional; ignored
if `departure_time` is also given), `results` (int, default 3, max 5).

Output: a structured object with a `status` of `ok`, `needs_clarification`,
`not_found`, `out_of_scope`, or `source_error`; a human-readable `message`;
`connections` (only for `ok`); `candidates` (only for `needs_clarification`);
and a `provenance` block with source name, URL, and retrieval timestamp
(only for `ok`).

## Configuration

See `.env.example`. `RESPECT_ROBOTS_TXT` (default `true`) is reserved for
future non-API sources this server may add later — the OJP adapter used
today is a licensed, keyed API, not scraped HTML, so this setting has no
effect on it yet.

## Running the checks

```bash
cd swiss-grounding-mcp/server
uv run pytest -v
```

## Manual verification checklist

1. Start the server: `uv run swiss-grounding-mcp`. In another terminal, run
   `uv run mcp dev src/swiss_grounding_mcp/server.py` (MCP Inspector) and
   call `find_connections` with `origin="Bern"`, `destination="Zürich HB"`.
   Confirm a cited `ok` response.
2. Repeat the same call from a second, independent MCP client.
3. Call with an ambiguous station name (e.g. one shared by two cantons) and
   confirm a `needs_clarification` response listing candidates.
4. Temporarily set `OJP_API_TOKEN` to an invalid value (or point
   `OJP_BASE_URL` at an unreachable host) and confirm a `source_error`
   response, not a guessed answer.
5. Ask a question unrelated to travel (e.g. about health insurance premiums)
   and confirm the tool is either not invoked or responds honestly that
   it's out of scope.

## Limitations

- Milestone 1 only; no fares, departure boards, disruption feeds, or
  non-rail modes.
- Station name resolution uses OJP's own fuzzy matching; extremely
  ambiguous or misspelled names may require a follow-up clarification.
```

- [ ] **Step 2: Run the full test suite**

Run: `cd swiss-grounding-mcp/server && uv run pytest -v`
Expected: PASS — all tests from Tasks 1–8 (settings, domain models, xml
builder, xml parser, ojp client, provenance, find_connections,
server registration).

- [ ] **Step 3: Perform the manual verification checklist**

Follow the five steps in the README's "Manual verification checklist"
section above, using a real `OJP_API_TOKEN`. Note the actual result of each
step (pass/fail and what was observed) for the team.

- [ ] **Step 4: Commit**

```bash
git add swiss-grounding-mcp/server/README.md
git commit -m "docs: add README with setup, scope, and verification checklist"
```

---

## Non-Goals (carried from spec §10, not implemented in this plan)

- No LLM calls inside the server.
- No departure-board/single-stop next-departures tool.
- No fares, disruptions, or non-rail modes.
- No LangGraph, Cala AI, Supertext translation, or React/React Flow UI.
