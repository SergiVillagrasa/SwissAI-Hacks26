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
