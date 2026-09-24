from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Connection, StopCandidate
from swiss_grounding_mcp.sources.aviationstack.client import AviationstackSourceError
from swiss_grounding_mcp.tools.connect_flight_to_train import connect_flight_to_train

_LX14_ARRIVAL_BODY = {
    "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 1},
    "data": [
        {
            "flight_date": "2026-09-25", "flight_status": "scheduled",
            "departure": {
                "airport": "JFK", "timezone": "America/New_York", "iata": "JFK", "icao": "KJFK",
                "terminal": None, "gate": None, "delay": None,
                "scheduled": "2026-09-25T09:00:00+00:00", "estimated": None, "actual": None,
            },
            "arrival": {
                "airport": "Zurich", "timezone": "Europe/Zurich", "iata": "ZRH", "icao": "LSZH",
                "terminal": "2", "gate": None, "delay": None,
                "scheduled": "2026-09-25T22:00:00+00:00", "estimated": "2026-09-25T22:10:00+00:00",
                "actual": None,
            },
            "airline": {"name": "SWISS", "iata": "LX", "icao": "SWR"},
            "flight": {"number": "15", "iata": "LX15", "icao": "SWR15", "codeshared": None},
            "aircraft": None, "live": None,
        }
    ],
}


class StubAviationstackClient:
    def __init__(self, body=None, raise_error=None):
        self.body = body
        self.raise_error = raise_error

    def get_flights(self, params):
        if self.raise_error is not None:
            raise self.raise_error
        return self.body


class StubOjpClient:
    def __init__(self):
        self.trip_calls = []

    def location_information(self, name):
        return [StopCandidate(name=name, stop_ref=f"ch:1:sloid:{abs(hash(name)) % 9999}", probability=1.0)]

    def trip_request(self, origin_ref, destination_ref, **kwargs):
        self.trip_calls.append({"origin_ref": origin_ref, "destination_ref": destination_ref, **kwargs})
        return [
            Connection(
                departure="2026-09-25T23:10:00Z",
                arrival="2026-09-26T00:03:00Z",
                duration_minutes=53,
                changes=0,
                legs=[],
            )
        ]


def _settings() -> Settings:
    return Settings.from_env({"AVIATIONSTACK_BASE_URL": "https://example.test/v1"})


def test_missing_destination_returns_needs_context():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "", 60, 3,
        aviation_client=StubAviationstackClient(body=_LX14_ARRIVAL_BODY),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"


def test_buffer_below_minimum_returns_needs_context():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 5, 3,
        aviation_client=StubAviationstackClient(body=_LX14_ARRIVAL_BODY),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"
    assert "buffer" in result.message.lower()


def test_missing_flight_and_confirmed_time_returns_needs_context():
    result = connect_flight_to_train(
        None, None, None, "Bern", 60, 3,
        aviation_client=StubAviationstackClient(body=_LX14_ARRIVAL_BODY),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"


def test_flight_lookup_success_computes_buffered_departure_and_calls_ojp():
    ojp_client = StubOjpClient()
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAviationstackClient(body=_LX14_ARRIVAL_BODY),
        ojp_client=ojp_client,
        settings=_settings(),
    )

    assert result.status == "answered"
    assert result.flight.flight_number == "LX15"
    assert len(result.train_connections) == 1
    assert result.flight_provenance.source == "aviationstack.com"
    assert result.rail_provenance is not None
    assert result.rail_provenance is not result.flight_provenance
    assert ojp_client.trip_calls[0]["departure_time"] == "2026-09-25T23:10:00+00:00"


def test_confirmed_arrival_time_skips_flight_lookup():
    ojp_client = StubOjpClient()
    result = connect_flight_to_train(
        None, None, "2026-09-25T22:00:00+00:00", "Bern", 30, 3,
        aviation_client=StubAviationstackClient(raise_error=AviationstackSourceError("should not be called")),
        ojp_client=ojp_client,
        settings=_settings(),
    )

    assert result.status == "answered"
    assert result.flight is None
    assert ojp_client.trip_calls[0]["departure_time"] == "2026-09-25T22:30:00+00:00"


def test_flight_lookup_source_unavailable_asks_for_confirmed_time():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAviationstackClient(raise_error=AviationstackSourceError("quota exceeded")),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"
    assert "confirmed_arrival_time" in result.message


def test_flight_not_found_returns_insufficient_evidence():
    empty_body = {"pagination": {"limit": 1, "offset": 0, "count": 0, "total": 0}, "data": []}

    result = connect_flight_to_train(
        "XX999", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAviationstackClient(body=empty_body),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "insufficient_evidence"
