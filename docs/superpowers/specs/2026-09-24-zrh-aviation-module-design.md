# Swiss Grounding MCP — ZRH Aviation Module Design Spec

Status: draft, awaiting review before implementation planning.

## 1. Purpose and Success Criteria

Extend the existing Swiss Grounding MCP server with a **Zurich Airport (ZRH/LSZH) aviation module**. The module lets a standard MCP client and LLM answer supported questions about flights arriving at or departing from ZRH, passenger guidance at the airport, and onward rail travel from Zürich Flughafen.

Success criteria:

- An independent MCP client can discover and invoke every aviation tool.
- Flight-number and airport-guidance queries return evidence the reviewer can open and check.
- Ambiguous country/city input requests the missing airport.
- Unknown flights, stale data, API failures, and unavailable fields produce honest outcomes.
- Flight-to-train queries preserve separate flight and rail provenance and use an explicit transfer buffer.
- An LLM using only this MCP does not assert unsupported arrival times, delays, gates, visa requirements, or train connections.

## 2. Declared Scope

**Topics:**

- ZRH flight lookup by flight number and date.
- ZRH arrivals/departures search by origin/destination airport and date.
- Cited ZRH passenger guidance: arrival process, transfers, baggage, airport rail access, and where to verify flight-specific details.
- Connecting a ZRH arrival to onward train travel via the existing OJP tool.

**Geography:** Zurich Airport (ZRH / LSZH). Origin/destination airports for flight searches may be any airport covered by the configured aviation-data provider.

**Reference period:** live/current flight timetable data at query time, via Aviationstack. Historical queries are not supported.

**Data quality note:** Aviationstack is a commercial flight-data aggregator, not a Swiss aviation authority. Times, status, gates, and terminals are reported **as supplied by the provider**. The module never synthesizes values not present in the response.

**Explicitly out of scope:**

- Fares, seat selection, check-in, immigration/visa rules, or personalized entry requirements.
- Airline-specific rules (e.g., baggage allowances, check-in deadlines).
- Real-time aircraft positions, radar/ADS-B tracking, or flight plans.
- Other Swiss challenge topics (taxes, health insurance, waste collection, etc.).
- Any airport other than ZRH for the passenger-guidance tool.

## 3. Data Sources

### 3.1 Live flight data — Aviationstack

- Provider: `aviationstack.com` (Apilayer Data Products GmbH).
- Endpoint: `https://api.aviationstack.com/v1/flights`.
- Auth: `access_key` query parameter.
- Free tier: ~100–500 requests/month (sources differ; use the smallest figure for planning). Personal license only.
- Paid tier: Basic plan $49.99/month for 10,000 requests and commercial license.
- Coverage: global commercial flights; fields include `flight_date`, `flight_status`, `departure`/`arrival` with `scheduled`, `estimated`, `actual`, `terminal`, `gate`, `delay`, plus airline and aircraft details.
- Update frequency: real-time status delayed ~30–60 seconds.
- Rate-limiting strategy: short in-memory cache (60 s), small `limit` values, fixture-based unit tests. Errors do not count against quota per Aviationstack FAQ.
- Terms: free tier is personal-use only; commercial/evaluation use requires a paid plan. Full terms at `https://aviationstack.com/agreement`.

### 3.2 Static airport guidance — official Zurich Airport pages

The following official pages are cited directly. The module returns pre-structured guidance with these URLs; it does **not** scrape the pages.

| Topic | Official ZRH page |
|---|---|
| Arrival process / getting from the airport | `https://www.flughafen-zuerich.ch/en/passengers` and arrivals page |
| Transfers | `https://www.flughafen-zuerich.ch/en/passengers/fly/all-about-the-flight/transfer` |
| Baggage | `https://www.flughafen-zuerich.ch/en/passengers/fly/all-about-the-flight/baggage` (linked from site footer) |
| Airport rail access | `https://www.flughafen-zuerich.ch/en/passengers/practical/parking-and-transport` routes |
| Verify flight details | `https://www.flughafen-zuerich.ch/en/passengers/fly/flightinformation/arrivals` / `departures` |

## 4. Repository Layout

Implementation lives under the existing `swiss-grounding-mcp/server/`.

```
swiss-grounding-mcp/server/
  src/swiss_grounding_mcp/
    config/settings.py              # extend with AVIATIONSTACK_* settings
    domain/models.py                # extend with aviation models
    evidence/provenance.py          # extend with aviation provenance builder
    sources/
      ojp/                          # existing train source adapter
      aviationstack/
        __init__.py
        client.py                   # HTTP wrapper, auth, timeout, error mapping
        parser.py                   # Aviationstack JSON -> domain models
      zrh/
        __init__.py
        guidance.py                 # static guidance records with ZRH URLs
    tools/
      find_connections.py           # existing train connections tool
      find_flight_by_number.py
      search_airport_flights.py
      get_airport_guidance.py
      connect_flight_to_train.py
    server.py                       # register new tools alongside find_connections
  tests/unit/
    test_aviationstack_client.py
    test_aviationstack_parser.py
    test_airport_guidance.py
    test_connect_flight_to_train.py
    fixtures/aviationstack/         # captured JSON responses
  .env.example
  README.md
```

## 5. Tool Contracts

All aviation tools return a structured object with a `status` field. Aviation tools use the statuses `answered`, `needs_context`, `insufficient_evidence`, `out_of_scope`, and `source_unavailable`. The existing train tool keeps its current status set unchanged.

### 5.1 `find_flight_by_number`

**Description for MCP clients:**
> Look up a flight by flight number and date for Zurich Airport (ZRH). Returns scheduled, estimated, and actual departure/arrival times only when provided by the aviation data source. Does not infer gates, delays, or status.

**Input:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `flight_number` | string | yes | IATA flight number, e.g. `LX14` or `LX 14`. |
| `flight_date` | string | yes | ISO 8601 date `YYYY-MM-DD`. |
| `direction` | string | no | `arrival` or `departure` at ZRH; omit for either. |

**Output:**

```json
{
  "status": "answered",
  "message": null,
  "flight": {
    "flight_number": "LX14",
    "flight_date": "2026-09-25",
    "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
    "departure": {
      "airport_iata": "ZRH",
      "airport_icao": "LSZH",
      "airport_name": "Zurich Airport",
      "scheduled": "2026-09-25T10:20:00+02:00",
      "estimated": "2026-09-25T10:25:00+02:00",
      "actual": null,
      "terminal": "1",
      "gate": "A12",
      "delay": 5
    },
    "arrival": {
      "airport_iata": "JFK",
      "airport_icao": "KJFK",
      "airport_name": "John F. Kennedy Intl",
      "scheduled": "2026-09-25T14:10:00-04:00",
      "estimated": "2026-09-25T14:05:00-04:00",
      "actual": null,
      "terminal": "4",
      "gate": "B22",
      "delay": null
    },
    "flight_status": "scheduled"
  },
  "fields_present": ["departure.scheduled", "departure.estimated", "arrival.scheduled", "arrival.estimated"],
  "fields_missing": ["departure.actual", "arrival.actual"],
  "provenance": {
    "source": "aviationstack.com",
    "source_url": "https://api.aviationstack.com/v1/flights",
    "retrieved_at": "2026-09-24T22:15:00Z",
    "applicable_date": "2026-09-25",
    "timezone": "Europe/Zurich"
  }
}
```

- `status` can also be `needs_context` (missing flight number/date), `insufficient_evidence` (no match), `source_unavailable` (provider error/quota), or `out_of_scope` (non-aviation input).
- Only fields that exist in the Aviationstack response are included; missing fields are listed in `fields_missing`.

### 5.2 `search_airport_flights`

**Description for MCP clients:**
> Search arrivals or departures at Zurich Airport for a date. Filter by origin/destination airport IATA/ICAO code or airline. City or country names alone are not accepted; provide the exact airport code.

**Input:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `direction` | string | yes | `arrival` or `departure`. |
| `flight_date` | string | yes | `YYYY-MM-DD`. |
| `airport_iata` | string | no | Origin (departures) or destination (arrivals) airport IATA. |
| `airport_icao` | string | no | Origin/destination ICAO. |
| `airline_iata` | string | no | Airline IATA filter. |
| `limit` | int | no | Default 10, max 100. |

**Output:** list of flights as above, plus `provenance`.

- If only a city/country is supplied without an airport code, return `needs_context` asking for the exact IATA or ICAO airport code.
- If no flights match, return `insufficient_evidence`, not `answered` with an empty list.

### 5.3 `get_airport_guidance`

**Description for MCP clients:**
> Cited passenger guidance for Zurich Airport. Topics: arrival process, transfers, baggage, airport rail access, and where to verify flight-specific details.

**Input:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `topic` | string | yes | One of `arrival_process`, `transfers`, `baggage`, `airport_rail_access`, `flight_status_verification`. |

**Output:**

```json
{
  "status": "answered",
  "topic": "transfers",
  "guidance": "If you already have a boarding pass for your connecting flight, check the departure time and gate on the flight information screens or on the Zurich Airport website. Your gate is shown at least 60 minutes before departure. ...",
  "source": "Flughafen Zürich AG",
  "source_url": "https://www.flughafen-zuerich.ch/en/passengers/fly/all-about-the-flight/transfer",
  "retrieved_at": "2026-09-24T22:15:00Z",
  "applicable_airport": "ZRH / LSZH",
  "limitations": "Airline-specific transfer rules are out of scope; verify with your airline."
}
```

### 5.4 `connect_flight_to_train`

**Description for MCP clients:**
> Connect a ZRH arrival to onward Swiss train travel. Requires an explicit transfer buffer. Either provide a flight number and date (to look up the arrival time) or a confirmed arrival time. Never assumes a train is reachable just because the flight is scheduled to arrive before it.

**Input:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `flight_number` | string | no | IATA flight number. Required unless `confirmed_arrival_time` is given. |
| `flight_date` | string | no | `YYYY-MM-DD`. Required if `flight_number` is given. |
| `confirmed_arrival_time` | string | no | ISO 8601 datetime at ZRH. Alternative to `flight_number`. |
| `destination_station` | string | yes | Swiss destination station name or OJP stop ref. |
| `transfer_buffer_minutes` | int | yes | Minimum minutes after arrival to allow before the first train. Must be >= 15. |
| `rail_results` | int | no | Default 3, max 5. |

**Output:**

```json
{
  "status": "answered",
  "message": "Flight LX14 is scheduled to arrive at ZRH at 14:10. With a 60-minute buffer, the earliest considered train departure is 15:10.",
  "flight": { ... },
  "train_connections": [ ... ],
  "flight_provenance": { ... },
  "rail_provenance": { ... }
}
```

- If `flight_number` is provided, the tool calls Aviationstack to obtain the ZRH arrival time; on `source_unavailable` it asks for `confirmed_arrival_time`.
- The tool computes `earliest_train_departure = arrival_time + transfer_buffer_minutes` and passes it as `departure_time` to the existing OJP-based `find_connections` tool from **Zürich Flughafen** to `destination_station`.
- If station resolution is ambiguous, the existing train tool's `needs_clarification` is returned unchanged.
- Flight and rail provenance are kept in separate objects.

## 6. Domain Models

Pydantic models added to `domain/models.py`:

- `AirportInfo`: iata, icao, name, timezone.
- `FlightTimes`: scheduled, estimated, actual, terminal, gate, delay. All optional.
- `Flight`: flight_number, flight_date, airline, departure, arrival, flight_status, aircraft (optional).
- `AviationProvenance`: source, source_url, retrieved_at, applicable_date, timezone.
- `FlightLookupResult`: status, message, flight (optional), fields_present, fields_missing, provenance.
- `FlightSearchResult`: status, message, flights[], provenance.
- `AirportGuidanceResult`: status, topic, guidance, source, source_url, retrieved_at, applicable_airport, limitations.
- `FlightToTrainResult`: status, message, flight (optional), train_connections, flight_provenance (optional), rail_provenance (optional).

## 7. Source Adapter

`AviationstackClient` in `sources/aviationstack/client.py`:

- Accepts `Settings`.
- Builds request params; uses `httpx` with timeout.
- Returns raw Aviationstack JSON.
- Raises `AviationstackSourceError` for non-2xx, network failure, JSON error, or unparseable response.

`AviationstackParser` in `sources/aviationstack/parser.py`:

- Parses Aviationstack flight objects into domain `Flight` models.
- Normalizes `flight_number` strings (strips spaces, uppercases).
- Records `fields_present` / `fields_missing` so the tool never claims a value that was absent.
- Filters results for ZRH when needed.

## 8. Configuration

Extend `Settings` and `.env.example`:

```bash
AVIATIONSTACK_API_KEY=
AVIATIONSTACK_BASE_URL=https://api.aviationstack.com/v1
AVIATIONSTACK_TIMEOUT_SECONDS=10
AVIATIONSTACK_ENABLE=true
AVIATIONSTACK_CACHE_SECONDS=60
```

- If `AVIATIONSTACK_ENABLE=false` or `AVIATIONSTACK_API_KEY` is empty, live flight tools return `source_unavailable` with a clear message.

## 9. Control Flow

### `find_flight_by_number`

1. Validate `flight_number` and `flight_date`. Missing -> `needs_context`.
2. Build query: `flight_iata=<normalized>`, `flight_date=<date>`.
3. If `direction=arrival`, also require `arr_iata=ZRH`; if `departure`, `dep_iata=ZRH`.
4. Call Aviationstack with `limit=1`.
5. On source failure -> `source_unavailable`.
6. Parse result. Zero matches -> `insufficient_evidence`. Multiple matches -> return the first and note multiplicity in `message`. Build provenance.

### `search_airport_flights`

1. Validate `direction` and `flight_date`. Missing -> `needs_context`.
2. If `airport_iata` or `airport_icao` is missing and the query text looks like a country or city name (heuristic: length > 3, no known code pattern) -> `needs_context` asking for the exact airport code.
3. Build query: `flight_date`, `dep_iata=ZRH` or `arr_iata=ZRH`, optional origin/destination filter and `airline_iata`.
4. Call Aviationstack with the requested `limit` (clamped ≤ 100).
5. Map results and provenance.

### `get_airport_guidance`

1. Validate `topic` against allowed enum. Unknown -> `out_of_scope`.
2. Return the pre-structured guidance record with official ZRH URL and current UTC timestamp.

### `connect_flight_to_train`

1. Validate `destination_station` and `transfer_buffer_minutes` (≥ 15). Missing -> `needs_context`.
2. If `flight_number` is given, look it up via `find_flight_by_number` logic; obtain ZRH arrival time.
   - If lookup returns non-`answered`, return that result (or ask for `confirmed_arrival_time`).
3. Else use `confirmed_arrival_time`.
4. Compute `train_departure_time = arrival_time + transfer_buffer_minutes`.
5. Call existing `find_train_connections(origin="Zürich Flughafen", destination=..., departure_time=train_departure_time, results=...)`. Reuse `get_client()` OJP client.
6. Combine flight and rail results with separate provenance.

## 10. Testing and Verification

### Unit tests (no live network)

- `test_aviationstack_parser`: parse sample Aviationstack JSON; verify all time/status fields mapped; verify `fields_missing` for absent fields.
- `test_aviationstack_client`: mock `httpx` responses for 200, 422/quota, network error; verify `AviationstackSourceError` and status mapping.
- `test_airport_guidance`: each topic returns an `answered` result with a `flughafen-zuerich.ch` URL.
- `test_connect_flight_to_train`: mock Aviationstack and OJP; verify buffer added, train origin is Zürich Flughafen, separate provenance.

Fixtures stored in `tests/fixtures/aviationstack/`:

- `lx14_zrh_jfk.json`: one scheduled departure from ZRH.
- `lx14_arrival_zrh.json`: one arrival at ZRH.
- `multiple_matches.json`: two flights with same number on different legs.
- `empty.json`: empty `data` array.
- `error_quota.json`: Aviationstack API error response.

### Manual verification (documented in README)

1. Start the server and list tools; confirm all four aviation tools appear.
2. Call `find_flight_by_number` with a known ZRH flight and verify `answered` with `provenance.source_url`.
3. Call `get_airport_guidance` for `transfers` and confirm the citation URL is `flughafen-zuerich.ch`.
4. Call `search_airport_flights` with a city name instead of airport code and confirm `needs_context`.
5. Call `find_flight_by_number` with a nonexistent flight and confirm `insufficient_evidence`.
6. Set `AVIATIONSTACK_API_KEY` to an invalid value and confirm `source_unavailable`.
7. Call `connect_flight_to_train` with a flight number and buffer; verify separate `flight_provenance` and `rail_provenance`.

### Live integration check

Run one live call against Aviationstack using the user's configured API key, if `AVIATIONSTACK_ENABLE=true`. The result is reported but not committed (to avoid burning quota).

## 11. Non-Goals

- No scraping of `flughafen-zuerich.ch` flight pages.
- No LLM calls inside the server.
- No visa, immigration, or airline-specific rule lookups.
- No aircraft tracking beyond what Aviationstack returns.
- No modification of the existing train tool contract.

## 12. Risks and Limitations

- Aviationstack is a third-party aggregator, not the airport operator. The challenge's "authoritative source" preference is weaker for flight data than for train data.
- Free tier has a tight quota; the demo must use small limits and caching.
- Field availability varies by airline and flight; gates and terminals may be missing.
- `flight_number` can be reused across airlines; normalization strips the airline prefix if already present.
- Rail connections depend on OJP, which is independent of Aviationstack.
