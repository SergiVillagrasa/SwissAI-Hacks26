from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import StopCandidate, StopEvent
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.station_timetable import get_station_board


class StubOjpClient:
    def __init__(self, *, candidates=None, events=None, raise_on_location=None, raise_on_events=None):
        self.candidates = candidates or []
        self.events = events if events is not None else []
        self.raise_on_location = raise_on_location
        self.raise_on_events = raise_on_events
        self.event_calls = []

    def location_information(self, name):
        if self.raise_on_location is not None:
            raise self.raise_on_location
        return self.candidates

    def get_stop_events(self, stop_ref, event_type="departure", when=None, limit=5, **kwargs):
        self.event_calls.append(
            {"stop_ref": stop_ref, "event_type": event_type, "when": when, "limit": limit}
        )
        if self.raise_on_events is not None:
            raise self.raise_on_events
        return self.events


def _settings() -> Settings:
    return Settings.from_env({"OJP_BASE_URL": "https://example.test/ojp20"})


def _swiss_station() -> StopCandidate:
    return StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)


def _event() -> StopEvent:
    return StopEvent(
        line="IC 1",
        mode="rail",
        direction_name="Genève-Aéroport",
        planned_time="2026-09-24T12:33:00Z",
        estimated_time="2026-09-24T12:37:00Z",
        platform="9",
        delay_minutes=4,
    )


def test_departures_return_ok_with_events_and_provenance():
    client = StubOjpClient(candidates=[_swiss_station()], events=[_event()])

    result = get_station_board("Zürich HB", client=client, settings=_settings())

    assert result.status == "ok"
    assert result.station_name == "Zürich HB"
    assert result.event_type == "departure"
    assert len(result.events) == 1
    assert result.events[0].line == "IC 1"
    assert result.events[0].platform == "9"
    assert result.events[0].delay_minutes == 4
    assert result.provenance.source_url == "https://example.test/ojp20"
    assert client.event_calls[0]["event_type"] == "departure"


def test_arrivals_mode_is_forwarded_to_client():
    client = StubOjpClient(candidates=[_swiss_station()], events=[_event()])

    result = get_station_board(
        "Zürich HB", mode="arrivals", client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert result.event_type == "arrival"
    assert client.event_calls[0]["event_type"] == "arrival"


def test_empty_station_returns_needs_clarification():
    client = StubOjpClient()

    result = get_station_board("   ", client=client, settings=_settings())

    assert result.status == "needs_clarification"
    assert client.event_calls == []


def test_invalid_mode_returns_needs_clarification():
    client = StubOjpClient(candidates=[_swiss_station()])

    result = get_station_board(
        "Zürich HB", mode="sideways", client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert "departures" in result.message or "arrivals" in result.message
    assert client.event_calls == []


def test_ambiguous_station_returns_needs_clarification_with_candidates():
    client = StubOjpClient(
        candidates=[
            StopCandidate(name="Bellevue (Zürich)", stop_ref="ch:1:sloid:1", probability=0.55),
            StopCandidate(name="Bellevue (Genève)", stop_ref="ch:1:sloid:2", probability=0.52),
        ]
    )

    result = get_station_board("Bellevue", client=client, settings=_settings())

    assert result.status == "needs_clarification"
    assert len(result.candidates) == 2
    assert client.event_calls == []


def test_unresolvable_station_returns_not_found():
    client = StubOjpClient(candidates=[])

    result = get_station_board("Atlantis", client=client, settings=_settings())

    assert result.status == "not_found"
    assert client.event_calls == []


def test_foreign_station_returns_out_of_scope_without_event_call():
    client = StubOjpClient(
        candidates=[
            StopCandidate(
                name="Paris Gare de Lyon", stop_ref="fr:1:sloid:1", probability=1.0
            )
        ],
        events=[_event()],
    )

    result = get_station_board(
        "Paris Gare de Lyon", client=client, settings=_settings()
    )

    assert result.status == "out_of_scope"
    assert result.events == []
    assert client.event_calls == []


def test_results_are_clamped_and_truncated():
    client = StubOjpClient(
        candidates=[_swiss_station()],
        events=[_event()] * 15,
    )

    result = get_station_board(
        "Zürich HB", results=50, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert client.event_calls[0]["limit"] == 10
    assert len(result.events) == 10


def test_source_error_from_location_information():
    client = StubOjpClient(raise_on_location=OjpSourceError("OJP returned HTTP 500"))

    result = get_station_board("Bern", client=client, settings=_settings())

    assert result.status == "source_error"


def test_source_error_from_stop_events():
    client = StubOjpClient(
        candidates=[_swiss_station()],
        raise_on_events=OjpSourceError("OJP returned HTTP 503"),
    )

    result = get_station_board("Zürich HB", client=client, settings=_settings())

    assert result.status == "source_error"
    assert result.events == []


def test_no_events_returns_not_found():
    client = StubOjpClient(candidates=[_swiss_station()], events=[])

    result = get_station_board("Zürich HB", client=client, settings=_settings())

    assert result.status == "not_found"
    assert result.station_name == "Zürich HB"
