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
uv run uvicorn agent_backend.main:app --reload --port 3001
```

Or, from the repository root: `make dev-api` / `npm run dev:api`.

## Endpoints

- `GET /api/health` — liveness check. Reports `openai_configured` so a
  missing or invalid `OPENAI_API_KEY` degrades cleanly instead of
  crashing the service at startup.
- `POST /api/chat` — `{"messages": [{"role": "user", "content": "..."}]}`,
  returns a `text/event-stream` containing the existing `token`, `widget`, and
  `done` events plus sanitized `run_*`, `node_*`, and `tool_*` workflow events.
  Clients may safely ignore event types they do not recognize. See the design spec at
  `docs/superpowers/specs/2026-09-24-swiss-grounding-mcp-frontend-design.md`
  for the full event/widget schema.

## Running the checks

```bash
uv run pytest -v
```
