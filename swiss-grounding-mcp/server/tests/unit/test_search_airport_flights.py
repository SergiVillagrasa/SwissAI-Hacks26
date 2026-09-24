from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackSourceError
from swiss_grounding_mcp.tools.search_airport_flights import search_airport_flights

_TWO_FLIGHTS_BODY = {
    "pagination": {"limit": 10, "offset": 0, "count": 2, "total": 2},
    "data": [
        {
            "flight_date": "2026-09-25", "flight_status": "scheduled",
            "departure": {
                "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH", "icao": "LSZH",
                "terminal": "1", "gate": "A12", "delay": None,
                "scheduled": "2026-09-25T10:20:00+00:00", "estimated": None, "actual": None,
            },
            "arrival": {
                "airport": "JFK", "timezone": "America/New_York", "iata": "JFK", "icao": "KJFK",
                "terminal": "4", "gate": None, "delay": None,
                "scheduled": "2026-09-25T13:10:00+00:00", "estimated": None, "actual": None,
            },
            "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
            "flight": {"number": "14", "iata": "LX14", "icao": "SWR14", "codeshared": None},
            "aircraft": None, "live": None,
        },
        {
            "flight_date": "2026-09-25", "flight_status": "scheduled",
            "departure": {
                "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH", "icao": "LSZH",
                "terminal": "1", "gate": "A14", "delay": None,
                "scheduled": "2026-09-25T18:00:00+00:00", "estimated": None, "actual": None,
            },
            "arrival": {
                "airport": "JFK", "timezone": "America/New_York", "iata": "JFK", "icao": "KJFK",
                "terminal": "4", "gate": None, "delay": None,
                "scheduled": "2026-09-25T21:00:00+00:00", "estimated": None, "actual": None,
            },
            "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
            "flight": {"number": "16", "iata": "LX16", "icao": "SWR16", "codeshared": None},
            "aircraft": None, "live": None,
        },
    ],
}

_EMPTY_BODY = {"pagination": {"limit": 10, "offset": 0, "count": 0, "total": 0}, "data": []}


class StubAviationstackClient:
    def __init__(self, body=None, raise_error=None):
        self.body = body
        self.raise_error = raise_error
        self.calls = []

    def get_flights(self, params):
        self.calls.append(params)
        if self.raise_error is not None:
            raise self.raise_error
        return self.body


def _settings() -> Settings:
    return Settings.from_env({"AVIATIONSTACK_BASE_URL": "https://example.test/v1"})


def test_missing_direction_returns_needs_context():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "", "2026-09-25", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"


def test_missing_flight_date_returns_needs_context():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "departure", "", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"


def test_departure_search_filters_by_zrh_and_destination_airport():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert len(result.flights) == 2
    assert client.calls[0]["dep_iata"] == "ZRH"
    assert client.calls[0]["arr_iata"] == "JFK"


def test_arrival_search_filters_by_zrh_and_origin_airport():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    search_airport_flights(
        "arrival", "2026-09-25", "JFK", None, None, 10, client=client, settings=_settings()
    )

    assert client.calls[0]["arr_iata"] == "ZRH"
    assert client.calls[0]["dep_iata"] == "JFK"


def test_no_airport_code_and_no_airline_returns_needs_context():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "departure", "2026-09-25", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"
    assert "airport" in result.message.lower()
    assert client.calls == []


def test_airline_only_filter_is_accepted_without_airport_code():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    result = search_airport_flights(
        "departure", "2026-09-25", None, None, "LX", 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert client.calls[0]["airline_iata"] == "LX"


def test_no_matching_flights_returns_insufficient_evidence():
    client = StubAviationstackClient(body=_EMPTY_BODY)

    result = search_airport_flights(
        "departure", "2026-09-25", "XXX", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "insufficient_evidence"
    assert result.flights == []


def test_source_failure_returns_source_unavailable():
    client = StubAviationstackClient(raise_error=AviationstackSourceError("network down"))

    result = search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "source_unavailable"


def test_limit_is_clamped_to_valid_range():
    client = StubAviationstackClient(body=_TWO_FLIGHTS_BODY)

    search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 0, client=client, settings=_settings()
    )
    assert client.calls[0]["limit"] == 1

    search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 1000, client=client, settings=_settings()
    )
    assert client.calls[1]["limit"] == 100
