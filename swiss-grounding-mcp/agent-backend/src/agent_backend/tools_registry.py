from __future__ import annotations

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "find_connections",
            "description": (
                "Find Swiss passenger-train connections between two stations. "
                "Scope: the current Swiss public-transport timetable only, via "
                "OJP 2.0 (opentransportdata.swiss). Does not cover fares, "
                "single-stop departure boards, disruption feeds, or purely "
                "non-Swiss travel."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Origin station name."},
                    "destination": {"type": "string", "description": "Destination station name."},
                    "departure_time": {"type": "string", "description": "ISO 8601 departure time; defaults to now."},
                    "arrival_time": {"type": "string", "description": "ISO 8601 arrival time; ignored if departure_time is also given."},
                    "results": {"type": "integer", "description": "Number of connections to return (max 5).", "default": 3},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_disruptions",
            "description": (
                "Find current public-transport disruptions affecting a Swiss "
                "station, using real-time OJP 2.0 stop-event information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "stop": {"type": "string", "description": "Station name."},
                },
                "required": ["stop"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_station_board",
            "description": (
                "Show upcoming departures or arrivals at a Swiss "
                "public-transport stop via OJP 2.0. Stations outside "
                "Switzerland are refused as out of scope."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "station": {"type": "string", "description": "Station name."},
                    "mode": {"type": "string", "enum": ["departures", "arrivals"], "default": "departures"},
                    "when": {"type": "string", "description": "ISO 8601 timestamp; defaults to now."},
                    "results": {"type": "integer", "description": "Number of events (max 10).", "default": 5},
                },
                "required": ["station"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_public_transport_fares",
            "description": (
                "Check public-transport fares between two Swiss stations via "
                "the OJP Fare Beta endpoint. If live fare data is unavailable, "
                "returns an SBB booking deep link instead of a guessed price. "
                "International routes are refused rather than guessed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "departure_time": {"type": "string", "description": "ISO 8601; defaults to now."},
                    "travel_class": {"type": "string", "default": "2"},
                    "discount_card": {"type": "string", "description": "e.g. 'Halbtax'."},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_flight_fares",
            "description": (
                "Find current commercial flight fares between supported Swiss "
                "airports via SerpApi Google Flights. Scope: domestic Swiss "
                "routes only (Zurich, Geneva, Basel/Mulhouse, Lugano, "
                "St. Gallen/Altenrhein, Sion). Foreign routes are refused "
                "rather than queried."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_city": {"type": "string", "description": "Origin city or airport name."},
                    "destination_city": {"type": "string", "description": "Destination city or airport name."},
                    "outbound_date": {"type": "string", "description": "YYYY-MM-DD; defaults to tomorrow."},
                    "currency": {"type": "string", "description": "Three-letter currency code.", "default": "CHF"},
                },
                "required": ["origin_city", "destination_city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_flight_by_number",
            "description": (
                "Look up a flight at Zurich Airport (ZRH) by flight number and "
                "date, via AeroDataBox. Only fields present in the response "
                "are returned; never infers gates, delays, or status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number": {"type": "string", "description": "IATA flight number, e.g. 'LX14'."},
                    "flight_date": {"type": "string", "description": "YYYY-MM-DD."},
                    "direction": {"type": "string", "enum": ["arrival", "departure"]},
                },
                "required": ["flight_number", "flight_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_airport_flights",
            "description": (
                "Search ZRH arrivals or departures for a date via AeroDataBox. "
                "Requires the exact IATA/ICAO code of the other airport; a "
                "city or country name alone is not accepted."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["arrival", "departure"]},
                    "flight_date": {"type": "string", "description": "YYYY-MM-DD."},
                    "airport_iata": {"type": "string"},
                    "airport_icao": {"type": "string"},
                    "airline_iata": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["direction", "flight_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_airport_guidance",
            "description": (
                "Cited Zurich Airport passenger guidance. Topics: "
                "arrival_process, transfers, baggage, airport_rail_access, "
                "flight_status_verification."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": [
                            "arrival_process",
                            "transfers",
                            "baggage",
                            "airport_rail_access",
                            "flight_status_verification",
                        ],
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "connect_flight_to_train",
            "description": (
                "Connect a ZRH arrival to onward Swiss train travel. Provide "
                "either flight_number + flight_date or confirmed_arrival_time. "
                "transfer_buffer_minutes (minimum 15) is required and added to "
                "the arrival time before searching trains."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination_station": {"type": "string"},
                    "transfer_buffer_minutes": {"type": "integer", "minimum": 15},
                    "flight_number": {"type": "string"},
                    "flight_date": {"type": "string", "description": "YYYY-MM-DD."},
                    "confirmed_arrival_time": {"type": "string", "description": "ISO 8601 datetime at ZRH."},
                    "rail_results": {"type": "integer", "default": 3},
                },
                "required": ["destination_station", "transfer_buffer_minutes"],
            },
        },
    },
]

TOOL_NAMES: frozenset[str] = frozenset(schema["function"]["name"] for schema in TOOL_SCHEMAS)
