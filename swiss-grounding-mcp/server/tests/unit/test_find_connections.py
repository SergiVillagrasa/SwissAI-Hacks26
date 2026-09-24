from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Connection, StopCandidate
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.find_connections import find_train_connections


class StubOjpClient:
    def __init__(self, *, candidates_by_name=None, connections=None, raise_on_trip=None):
        self.candidates_by_name = candidates_by_name or {}
        self.connections = connections if connections is not None else []
        self.raise_on_trip = raise_on_trip
        self.trip_calls = []

    def location_information(self, name):
        return self.candidates_by_name.get(name, [])

    def trip_request(self, origin_ref, destination_ref, **kwargs):
        self.trip_calls.append({"origin_ref": origin_ref, "destination_ref": destination_ref, **kwargs})
        if self.raise_on_trip is not None:
            raise self.raise_on_trip
        return self.connections


def _settings() -> Settings:
    return Settings.from_env({"OJP_BASE_URL": "https://example.test/ojp20"})


def _connection() -> Connection:
    return Connection(
        departure="2026-09-24T18:04:00Z",
        arrival="2026-09-24T18:57:00Z",
        duration_minutes=53,
        changes=0,
        legs=[],
    )


def test_missing_origin_returns_needs_clarification():
    client = StubOjpClient()

    result = find_train_connections(
        "", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert "origin" in result.message.lower()


def test_valid_stations_return_ok_with_provenance():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Bern", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert len(result.connections) == 1
    assert result.provenance.source_url == "https://example.test/ojp20"
    assert client.trip_calls[0]["origin_ref"] == "ch:1:sloid:7000"
    assert client.trip_calls[0]["destination_ref"] == "ch:1:sloid:8503000"


def test_unresolvable_station_returns_not_found():
    client = StubOjpClient(candidates_by_name={"Atlantis": [], "Bern": [
        StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)
    ]})

    result = find_train_connections(
        "Atlantis", "Bern", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "not_found"


def test_genuinely_ambiguous_station_returns_needs_clarification_with_candidates():
    client = StubOjpClient(
        candidates_by_name={
            "Fribourg": [
                StopCandidate(name="Fribourg/Freiburg", stop_ref="ch:1:sloid:7100", probability=0.62),
                StopCandidate(
                    name="Freiburg(Breisgau) Hbf", stop_ref="de:1:sloid:1", probability=0.58
                ),
            ],
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
        }
    )

    result = find_train_connections(
        "Fribourg", "Bern", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert len(result.candidates) == 2


def test_dominant_match_auto_resolves_despite_multiple_candidates():
    client = StubOjpClient(
        candidates_by_name={
            "Bern City": [
                StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0),
                StopCandidate(name="Bern, Bümpliz", stop_ref="ch:1:sloid:7062", probability=0.3),
            ],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Bern City", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert client.trip_calls[0]["origin_ref"] == "ch:1:sloid:7000"


def test_accented_and_alternate_names_resolve_without_clarification():
    client = StubOjpClient(
        candidates_by_name={
            "Geneve": [
                StopCandidate(name="Genève", stop_ref="ch:1:sloid:9000", probability=0.55),
                StopCandidate(
                    name="Genève-Aéroport", stop_ref="ch:1:sloid:9001", probability=0.50
                ),
            ],
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Geneve", "Bern", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert client.trip_calls[0]["origin_ref"] == "ch:1:sloid:9000"


def test_source_error_from_trip_request_returns_source_error_status():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        raise_on_trip=OjpSourceError("OJP returned HTTP 503"),
    )

    result = find_train_connections(
        "Bern", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "source_error"
    assert result.connections == []
    assert "503" in result.message


def test_both_times_given_departure_time_wins_and_message_says_so():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Bern",
        "Zürich HB",
        "2026-09-24T18:00:00Z",
        "2026-09-24T20:00:00Z",
        3,
        client=client,
        settings=_settings(),
    )

    assert result.status == "ok"
    assert client.trip_calls[0]["departure_time"] == "2026-09-24T18:00:00Z"
    assert client.trip_calls[0]["arrival_time"] is None
    assert "departure_time" in result.message


def test_results_parameter_is_clamped_to_valid_range():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    find_train_connections(
        "Bern", "Zürich HB", None, None, 0, client=client, settings=_settings()
    )
    assert client.trip_calls[0]["number_of_results"] == 1

    find_train_connections(
        "Bern", "Zürich HB", None, None, 500, client=client, settings=_settings()
    )
    assert client.trip_calls[1]["number_of_results"] == 5
