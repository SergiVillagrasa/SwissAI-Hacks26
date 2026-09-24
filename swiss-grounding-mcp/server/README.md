# Swiss Grounding MCP — Train Connections & ZRH Aviation Server

An MCP server that answers Swiss passenger-train connection questions using
live data from [OJP 2.0](https://opentransportdata.swiss/en/cookbook/open-journey-planner-ojp-landing-page/)
(`opentransportdata.swiss`, operated under a Federal Office of Transport
mandate), and Zurich Airport (ZRH) flight and passenger-guidance questions
using [Aviationstack](https://aviationstack.com/) and official Zurich
Airport (`flughafen-zuerich.ch`) pages.

## Declared scope

**Train connections:**

- **Topics:** Swiss passenger-train connection lookups between two named
  stations, and departure/arrival boards at a named stop, for a given
  (optional) date/time.
- **Geography:** all stations reachable via the OJP 2.0 network (all of
  Switzerland), plus cross-border journeys where at least one end of the
  route is a Swiss station (e.g. Paris→Genève or Zürich→Milan). Purely
  foreign routes with no Swiss end are refused.
- **Reference period:** live/current OJP timetable data at query time; no
  historical timetable queries.
- **Out of scope:** fares, non-public-transit topics, and every other
  challenge topic area (taxes, health insurance, waste collection, etc).
  Out-of-scope questions get an honest "not covered" response, never a
  guess. Current disruptions affecting a station *are* covered — see
  `find_disruptions` below.
- **Scope enforcement:** OJP 2.0 also indexes non-Swiss stops, which keeps
  legitimate cross-border journeys working. Both ends are resolved first;
  only when *neither* stop reference carries the Swiss `ch:` DiDok/SLOID
  prefix (or a Swiss `85xxxxx` UIC number) is the route refused with
  status `out_of_scope` before any trip request — purely foreign routes
  (e.g. Paris→Marseille, Berlin→Hamburg) are never answered.

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
  `flughafen-zuerich.ch` pages, not scraped live.

**Out of scope (both modules):** fares, departure boards beyond what's
described above, visas/immigration rules, airline-specific policies,
non-Swiss/non-ZRH topics, and every other challenge topic area (taxes,
health insurance, waste collection, etc). Out-of-scope questions get an
honest response, never a guess.

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
- `AVIATIONSTACK_API_KEY`: an API key for [Aviationstack](https://aviationstack.com/).
  Sign up for the free plan (~100–500 requests/month, personal-use
  license) or a paid plan for higher volume and a commercial license.
  Without this key, the aviation flight-lookup and flight-search tools
  return `source_unavailable`; the airport-guidance tool still works
  (it uses static, pre-written content, not a live API call).

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

## The `get_station_board` tool

Input: `station` (str), `mode` (`"departures"` default or `"arrivals"`),
`when` (ISO 8601, optional — defaults to now), `results` (int, default 5,
max 10).

Output: same status set as `find_connections`; on `ok`, a `station_name`,
`event_type`, and a list of `events` with `line`, `mode`,
`direction_name` (destination for departures, origin for arrivals),
`planned_time`, `estimated_time`, `platform`, `delay_minutes`, plus the
`provenance` block. Foreign stations are refused as `out_of_scope`;
departure boards exist only for the Swiss network.

## The `find_disruptions` tool

Input: `stop` (str).

Output: same status set as `find_connections`; on `ok`, a list of
`disruptions` with `id`, `title`, `description`, `severity`, `start_time`,
`end_time`, `status`, `affected_lines`, and `affected_stops`, plus the
`provenance` block. Uses current real-time OJP 2.0 stop-event information
to surface cancellations, delays, and boarding/alighting restrictions
affecting services at the requested station.

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
