# Swiss Grounding MCP — Design Spec (Milestone 1: Train Connections)

Status: approved by user on 2026-09-24, ready for implementation planning.

## 1. Purpose and Success Criteria

Build an MCP server for the Swisscom myAI "Swiss Grounding MCP" challenge
(Swiss AI Weeks 2026, Zurich hackathon). The server must let a standard MCP
client, driven by an LLM, answer questions about Swiss passenger-train
connections with authoritative, cited, current data — and must say so
honestly when it cannot.

Success for milestone 1:

- A documented `start` command boots the server locally (stdio) and as a
  network endpoint (Streamable HTTP).
- MCP Inspector and at least one independent MCP client can list and call
  the one exposed tool.
- The tool correctly handles: a valid connection question, a question
  needing clarification (ambiguous station), a simulated source failure,
  and an out-of-scope question — each with an honest, structured response.
- Every successful answer carries a source citation and retrieval
  timestamp.

## 2. Declared Scope (for README)

**Topics:** Swiss passenger-train connection lookups between two named
stations/stops, for a given (optional) date/time.

**Geography:** All stations reachable via the OJP 2.0 network (all of
Switzerland; cross-border stations that OJP resolves are incidentally
covered, but not a declared guarantee).

**Explicitly out of scope for milestone 1:** fares, departure boards
(single-stop next-departures), disruption/incident feeds, non-rail modes,
any of the other 15 challenge topic areas (taxes, health insurance, waste
collection, etc). Out-of-scope questions get an honest "not covered"
response, never a guess.

**Reference period:** live/current OJP timetable data at query time; no
historical timetable queries.

## 3. Data Source: OJP 2.0 (verified)

- Provider: `opentransportdata.swiss`, operated under a Federal Office of
  Transport (FOT/BAV) mandate — semi-official authoritative source, and
  explicitly listed as the example source for the "public transport and
  mobility" topic area in the challenge README.
- Protocol: XML request/response over a single POST endpoint (not a
  REST/JSON API). Endpoint: `https://api.opentransportdata.swiss/ojp20`.
- Required headers: `Content-Type: application/xml`,
  `Authorization: Bearer <token>`.
- Auth: a free API token obtained by registering an app at
  `api-manager.opentransportdata.swiss` and subscribing to the "OJP 2.0"
  product. No payment needed at hackathon volume.
- Rate limits: 50 requests/minute, 20,000 requests/day per token (free
  tier) — ample for a demo; the client wraps calls so limit errors surface
  as `source_error`, not a crash.
- Services used:
  - `OJPLocationInformationRequest` — resolve free-text station names
    (e.g. "Bern", "Lugano") to stop refs (`siri:StopPointRef`), or confirm
    an already-known stop ref.
  - `OJPTripRequest` — compute connections between an `Origin` and
    `Destination`, each a `PlaceRef`, with an optional `DepArrTime`.
- Terms of use: attribution to `opentransportdata.swiss` required in any
  publication/analysis using the data; this is satisfied by including the
  source name/URL in every citation this server returns. No robots.txt
  applies — this is a licensed, keyed API, not scraped HTML.

## 4. Repository Layout

Implementation lives at `swiss-grounding-mcp/server/`, alongside the
existing challenge material (`README.md`, `AGENTS.md`,
`briefing-swiss-grounding-mcp.pdf`) in that folder.

```
swiss-grounding-mcp/server/
  src/swiss_grounding_mcp/
    server.py                # MCP server entrypoint; registers tools; stdio + Streamable HTTP transport
    tools/
      find_connections.py    # the one tool: orchestrates resolve -> query -> format
    sources/ojp/
      client.py              # HTTP call, auth header, timeout, error mapping
      xml_builder.py         # builds LIR & TripRequest XML bodies (escaped via a real XML builder, not raw string interpolation)
      xml_parser.py          # parses LIR & TripRequest XML responses into domain models
    domain/
      models.py              # Station, Connection, Leg, ToolResult, Status enum
    evidence/
      provenance.py          # builds citation blocks: source name/url, retrieved_at, requestor ref
      status.py              # Status enum + helpers: ok / needs_clarification / not_found / out_of_scope / source_error
    config/
      settings.py            # env-driven config: OJP_API_TOKEN, OJP_BASE_URL, OJP_REQUESTOR_REF, timeouts, RESPECT_ROBOTS_TXT, HTTP host/port
  tests/
    unit/                     # xml_builder, xml_parser, status/clarification logic — fixture-based, no live network calls
    fixtures/ojp/             # sample LIR/TripRequest request & response XML (captured from public OJP docs/API Explorer)
  .env.example
  README.md                  # setup, declared scope, limitations, credentials, how to run checks
  pyproject.toml
```

Ownership split for a 3-person team, after the plan is approved:

- Person A: `sources/ojp/` (client, xml_builder, xml_parser) + its unit
  tests/fixtures.
- Person B: `tools/`, `domain/`, `evidence/` (orchestration, status logic,
  citations) + its unit tests.
- Person C: `server.py`, `config/`, `.env.example`, README, and
  integration/manual verification (MCP Inspector + second client).

## 5. Tool Contract

One tool exposed: `find_train_connections`.

**Input parameters:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `origin` | string | yes | Free-text station name or an OJP stop ref. |
| `destination` | string | yes | Same as `origin`. |
| `departure_time` | string (ISO 8601) | no | Defaults to "now" if omitted and `arrival_time` is also omitted. |
| `arrival_time` | string (ISO 8601) | no | If both `departure_time` and `arrival_time` are given, `departure_time` takes precedence and the response says so. |
| `results` | integer | no | Default 3, max 5. |

The tool's MCP description explicitly states its scope (Swiss passenger
rail/PT connections only, current live timetable, no fares/disruptions/
departure boards) so a capable client/LLM can self-select correctly on
out-of-scope questions before ever calling it.

**Output shape (always structured, always carries a status):**

```json
{
  "status": "ok | needs_clarification | not_found | out_of_scope | source_error",
  "message": "human-readable explanation; populated for every non-ok status, optional for ok",
  "connections": [
    {
      "departure": "2026-09-24T18:04:00Z",
      "arrival": "2026-09-24T19:47:00Z",
      "duration_minutes": 103,
      "changes": 1,
      "legs": [
        {
          "mode": "rail",
          "line": "IC 8",
          "from": "Bern",
          "to": "Zürich HB",
          "departure": "2026-09-24T18:04:00Z",
          "arrival": "2026-09-24T18:57:00Z"
        }
      ]
    }
  ],
  "candidates": [
    {"name": "Freiburg im Breisgau Hbf", "stop_ref": "..."},
    {"name": "Fribourg/Freiburg", "stop_ref": "..."}
  ],
  "provenance": {
    "source": "opentransportdata.swiss OJP 2.0",
    "source_url": "https://api.opentransportdata.swiss/ojp20",
    "retrieved_at": "2026-09-24T18:03:12Z"
  }
}
```

`connections` is populated only for `status: ok`. `candidates` is
populated only for `status: needs_clarification`.

## 6. Control Flow

1. Validate inputs. Missing `origin` or `destination` -> `needs_clarification`
   asking for exactly the missing field (per the challenge's guidance that a
   precise request for missing context counts as correct).
2. Resolve `origin` and `destination`:
   - If the string already looks like a known stop ref format, skip
     resolution.
   - Otherwise call `OJPLocationInformationRequest` with `Type=stop`.
     - Zero results -> `not_found` (covers non-Swiss or nonexistent
       places — this is also the primary out-of-scope detector for
       geography).
     - One clearly best result (exact or unambiguous case-insensitive
       name match) -> use it.
     - Multiple plausible results -> `needs_clarification`, returning the
       candidate list (name + stop ref) for origin and/or destination,
       whichever was ambiguous.
3. Build `OJPTripRequest` XML with resolved stop refs and the
   requested/default time.
4. POST to the OJP endpoint.
   - Network error, timeout, non-2xx, or unparsable XML -> `source_error`
     with the underlying reason (never fabricate an answer).
   - OJP-level error element in an otherwise-2xx response -> `source_error`
     with the OJP-reported message.
5. Parse the `OJPTripResponse` into `Connection`/`Leg` domain models.
6. Build the `provenance` block (source name/url, `retrieved_at` =
   wall-clock time of the successful response).
7. Return `status: ok` with `connections` and `provenance`.

Out-of-scope questions unrelated to travel (e.g. a tax question) are
primarily handled by the tool's description steering the client/LLM away
from calling it at all; if called anyway with nonsensical input, step 2's
`not_found` path is the fallback honest response.

## 7. Configuration

`.env.example` (no secrets committed):

```
OJP_API_TOKEN=
OJP_BASE_URL=https://api.opentransportdata.swiss/ojp20
OJP_REQUESTOR_REF=swiss-grounding-mcp
OJP_TIMEOUT_SECONDS=10
RESPECT_ROBOTS_TXT=true
MCP_HTTP_HOST=127.0.0.1
MCP_HTTP_PORT=8000
```

`RESPECT_ROBOTS_TXT` is plumbed through `config/settings.py` now, default
`true`, and documented in the README as applying to any future
non-API/scraping-based source; it is not consulted by the OJP adapter
(a licensed, keyed API, not scraped HTML), and the README says so
explicitly to avoid a misleading impression of dead configuration.

## 8. Transport

Built on MCP Python SDK v2. `server.py` registers the single tool and
starts both:

- stdio transport, for MCP Inspector and desktop MCP clients.
- Streamable HTTP transport, for a network-reachable deployment.

Both transports share the same tool implementation; no duplicated logic.

## 9. Testing and Verification

**Unit tests (no live network calls):**

- `xml_builder`: given known inputs, produces correctly structured and
  escaped LIR/TripRequest XML.
- `xml_parser`: given fixture response XML (captured from the public OJP
  cookbook/API Explorer documentation), produces the expected domain
  models — including a fixture for zero-result and multi-result LIR
  responses, to test the clarification path.
- `status`/orchestration logic: missing-input, ambiguous-station,
  not-found, and source-error paths all return the correct `status` and
  never populate `connections` on non-ok paths.

**Manual verification (documented as a checklist in the README):**

1. Start the server (stdio) and connect MCP Inspector; list tools; call
   `find_train_connections` with a valid origin/destination and confirm a
   cited, structured `ok` response.
2. Repeat with a second, independent MCP client.
3. Trigger the clarification path (ambiguous station name).
4. Trigger a source failure (e.g. temporarily invalid token or unreachable
   base URL via config) and confirm an honest `source_error`, not a
   guess.
5. Ask an out-of-scope question (e.g. about health insurance) and confirm
   the tool is either not called or returns an honest out-of-scope-style
   `not_found`/description-driven refusal.

## 10. Non-Goals for Milestone 1

- No LLM calls inside the server (keeps the server free of extra API keys
  and improves operability score).
- No departure-board/single-stop next-departures tool (explicitly
  deferred).
- No fares, disruptions, or non-rail modes.
- No LangGraph, Cala AI, Supertext translation, or React/React Flow UI —
  future milestones, out of scope here. The layered module boundaries
  (protocol layer vs. source adapter vs. evidence logic vs. config) are
  chosen so these can be added later without restructuring.
