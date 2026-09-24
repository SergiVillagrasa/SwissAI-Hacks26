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
