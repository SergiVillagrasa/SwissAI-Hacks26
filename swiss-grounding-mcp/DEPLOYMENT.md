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
- `MCP_AUTH_TOKEN` — required for public binds. For an open judging
  endpoint, set `MCP_ALLOW_UNAUTHENTICATED=true`; the request rate limit
  still applies.
- `MCP_RATE_LIMIT_PER_MINUTE` — per-client request limit (default `60`;
  `0` disables it).
- `MCP_ALLOWED_HOSTS` — optional, comma-separated allowed `Host` values.
  When unset on a public bind, no Host check is applied (the bearer token
  is the access control). When set, the MCP SDK rejects any request whose
  `Host` header is not listed, so confirm the Host your proxy forwards
  (e.g. the public Railway hostname) before enabling it.
- `MCP_ALLOWED_ORIGINS` — ignored unless `MCP_ALLOWED_HOSTS` is set.
  When enabled, this is the comma-separated browser Origin allowlist;
  requests from unlisted origins are rejected.
- `MCP_CLIENT_IP_HEADER` — optional trusted client-IP header. Leave it
  empty to key limits on the TCP peer address. Set it only when every
  request reaches the service through a proxy that overwrites the header;
  otherwise clients can spoof it to get around per-client limits. On
  Railway, check that the edge overwrites a client-supplied `X-Real-IP`
  before relying on it. Behind Railway's edge, leaving this empty makes
  every client share the proxy IP, so the per-client limit becomes one
  service-wide limit (60 requests per minute by default).
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
- `AGENT_BACKEND_API_KEY` — bearer key required for the three chat and
  voice POST routes when configured; keep it the same as the frontend
  build variable.
- `AGENT_RATE_LIMIT_PER_MINUTE` — per-client request limit (default `30`;
  `0` disables it).
- `AGENT_DAILY_REQUEST_LIMIT` — global rolling daily cap; default `0`
  disables it. A starting budget such as `2000` requests/day is
  recommended.
- `AGENT_MAX_OUTPUT_TOKENS` — maximum completion tokens generated for a
  model response (default `1024`); set to `0` or less to disable the cap.
- `AGENT_CLIENT_IP_HEADER` — optional trusted client-IP header. Leave it
  empty to key limits on the TCP peer address. Set it only when every
  request reaches the service through a proxy that overwrites the header;
  otherwise clients can spoof it to get around per-client limits. On
  Railway, check that the edge overwrites a client-supplied `X-Real-IP`
  before relying on it. Behind Railway's edge, leaving this empty makes
  every client share the proxy IP, so the per-client limit becomes one
  service-wide limit (30 requests per minute by default).
- `MAX_AUDIO_UPLOAD_BYTES` — maximum uploaded audio bytes (default
  `10485760`, or 10 MiB).
- `OJP_API_TOKEN`, `AERODATABOX_API_KEY`, `SERPAPI_API_KEY` — same keys
  as the MCP server; this service loads `swiss_grounding_mcp` settings
  independently and does not read them from the other service.
- `CORS_ALLOWED_ORIGIN` — set to the deployed frontend's public URL
  (e.g. `https://frontend-production-xxxx.up.railway.app`) once you know
  it. Comma-separate multiple origins.
- `CORS_ALLOW_ANY_LOCAL_PORT` defaults to `false`. Set it to `true` only
  for local development when arbitrary `localhost`/`127.0.0.1` ports are
  needed.
- `OPENAI_MODEL`, `OPENAI_TRANSCRIBE_MODEL`, `OPENAI_TTS_MODEL`,
  `OPENAI_TTS_VOICE` — optional overrides.

Health check: `GET /api/health`.

## 3. `frontend` (static SPA via nginx)

Vite inlines `VITE_*` variables at **build time**, so these must be set
as service variables before the image is built (Railway forwards
matching variables as Docker build args automatically since the
Dockerfile declares the corresponding `ARG` values):

- `VITE_AGENT_BACKEND_URL` — the `agent-backend` service's public URL
  (e.g. `https://agent-backend-production-xxxx.up.railway.app`).
- `VITE_AGENT_BACKEND_API_KEY` — sent as a bearer key to the backend.
  A key bundled into a public SPA is visible to every visitor, so it
  deters drive-by use but is not a secret. Rate and daily request limits,
  plus an OpenAI dashboard spend cap, are the actual cost controls.
- `VITE_MAPBOX_TOKEN` — use a public `pk.` Mapbox token with URL
  restrictions configured in the Mapbox dashboard. The build rejects
  secret `sk.` tokens.

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
