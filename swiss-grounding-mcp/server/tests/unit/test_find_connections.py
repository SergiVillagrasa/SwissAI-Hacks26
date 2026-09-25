from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Connection, StopCandidate
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.find_connections import find_train_connections


class StubOjpClient:
    def __init__(self, *, candidates_by_name=None, connections=None, raise_on_trip=None, raise_on_location=None):
        self.candidates_by_name = candidates_by_name or {}
        self.connections = connections if connections is not None else []
        self.raise_on_trip = raise_on_trip
        self.raise_on_location = raise_on_location
        self.trip_calls = []

    def location_information(self, name):
        if self.raise_on_location is not None:
            raise self.raise_on_location
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


def test_purely_foreign_route_returns_out_of_scope_without_trip_request():
    client = StubOjpClient(
        candidates_by_name={
            "Paris Gare de Lyon": [
                StopCandidate(
                    name="Paris Gare de Lyon", stop_ref="fr:1:sloid:1", probability=1.0
                )
            ],
            "Marseille": [
                StopCandidate(name="Marseille", stop_ref="fr:1:sloid:2", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Paris Gare de Lyon",
        "Marseille",
        None,
        None,
        3,
        client=client,
        settings=_settings(),
    )

    assert result.status == "out_of_scope"
    assert result.connections == []
    assert "foreign" in result.message.lower()
    assert client.trip_calls == []


def test_inbound_cross_border_route_returns_ok():
    client = StubOjpClient(
        candidates_by_name={
            "Paris Gare de Lyon": [
                StopCandidate(
                    name="Paris Gare de Lyon", stop_ref="fr:1:sloid:1", probability=1.0
                )
            ],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Paris Gare de Lyon",
        "Zürich HB",
        None,
        None,
        3,
        client=client,
        settings=_settings(),
    )

    assert result.status == "ok"
    assert len(result.connections) == 1
    assert client.trip_calls[0]["origin_ref"] == "fr:1:sloid:1"
    assert client.trip_calls[0]["destination_ref"] == "ch:1:sloid:8503000"


def test_outbound_cross_border_route_returns_ok():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Milano Centrale": [
                StopCandidate(
                    name="Milano Centrale", stop_ref="it:1:sloid:3", probability=1.0
                )
            ],
        },
        connections=[_connection()],
    )

    result = find_train_connections(
        "Bern", "Milano Centrale", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert len(result.connections) == 1
    assert client.trip_calls[0]["destination_ref"] == "it:1:sloid:3"


def test_connections_are_truncated_to_requested_results():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[_connection(), _connection(), _connection()],
    )

    result = find_train_connections(
        "Bern", "Zürich HB", None, None, 2, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert len(result.connections) == 2


def test_bare_numeric_swiss_uic_stop_ref_is_accepted():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="8507000", probability=1.0)],
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
    assert client.trip_calls[0]["origin_ref"] == "8507000"


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


def test_sort_by_departure_orders_connections_soonest_first():
    later = Connection(
        departure="2026-09-24T19:04:00Z",
        arrival="2026-09-24T19:57:00Z",
        duration_minutes=53,
        changes=0,
        legs=[],
    )
    sooner = _connection()
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[later, sooner],
    )

    result = find_train_connections(
        "Bern", "Zürich HB", None, None, 3, "departure",
        client=client, settings=_settings(),
    )

    assert result.status == "ok"
    assert [c.departure for c in result.connections] == [
        "2026-09-24T18:04:00Z",
        "2026-09-24T19:04:00Z",
    ]
    assert result.sorted_by == "departure"


def test_no_sort_by_keeps_source_order_and_no_sorted_by():
    later = Connection(
        departure="2026-09-24T19:04:00Z",
        arrival="2026-09-24T19:57:00Z",
        duration_minutes=53,
        changes=0,
        legs=[],
    )
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        },
        connections=[later, _connection()],
    )

    result = find_train_connections(
        "Bern", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert [c.departure for c in result.connections] == [
        "2026-09-24T19:04:00Z",
        "2026-09-24T18:04:00Z",
    ]
    assert result.sorted_by is None


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


class _MarginStubOjpClient(StubOjpClient):
    """Stub whose trip_request only succeeds once a margin has been applied."""

    def __init__(self, *, candidates_by_name, connections):
        super().__init__(candidates_by_name=candidates_by_name)
        self._connections = connections

    def trip_request(self, origin_ref, destination_ref, **kwargs):
        self.trip_calls.append({"origin_ref": origin_ref, "destination_ref": destination_ref, **kwargs})
        # Only the retried (margin-adjusted) call returns results; the
        # exact-time call it replaces returns nothing, mimicking a train
        # that departs/arrives a minute or two off the requested instant.
        if len(self.trip_calls) == 1:
            return []
        return self._connections


def test_exact_departure_time_miss_retries_with_margin_and_succeeds():
    client = _MarginStubOjpClient(
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
        None,
        3,
        client=client,
        settings=_settings(),
    )

    assert result.status == "ok"
    assert len(result.connections) == 1
    assert len(client.trip_calls) == 2
    # The retry shifts the departure floor earlier so a train departing
    # shortly after the requested time is still included.
    assert client.trip_calls[0]["departure_time"] == "2026-09-24T18:00:00Z"
    assert client.trip_calls[1]["departure_time"] == "2026-09-24T17:50:00Z"
    assert "margin" in result.message.lower()


def test_exact_arrival_time_miss_retries_with_margin_and_succeeds():
    client = _MarginStubOjpClient(
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
        None,
        "2026-09-24T18:00:00Z",
        3,
        client=client,
        settings=_settings(),
    )

    assert result.status == "ok"
    assert len(client.trip_calls) == 2
    assert client.trip_calls[0]["arrival_time"] == "2026-09-24T18:00:00Z"
    assert client.trip_calls[1]["arrival_time"] == "2026-09-24T18:10:00Z"
    assert "margin" in result.message.lower()


def test_no_time_given_does_not_retry_on_empty_results():
    client = _MarginStubOjpClient(
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

    # No departure/arrival time was given, so there is nothing to widen;
    # the first (and only) empty result must be reported as not_found.
    assert result.status == "not_found"
    assert len(client.trip_calls) == 1


def test_source_error_from_location_information_returns_source_error_status():
    client = StubOjpClient(
        raise_on_location=OjpSourceError("OJP returned HTTP 403"),
    )

    result = find_train_connections(
        "Bern", "Zürich HB", None, None, 3, client=client, settings=_settings()
    )

    assert result.status == "source_error"
    assert result.connections == []
    assert "403" in result.message
