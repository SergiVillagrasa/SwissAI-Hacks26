# Deploying to Railway

This project deploys as **three independent Railway services**, all built
from Dockerfiles in this repository. They don't share a network at
runtime — the frontend talks to the agent backend over its public HTTPS
URL, and the MCP server is a standalone endpoint for MCP clients (it is
not called by the agent backend, which imports the same tool functions
in-process; see `agent-backend/README.md`).

| Service | Root Directory | Dockerfile Path | Config file |
| --- | --- | --- | --- |
| `mcp-server` | `swiss-grounding-mcp/server` | `Dockerfile` | `swiss-grounding-mcp/server/railway.json` |
| `agent-backend` | `swiss-grounding-mcp` | `agent-backend/Dockerfile` | `swiss-grounding-mcp/railway.json` |
| `frontend` | `swiss-grounding-mcp/frontend` | `Dockerfile` | `swiss-grounding-mcp/frontend/railway.json` |

`agent-backend`'s Root Directory must be the **parent** folder
(`swiss-grounding-mcp`), not `agent-backend/` itself: the service depends
on the MCP server's tool functions via an editable path dependency
(`../server`), so the build context needs both folders side by side.

All three services already listen on Railway's injected `PORT` (see each
service's `CMD`/entrypoint), so no extra configuration is needed for
that.

## 1. `mcp-server` (Streamable HTTP MCP endpoint)

Set these variables on the service (see `server/.env.example` for the
full list; only set what the tools you need require):

- `OJP_API_TOKEN` — required for train tools.
- `AERODATABOX_API_KEY` — required for the aviation tools.
- `SERPAPI_API_KEY` — required for `get_flight_fares`.
- `OJP_BASE_URL`, `OJP_FARE_URL`, `RESPECT_ROBOTS_TXT`,
  `TRIP_TIME_MARGIN_MINUTES`, etc. — optional, defaults match
  `.env.example`.

Do **not** set `MCP_HTTP_HOST`/`MCP_HTTP_PORT`; the container's `CMD`
already binds `0.0.0.0:$PORT`. Once deployed, the MCP endpoint is at
`https://<railway-domain>/mcp`.

## 2. `agent-backend` (FastAPI chat service)

Set:

- `OPENAI_API_KEY` (required — without it `/api/chat` degrades to a
  clean "assistant unavailable" response instead of crashing).
- `OJP_API_TOKEN`, `AERODATABOX_API_KEY`, `SERPAPI_API_KEY` — same keys
  as the MCP server; this service loads `swiss_grounding_mcp` settings
  independently and does not read them from the other service.
- `CORS_ALLOWED_ORIGIN` — set to the deployed frontend's public URL
  (e.g. `https://frontend-production-xxxx.up.railway.app`) once you know
  it. Comma-separate multiple origins.
- `CORS_ALLOW_ANY_LOCAL_PORT=false` — the `true` default is meant for
  local dev (it allow-lists any `localhost`/`127.0.0.1` port); turn it
  off for a public deployment.
- `OPENAI_MODEL`, `OPENAI_TRANSCRIBE_MODEL`, `OPENAI_TTS_MODEL`,
  `OPENAI_TTS_VOICE` — optional overrides.

Health check: `GET /api/health`.

## 3. `frontend` (static SPA via nginx)

Vite inlines `VITE_*` variables at **build time**, so these must be set
as service variables before the image is built (Railway forwards
matching variables as Docker build args automatically since the
Dockerfile declares `ARG VITE_AGENT_BACKEND_URL` / `ARG
VITE_MAPBOX_TOKEN`):

- `VITE_AGENT_BACKEND_URL` — the `agent-backend` service's public URL
  (e.g. `https://agent-backend-production-xxxx.up.railway.app`).
- `VITE_MAPBOX_TOKEN` — a Mapbox access token for the route map widget.

## Suggested deployment order

1. Deploy `mcp-server` and `agent-backend` first (with their API keys)
   and note `agent-backend`'s public URL.
2. Deploy `frontend` with `VITE_AGENT_BACKEND_URL` set to that URL.
3. Set `agent-backend`'s `CORS_ALLOWED_ORIGIN` to the `frontend` service's
   public URL and redeploy `agent-backend` so the browser can call it.

## Verifying locally before pushing

Each Dockerfile can be built and run standalone to catch issues before
deploying:

```sh
# MCP server
docker build -t swiss-mcp-server swiss-grounding-mcp/server
docker run --rm -p 8000:8000 -e PORT=8000 swiss-mcp-server

# Agent backend (note the build context: the parent folder)
docker build -t swiss-agent-backend -f swiss-grounding-mcp/agent-backend/Dockerfile swiss-grounding-mcp
docker run --rm -p 3001:3001 -e PORT=3001 -e OPENAI_API_KEY=sk-... swiss-agent-backend

# Frontend
docker build -t swiss-frontend swiss-grounding-mcp/frontend \
  --build-arg VITE_AGENT_BACKEND_URL=http://localhost:3001
docker run --rm -p 8080:8080 -e PORT=8080 swiss-frontend
```
