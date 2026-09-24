# Swiss Grounding MCP — Chat Frontend & Agent Backend Design Spec

Status: approved by user on 2026-09-24, ready for implementation planning.

## 1. Purpose and Success Criteria

Give the Swiss Grounding MCP project (train connections + ZRH aviation
tools, in `swiss-grounding-mcp/server/`) a usable frontend: a clean,
Apple-like chat interface, similar in spirit to the Gemini app's empty
state (centered greeting + single pill composer collapsing into a
thread), but that never renders a plain wall of chat text for factual
results. Every tool result becomes a visual widget the user can read and
act on (pick a connection, pick a flight, see a route on a map), with
plain assistant text limited to short summaries, clarifying questions,
and honest "not covered" / error messages.

Success for this milestone:

- A user can type a travel question in the empty-state composer and see
  the UI collapse into a thread showing a widget for the result (train
  connections, station board, fares, disruptions, flight lookup/search,
  airport guidance, or flight-to-train), driven by real calls into the
  existing MCP server's tool functions with real OJP/AeroDataBox data.
- Every one of the tools' non-success statuses (`needs_clarification`,
  `not_found`, `out_of_scope`, `source_error`, `source_unavailable`)
  renders an honest status banner, never a fabricated widget.
- A route/flight result with resolvable station or airport names shows
  a map with origin/destination markers and a connecting line.
- The whole flow runs locally: frontend dev server + new agent backend
  + existing MCP server's tool code (imported directly, not over MCP
  transport) + real OpenAI, OJP, and AeroDataBox credentials.

## 2. Scope

**In scope:** a new agent backend that wires OpenAI tool-calling to the
8 existing tool functions, and a new single-page chat frontend that
renders widgets for every tool's output shape, including all
non-success statuses.

**Out of scope (future work, not this milestone):** an execution-flow
visualization page (React Flow + LangGraph) showing the agent's
tool-call graph as it runs. The user explicitly wants this later; the
design below keeps the backend's tool-dispatch and event-streaming
layers cleanly separated (`tools_registry.py` / `dispatch.py` /
`agent_loop.py`) specifically so a future step-by-step execution trace
can be added without restructuring, but no LangGraph/React Flow code is
written now. Also out of scope: auth, persistence across reloads,
multi-conversation history/sidebar, voice input, and literal rail-track
polylines on the map (only resolved endpoint markers + a straight
connecting line, since OJP/AeroDataBox responses carry station/airport
names, not track geometry).

## 3. Repository Layout

```
swiss-grounding-mcp/
  server/                      # existing MCP server — untouched
  agent-backend/                # NEW
    pyproject.toml              # path dependency on ../server (swiss_grounding_mcp)
    src/agent_backend/
      main.py                   # FastAPI app, CORS, /api/chat SSE endpoint, /api/health
      settings.py                # env-driven: OPENAI_API_KEY, OPENAI_MODEL, CORS origin
      clients.py                  # builds one OjpClient/AerodataboxClient at startup (same pattern as server.py's get_client())
      tools_registry.py          # OpenAI tool-schema defs for all 8 tools, descriptions copied from server.py docstrings
      dispatch.py                 # tool name + args (from the model) -> calls the real tool function
      widget_mapper.py            # tool name + Pydantic result -> {widget_type, status, data} JSON for the frontend
      agent_loop.py               # OpenAI chat-completions tool-calling loop; yields SSE events
      sse.py                       # SSE event formatting helpers
    tests/
      test_dispatch.py
      test_widget_mapper.py
      fixtures/                    # sample ConnectionSearchResult/FlightLookupResult/etc. payloads per status
    .env.example
    README.md
  frontend/                      # NEW
    package.json                  # Vite + React + TypeScript + Tailwind CSS
    src/
      main.tsx
      App.tsx                     # empty-state hero <-> thread view
      components/
        Composer.tsx
        ChatThread.tsx
        AssistantTurn.tsx          # short text line + widget(s)
        widgets/
          TrainConnectionsCard.tsx
          StationBoardCard.tsx
          FaresCard.tsx
          DisruptionsCard.tsx
          FlightCard.tsx            # used for both single lookup and search-list results
          AirportGuidanceCard.tsx
          FlightToTrainCard.tsx
          RouteMap.tsx
          StatusBanner.tsx           # needs_clarification / not_found / out_of_scope / source_error / source_unavailable
      lib/
        sse.ts                       # fetch + ReadableStream SSE parser
        types.ts                     # mirrors backend widget event schema
        geocode.ts                   # Mapbox Geocoding lookups for station/airport names
      styles/                        # Tailwind config, design tokens (Apple-like: type scale, spacing, color)
    .env.example                     # VITE_AGENT_BACKEND_URL, VITE_MAPBOX_TOKEN
    tests/                           # component tests per widget with fixture payloads
```

## 4. Agent Backend Design

### 4.1 Tool reuse (no MCP transport hop)

`agent-backend` depends on `swiss_grounding_mcp` as a local path
dependency (`../server`, editable install) and imports the underlying
tool functions directly — the same functions `server.py` wraps with
`@mcp.tool()`:

- `find_train_connections` (train connections)
- `find_station_disruptions`
- `get_station_board_impl`
- `check_public_transport_fares`
- `find_flight_by_number`
- `search_airport_flights`
- `get_airport_guidance`
- `connect_flight_to_train`

`clients.py` builds one `OjpClient(settings)` and one
`AerodataboxClient(settings)` at startup, exactly mirroring
`server.py`'s `get_client()` / `get_aviation_client()` singletons, using
`Settings.from_env()` from the existing `swiss_grounding_mcp.config.settings`
module. This avoids a second network hop through the MCP
stdio/streamable-http transport and keeps one source of truth for tool
behavior — the agent backend never re-implements OJP/AeroDataBox logic.

### 4.2 Tool schemas and dispatch

`tools_registry.py` declares one OpenAI tool-calling JSON schema per
tool above, with parameter names/types/defaults matching the existing
signatures (documented in `server/README.md`) and descriptions adapted
from each tool's docstring in `server.py`, so the model receives the
same scope guidance (Swiss-only, no fares guessing, no fabricated
flight fields, etc.) that MCP clients already get.

`dispatch.py` maps a tool name + the model's argument dict to a call
into the corresponding function from 4.1, returning the tool's Pydantic
result object. Unknown tool names (should not happen, but defensively)
raise, and the agent loop turns that into a `source_error`-shaped
widget event rather than crashing the request.

### 4.3 Chat endpoint and event protocol

`POST /api/chat` accepts `{"messages": [{"role": "user"|"assistant", "content": "..."}]}`
and returns a `text/event-stream` response driven by `agent_loop.py`:

1. Call OpenAI chat completions with the running message list and the
   full tool schema list, streaming.
2. If the model streams plain text, forward it as
   `{"type": "token", "text": "..."}` events.
3. If the model requests one or more tool calls: for each, call
   `dispatch.py`, convert the Pydantic result via `widget_mapper.py`
   into `{"type": "widget", "tool": "<name>", "status": "<status>", "data": {...}}`,
   emit it immediately (so the widget appears before the model's
   follow-up text), then feed the raw tool result back to OpenAI as a
   tool message and continue the loop for the model's next turn
   (typically a short summary sentence, or another tool call for
   compound requests like "flight then train").
4. Emit `{"type": "done"}` when the model's turn ends with no further
   tool calls.

No persistence: the frontend holds the message list in memory and
resends it each turn (standard stateless chat pattern). No auth — CORS
is restricted to the configured frontend origin via `settings.py`.

### 4.4 Widget mapping (`widget_mapper.py`)

One mapping function per tool, each a pure function from the tool's
Pydantic result to `{widget_type, status, data}`:

| Tool | widget_type | Notes |
|---|---|---|
| `find_connections` | `train_connections` | `data.connections`, `data.candidates` (if `needs_clarification`), `data.provenance` |
| `find_disruptions` | `disruptions` | `data.disruptions`, `data.provenance` |
| `get_station_board` | `station_board` | `data.station_name`, `data.events`, `data.candidates` |
| `check_public_transport_fares` | `fares` | `data.fares`, `data.booking_url` (fallback path), `data.candidates` |
| `find_flight_by_number` | `flight` | `data.flight`, `data.fields_present`/`fields_missing` |
| `search_airport_flights` | `flight_search` | `data.flights[]` |
| `get_airport_guidance` | `airport_guidance` | `data.guidance`, `data.source_url` |
| `connect_flight_to_train` | `flight_to_train` | `data.flight`, `data.train_connections`, both provenance blocks |

Every mapper passes `status` through unchanged from the tool result
(the train/fare tool's `Status` set vs. the aviation tools'
`AviationStatus` set are both forwarded as-is) — the frontend's
`StatusBanner` switches on the exact status string rather than the
backend collapsing them into a generic "error".

## 5. Frontend Design

### 5.1 Visual direction

Apple-like: generous whitespace, soft/layered depth rather than hard
borders, a restrained system-font stack, quiet color (neutral base,
one accent color for interactive/selected states), subtle motion on
state transitions (hero collapse, widget entry) rather than flashy
animation. Built with Tailwind CSS for utility styling and a small set
of shared design tokens (spacing scale, radii, shadow levels, accent
color) so every widget looks like one family, not eight one-off
components.

### 5.2 Empty state → thread

`App.tsx` starts in an empty-state hero (centered greeting text +
single pill `Composer`), matching the reference screenshot's layout
proportions but restyled to the Apple-like direction above (light or
dark — default to a light, airy theme; dark is a follow-up, not
blocking this milestone unless trivial). On the first submitted
message, the hero collapses (animated) and the view becomes a
top-to-bottom scrolling `ChatThread`.

### 5.3 Turn rendering

Each assistant turn (`AssistantTurn.tsx`) renders, in order:

1. A short one- or two-line text summary from the model's streamed
   tokens (kept intentionally brief — the widget carries the
   substance, not a restated paragraph).
2. Zero or more widget cards, one per `widget` event received during
   that turn, in the order they arrived.

This directly satisfies "we don't want a normal chat view with the
agent answer" — prose is a caption, not the answer.

### 5.4 Widget catalog

- **`TrainConnectionsCard`** — one selectable card per connection:
  departure/arrival time, duration, change count, expandable leg list
  (mode/line/from/to/times), citation footer (`provenance.source` +
  link). Selecting a card highlights it and can drive `RouteMap`.
- **`StationBoardCard`** — station name + a compact list of
  departure/arrival events (line, direction, planned/estimated time,
  platform, delay).
- **`FaresCard`** — fare product cards (product, price, class,
  discount) when `status: success`; otherwise a single card with the
  `booking_url` deep link when `status: fallback_link`.
- **`DisruptionsCard`** — list of disruption entries with severity
  badge, affected lines/stops, time window.
- **`FlightCard`** — used for both a single `find_flight_by_number`
  result and a `search_airport_flights` list; each flight is a
  selectable card (airline, flight number, scheduled/estimated/actual
  times, terminal/gate when present, explicit "not reported" for
  fields in `fields_missing` rather than blank space).
- **`AirportGuidanceCard`** — guidance text + citation to the
  `flughafen-zuerich.ch` source URL.
- **`FlightToTrainCard`** — composes `FlightCard` (arrival) +
  `TrainConnectionsCard` (onward trains), each with its own provenance
  footer, plus the computed buffer explanation from `message`.
- **`RouteMap`** — Mapbox GL map. Given the widget's resolved
  place names (origin/destination, or ZRH for aviation-linked trains),
  looks them up via Mapbox Geocoding (`lib/geocode.ts`, client-side,
  `VITE_MAPBOX_TOKEN`), drops markers, and draws a straight connecting
  line labeled with the leg. Geocoding failures degrade gracefully to
  "map unavailable for this location" rather than a broken map.
- **`StatusBanner`** — renders for every non-`ok`/non-`answered`
  status:
  - `needs_clarification` → shows `candidates` as quick-pick chips;
    clicking one resends the clarified value as the next user message.
  - `not_found` / `out_of_scope` / `source_error` /
    `source_unavailable` → a plain honest message from the tool
    result's `message` field, styled distinctly from a normal widget
    (muted, no call-to-action), never inventing a fallback answer.

### 5.5 Data flow

`lib/sse.ts` opens `POST /api/chat`, reads the `ReadableStream`, parses
SSE frames, and dispatches parsed events into React state:
`token` events append to the current turn's summary text; `widget`
events append a widget descriptor (validated against `lib/types.ts`,
which mirrors the backend's event schema) to the current turn; `done`
finalizes the turn and re-enables the composer.

## 6. Configuration

`agent-backend/.env.example`:

```
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
AGENT_BACKEND_HOST=127.0.0.1
AGENT_BACKEND_PORT=8080
CORS_ALLOWED_ORIGIN=http://localhost:5173
```

The OJP and AeroDataBox credentials are **not duplicated**: the backend
loads `swiss-grounding-mcp/server/.env` (via the same `Settings.from_env()`
mechanism, pointed at that file) so there is one place those
credentials live.

`frontend/.env.example`:

```
VITE_AGENT_BACKEND_URL=http://127.0.0.1:8080
VITE_MAPBOX_TOKEN=
```

Both example files list names only; the user provides real values
locally.

## 7. Error Handling

- Every backend failure path (OpenAI API error, tool exception, dispatch
  of an unknown tool name) produces a `source_error`-shaped widget event
  plus a short apologetic `token` summary — never a raw stack trace or a
  silently dropped request. The SSE stream always ends with `done`.
- The frontend's `sse.ts` treats a dropped/failed connection as an
  implicit `source_error` widget with a retry affordance on the
  composer.
- Widgets never render partial/guessed data: any field absent from the
  tool result (e.g., `fields_missing` on a flight) is shown as an
  explicit "not reported by source" rather than omitted or blanked,
  consistent with the MCP server's own honesty requirements.

## 8. Testing and Verification

**Backend (no live OpenAI/OJP/AeroDataBox calls in unit tests):**

- `test_dispatch.py`: each of the 8 tool names routes to the correct
  function with correctly forwarded arguments (mock the underlying
  tool functions).
- `test_widget_mapper.py`: for each tool, fixture Pydantic results
  covering every status value in its status set map to the expected
  `{widget_type, status, data}` shape.

**Frontend:**

- Component-level tests per widget, rendered against fixture payloads
  captured from the backend fixtures above, including every
  non-success status for `StatusBanner`.

**Manual verification (documented in `agent-backend/README.md` and
`frontend/README.md`):**

1. Start `server`'s dependencies are satisfied (`OJP_API_TOKEN`,
   `AERODATABOX_API_KEY` already configured per `server/README.md`).
2. Start `agent-backend` (`uv run uvicorn agent_backend.main:app`) and
   `frontend` (`npm run dev`); open the frontend.
3. Ask a real train-connection question; confirm the hero collapses,
   a `TrainConnectionsCard` and `RouteMap` render, and the citation
   footer links to `opentransportdata.swiss`.
4. Ask with an ambiguous station name; confirm `StatusBanner`
   clarification chips appear and clicking one resolves the query.
5. Ask a flight-number question; confirm `FlightCard` renders with
   `fields_missing` handled explicitly.
6. Ask an out-of-scope question (e.g., about taxes); confirm an honest
   `StatusBanner`, no fabricated widget.
7. Temporarily break `OJP_API_TOKEN`; confirm a `source_error`
   `StatusBanner`, not a crash or a guessed answer.
8. Run an `impeccable audit`/`polish` pass on the built frontend before
   calling the UI done.

## 9. Non-Goals

- No LangGraph or React Flow execution-visualization page in this
  milestone — explicitly deferred future work; the backend's layering
  (`tools_registry` / `dispatch` / `agent_loop` as separate modules) is
  chosen so that page can be added later without restructuring this
  code.
- No auth, no persistence across reloads, no multi-conversation
  sidebar, no voice input.
- No literal rail-track polyline on the map — endpoint markers and a
  straight connecting line only.
- No changes to `swiss-grounding-mcp/server/` itself.
