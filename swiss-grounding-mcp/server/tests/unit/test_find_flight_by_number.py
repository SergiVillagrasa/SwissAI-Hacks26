from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackSourceError
from swiss_grounding_mcp.tools.find_flight_by_number import find_flight_by_number

_LX14_BODY = {
    "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 1},
    "data": [
        {
            "flight_date": "2026-09-25",
            "flight_status": "scheduled",
            "departure": {
                "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH", "icao": "LSZH",
                "terminal": "1", "gate": "A12", "delay": 5,
                "scheduled": "2026-09-25T10:20:00+00:00",
                "estimated": "2026-09-25T10:25:00+00:00", "actual": None,
            },
            "arrival": {
                "airport": "JFK", "timezone": "America/New_York", "iata": "JFK", "icao": "KJFK",
                "terminal": "4", "gate": "B22", "delay": None,
                "scheduled": "2026-09-25T13:10:00+00:00",
                "estimated": "2026-09-25T13:05:00+00:00", "actual": None,
            },
            "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
            "flight": {"number": "14", "iata": "LX14", "icao": "SWR14", "codeshared": None},
            "aircraft": None,
            "live": None,
        }
    ],
}

_EMPTY_BODY = {"pagination": {"limit": 1, "offset": 0, "count": 0, "total": 0}, "data": []}


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


def test_missing_flight_number_returns_needs_context():
    client = StubAviationstackClient(body=_LX14_BODY)

    result = find_flight_by_number("", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "needs_context"
    assert client.calls == []


def test_missing_flight_date_returns_needs_context():
    client = StubAviationstackClient(body=_LX14_BODY)

    result = find_flight_by_number("LX14", "", None, client=client, settings=_settings())

    assert result.status == "needs_context"


def test_found_flight_returns_answered_with_provenance_and_field_lists():
    client = StubAviationstackClient(body=_LX14_BODY)

    result = find_flight_by_number("LX14", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "answered"
    assert result.flight.flight_number == "LX14"
    assert "departure.scheduled" in result.fields_present
    assert "departure.actual" in result.fields_missing
    assert result.provenance.source == "aviationstack.com"
    assert result.provenance.applicable_date == "2026-09-25"
    assert result.provenance.timezone == "Europe/Zurich"
    assert client.calls[0]["flight_iata"] == "LX14"
    assert client.calls[0]["flight_date"] == "2026-09-25"


def test_flight_number_is_normalized_before_query():
    client = StubAviationstackClient(body=_LX14_BODY)

    find_flight_by_number("lx 14", "2026-09-25", None, client=client, settings=_settings())

    assert client.calls[0]["flight_iata"] == "LX14"


def test_direction_arrival_filters_by_zrh_arrival():
    client = StubAviationstackClient(body=_LX14_BODY)

    find_flight_by_number("LX14", "2026-09-25", "arrival", client=client, settings=_settings())

    assert client.calls[0]["arr_iata"] == "ZRH"


def test_direction_departure_filters_by_zrh_departure():
    client = StubAviationstackClient(body=_LX14_BODY)

    find_flight_by_number("LX14", "2026-09-25", "departure", client=client, settings=_settings())

    assert client.calls[0]["dep_iata"] == "ZRH"


def test_no_matching_flight_returns_insufficient_evidence():
    client = StubAviationstackClient(body=_EMPTY_BODY)

    result = find_flight_by_number("XX9999", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "insufficient_evidence"
    assert result.flight is None


def test_source_failure_returns_source_unavailable():
    client = StubAviationstackClient(raise_error=AviationstackSourceError("quota exceeded"))

    result = find_flight_by_number("LX14", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "source_unavailable"
    assert "quota exceeded" in result.message
