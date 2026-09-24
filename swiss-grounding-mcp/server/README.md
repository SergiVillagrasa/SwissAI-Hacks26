# Swiss Grounding MCP — Train Connections & ZRH Aviation Server

An MCP server that answers Swiss passenger-train connection questions using
live data from [OJP 2.0](https://opentransportdata.swiss/en/cookbook/open-journey-planner-ojp-landing-page/)
(`opentransportdata.swiss`, operated under a Federal Office of Transport
mandate), and Zurich Airport (ZRH) flight and passenger-guidance questions
using [AeroDataBox](https://aerodatabox.com/) (via RapidAPI) and official
Zurich Airport (`flughafen-zuerich.ch`) pages.

## Declared scope

**Train connections:**

- **Topics:** Swiss passenger-train connection lookups between two named
  stations, departure/arrival boards at a named stop, and fare lookups for
  Swiss domestic routes, all for a given (optional) date/time.
- **Geography:** all stations reachable via the OJP 2.0 network (all of
  Switzerland), plus cross-border journeys where at least one end of the
  route is a Swiss station (e.g. Paris→Genève or Zürich→Milan). Purely
  foreign routes with no Swiss end are refused.
- **Reference period:** live/current OJP timetable data at query time; no
  historical timetable queries.
- **Out of scope:** non-public-transit topics, and every other challenge
  topic area (taxes, health insurance, waste collection, etc).
  International fare lookups are refused with an SBB booking deep link
  instead of a guessed price. Out-of-scope questions get an honest "not
  covered" response, never a guess. Current disruptions affecting a
  station *are* covered — see `find_disruptions` below.
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
  route to/from ZRH that AeroDataBox indexes.
- **Reference period:** live and scheduled flight data via AeroDataBox,
  including current-day and scheduled future flights (e.g. tomorrow's
  timetable) via its dedicated flight-by-date endpoint. No historical
  flight queries.
- **Data quality note:** AeroDataBox is a commercial flight-data
  aggregator, not the airport operator or a Swiss aviation authority.
  Times, gates, and delays are reported only when present in the
  provider's response; the server never infers or guesses a value.
  Static airport guidance is sourced directly from official
  `flughafen-zuerich.ch` pages, not scraped live.

**Domestic flight fares:**

- **Topics:** current commercial flight-fare searches between supported Swiss
  airports, with airline, flight number, departure/arrival time, duration,
  requested-currency price, and carbon emissions when supplied.
- **Geography:** domestic routes between Zurich (ZRH), Geneva (GVA),
  Basel/Mulhouse (BSL/EAP/MLH), Lugano (LUG), St. Gallen/Altenrhein (ACH),
  and Sion (SIR). Routes with a foreign endpoint are refused.
- **Reference period:** live Google Flights search results retrieved through
  SerpApi for today or a future date; an omitted date defaults to tomorrow.
- **Data quality note:** SerpApi is a third-party search API. Sparse or absent
  domestic services return `not_found`; the server never invents a fare.

**Out of scope (all modules):** departure boards beyond what's
described above, visas/immigration rules, airline-specific policies,
foreign domestic-flight fares, and every other challenge topic area (taxes,
health insurance, waste collection, etc). Out-of-scope questions get an
honest response, never a guess.

## Setup

Requires Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).

```bash
cd swiss-grounding-mcp/server
uv venv
uv pip install -e ".[dev]" --group dev
cp .env.example .env
# edit .env and set the credentials for the tools you plan to use
```

## Required credentials

- `OJP_API_TOKEN`: a free API token for OJP 2.0. Register an app and
  subscribe to the "OJP 2.0" product at
  <https://api-manager.opentransportdata.swiss/>. Free tier limits: 50
  requests/minute, 20,000/day.
- `AERODATABOX_API_KEY`: a RapidAPI key for
  [AeroDataBox](https://rapidapi.com/aedbx-aedbx/api/aerodatabox). Sign
  up for the free "Basic" plan (400 API units/month, 1 request/second)
  or a paid plan ("Pro" and above) for higher volume.
  Without this key, the aviation flight-lookup and flight-search tools
  return `source_unavailable`; the airport-guidance tool still works
  (it uses static, pre-written content, not a live API call).
  **Free-tier terms:** the "Basic" plan does not permit commercial use
  and requires visible attribution to AeroDataBox with a link to
  aerodatabox.com wherever the data is shown publicly (this server's
  `provenance.source` field already reads `"AeroDataBox
  (aerodatabox.com)"` for that purpose). For Swisscom's evaluation run,
  or any use beyond personal development/testing, upgrade to a paid
  plan (from ~$7.50–8/month), which lifts the commercial-use
  restriction and makes attribution optional.
- `SERPAPI_API_KEY`: a SerpApi key used by `get_flight_fares` to query Google
  Flights results. Without this key, that tool returns `source_error`; all
  train, AeroDataBox, and static-guidance tools continue to work.

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
`departure_time`/`arrival_time` should be left unset for "now" rather than
computed by the calling model/LLM, since the current date is filled in
here and not something the LLM reliably knows; a relative day such as
"tomorrow" should still be resolved by the caller against the real
current date. All times, in requests and in responses, are UTC.

If the exact requested departure/arrival minute does not match the
timetable (e.g. asking for a 18:00 departure when the next train leaves
at 18:01), the tool retries once with a small margin
(`TRIP_TIME_MARGIN_MINUTES`, default 10 minutes, configurable) before
reporting `not_found`, and says so in `message` when the margin was used.

Output: a structured object with a `status` of `ok`, `needs_clarification`,
`not_found`, `out_of_scope`, or `source_error`; a human-readable `message`;
`connections` (only for `ok`); `candidates` (only for `needs_clarification`);
and a `provenance` block with source name, URL, retrieval timestamp, and
`timezone` (always `"UTC"`) (only for `ok`).

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

## The `check_public_transport_fares` tool

Input: `origin` (str), `destination` (str), `departure_time` (ISO 8601,
optional — defaults to "now"), `travel_class` (str, default `"2"`),
`discount_card` (str, optional — e.g. `"Halbtax"`).

Output: `status` of `success`, `fallback_link`, `out_of_scope`,
`needs_clarification`, or `source_error`; a human-readable `message`;
`fares` (only for `success`) as a list of `FareProduct` objects with
`product`, `price_chf`, `class_of_travel`, and `discount`; and a
`booking_url` with an SBB timetable deep link for the requested journey
whenever a price cannot be returned. International routes are refused as
`out_of_scope` and return the SBB deep link without a guessed fare.

## The `find_disruptions` tool

Input: `stop` (str). Unlike `find_connections` and `get_station_board`,
this tool is **not** restricted to Swiss stations — OJP 2.0 also indexes
stops just across the border, and a disruption question about one of
those is answered rather than refused as out of scope.

Output: same status set as `find_connections`; on `ok`, a list of
`disruptions` with `id`, `title`, `description`, `severity`, `start_time`,
`end_time`, `status`, `affected_lines`, and `affected_stops`, plus the
`provenance` block. Uses current real-time OJP 2.0 stop-event information
to surface cancellations, delays, and boarding/alighting restrictions
affecting services at the requested station.

## The `get_flight_fares` tool

Input: `origin_city`, `destination_city`, optional `outbound_date`
(`YYYY-MM-DD`, defaults to tomorrow), and `currency` (defaults to `CHF`).
City names and IATA aliases are accepted for ZRH, GVA, BSL/EAP/MLH, LUG,
ACH, and SIR.

Output: `status` of `ok`, `needs_clarification`, `not_found`, `out_of_scope`,
or `source_error`; up to five concise flight itineraries for `ok`; and
SerpApi provenance with a UTC retrieval timestamp. Foreign routes are refused
before an API call, and routes without commercial service return `not_found`.

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
applicable_date, timezone). `timezone` is always `"UTC"`: this server
only ever reads AeroDataBox's `.utc` time fields, never `.local`, so
every flight time it returns (and the train tools' times) is UTC —
consistently, across all tools, not the departure or arrival airport's
local zone.

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
future non-API sources this server may add later — the OJP, AeroDataBox, and
SerpApi adapters used today are keyed APIs, not scraped HTML, so this setting
has no effect on them yet. `SERPAPI_BASE_URL` defaults to
`https://serpapi.com/search.json`, and `SERPAPI_TIMEOUT_SECONDS` defaults to 10.
`TRIP_TIME_MARGIN_MINUTES` (default `10`) controls how far `find_connections`
widens an exact departure/arrival time before giving up and reporting
`not_found`.

## Running the checks

```bash
cd swiss-grounding-mcp/server
uv run pytest -v
```

## Voice assistant

`voice_assistant.py` is a hands-free conversational front end over all
seven tools: microphone -> ElevenLabs Scribe STT -> intent routing -> tool
call -> spoken summary -> ElevenLabs TTS -> speaker, looping until you say
goodbye.

```bash
cd swiss-grounding-mcp/server
uv pip install --python .venv/Scripts/python.exe elevenlabs sounddevice soundfile numpy  # or: uv sync --group voice
./.venv/Scripts/python voice_assistant.py              # voice loop (needs ELEVENLABS_API_KEY in .env)
./.venv/Scripts/python voice_assistant.py --text       # type instead of speaking
./.venv/Scripts/python voice_assistant.py --mute       # print answers, skip TTS
./.venv/Scripts/python voice_assistant.py --self-test  # mock end-to-end check, no mic needed
./.venv/Scripts/python voice_assistant.py --list-devices
```

Understands English, German, and French phrasings for connections
("Bern to Zurich", "Bern nach Zürich"), station boards ("departures from
Zurich HB"), disruptions, flight numbers ("LX14"), airport guidance, and
flight-to-train connections. `ELEVENLABS_API_KEY` (or `ELEVEN_LABS_API_KEY`)
is read from `.env`/`.env.local`; `ELEVENLABS_VOICE_ID` overrides the
default voice.

### Conversational brain

The assistant maintains full chat history and supports multi-turn
clarification ("Zurich" → "do you want departures or a connection?" →
"to Geneva" → `find_connections`). With an LLM key it uses real function
calling over all seven tools; without one it falls back to a deterministic
router with the same multi-turn memory:

```bash
OPENAI_API_KEY=...          # gpt-4o-mini (OPENAI_MODEL/OPENAI_BASE_URL override)
GROQ_API_KEY=...            # or Groq (llama-3.3-70b-versatile)
OPENROUTER_API_KEY=...      # or OpenRouter (openai/gpt-4o-mini)
```

Add any one to `.env`; the active brain is printed at startup.

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
   `provenance.source_url` under `aerodatabox.com`.
7. Call `get_airport_guidance` with `topic="transfers"`; confirm the
   `source_url` is under `flughafen-zuerich.ch`.
8. Call `search_airport_flights` with `direction="departure"` and no
   `airport_iata`/`airport_icao`/`airline_iata`; confirm `needs_context`.
9. Call `find_flight_by_number` with a nonexistent flight number;
   confirm `insufficient_evidence`, not a guessed answer.
10. Temporarily set `AERODATABOX_API_KEY` to an empty value and call
    `find_flight_by_number`; confirm `source_unavailable`, and that
    `get_airport_guidance` still returns `answered` (it needs no API key).
11. Call `connect_flight_to_train` with a real flight number, date, a
    destination station, and `transfer_buffer_minutes=45`; confirm
    separate `flight_provenance` and `rail_provenance` blocks and that
    the train search departure time is the flight's arrival time plus
    the buffer.

## Limitations

- Milestone 1 (train) covers connection search, station boards,
  disruption feeds, and fare lookups; no other non-rail modes.
- Fare lookups use the OJP Fare Beta endpoint when available; when that
  endpoint fails, the response falls back to an SBB booking deep link with
  no guessed price.
- Station name resolution uses OJP's own fuzzy matching; extremely
  ambiguous or misspelled names may require a follow-up clarification.
- The aviation module covers ZRH only, is backed by a third-party
  aggregator (AeroDataBox) rather than the airport operator, and does
  not cover historical flights, fares, visas, or airline-specific rules.
- The AeroDataBox free ("Basic") tier has a small monthly quota (400 API
  units) and a 1 request/second rate limit; the client caches identical
  requests for `AERODATABOX_CACHE_SECONDS` (default 60s) to conserve it,
  but sustained heavy use requires a paid plan. The free tier also does
  not permit commercial use and requires public attribution — see
  "Required credentials" above.
- `search_airport_flights` issues two API calls per search (AeroDataBox's
  FIDS/airport-schedule endpoint caps each call's time range at 12
  hours, so a full day requires two windows), which costs roughly twice
  the API quota of a single-flight lookup.
- AeroDataBox's flight-by-number-and-date endpoint (used by
  `find_flight_by_number`) explicitly supports scheduled future flights
  (e.g. tomorrow's timetable), which was the reason this module was
  switched from an earlier provider (Aviationstack) whose free tier
  could not filter by date at all.
- **Confirmed via live testing:** AeroDataBox returns `HTTP 204` with an
  empty body for "no matching flight" on the flight-by-number endpoint,
  rather than `200` with an empty array. The client treats this as a
  valid "no match" (`insufficient_evidence`), not a provider failure.
