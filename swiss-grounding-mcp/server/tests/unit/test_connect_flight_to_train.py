from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import (
    Connection,
    ConnectionSearchResult,
    FareProduct,
    StopCandidate,
)
from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxSourceError
from swiss_grounding_mcp.tools.connect_flight_to_train import connect_flight_to_train

_LX15_ARRIVAL_ITEMS = [
    {
        "number": "LX 15",
        "status": "Scheduled",
        "airline": {"name": "Swiss", "iata": "LX", "icao": "SWR"},
        "departure": {
            "airport": {"iata": "JFK", "icao": "KJFK", "name": "JFK"},
            "scheduledTime": {"utc": "2026-09-25 09:00Z", "local": "2026-09-25 05:00-04:00"},
            "revisedTime": None,
            "runwayTime": None,
            "terminal": None,
            "gate": None,
        },
        "arrival": {
            "airport": {"iata": "ZRH", "icao": "LSZH", "name": "Zurich"},
            "scheduledTime": {"utc": "2026-09-25 22:00Z"},
            "revisedTime": {"utc": "2026-09-25 22:10Z"},
            "runwayTime": None,
            "terminal": "2",
            "gate": None,
        },
    }
]


class StubAerodataboxClient:
    def __init__(self, items=None, raise_error=None):
        self.items = items if items is not None else []
        self.raise_error = raise_error

    def get_flight_by_number(self, flight_number, date_local):
        if self.raise_error is not None:
            raise self.raise_error
        return self.items


class StubOjpClient:
    def __init__(self, fares=None):
        self.trip_calls = []
        self.fares = fares if fares is not None else []

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

    def fare_request(self, origin_ref, destination_ref, **kwargs):
        return self.fares


def _settings() -> Settings:
    return Settings.from_env({"AERODATABOX_BASE_URL": "https://example.test"})


def test_missing_destination_returns_needs_context():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "", 60, 3,
        aviation_client=StubAerodataboxClient(items=_LX15_ARRIVAL_ITEMS),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"


def test_buffer_below_minimum_returns_needs_context():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 5, 3,
        aviation_client=StubAerodataboxClient(items=_LX15_ARRIVAL_ITEMS),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"
    assert "buffer" in result.message.lower()


def test_missing_flight_and_confirmed_time_returns_needs_context():
    result = connect_flight_to_train(
        None, None, None, "Bern", 60, 3,
        aviation_client=StubAerodataboxClient(items=_LX15_ARRIVAL_ITEMS),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"


def test_flight_lookup_success_computes_buffered_departure_and_calls_ojp():
    ojp_client = StubOjpClient()
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAerodataboxClient(items=_LX15_ARRIVAL_ITEMS),
        ojp_client=ojp_client,
        settings=_settings(),
    )

    assert result.status == "answered"
    assert result.flight.flight_number == "LX15"
    assert result.flight.booking_url == (
        "https://www.google.com/travel/flights?q=Flights+from+JFK+to+ZRH+on+2026-09-25"
    )
    assert len(result.train_connections) == 1
    assert result.flight_provenance.source == "AeroDataBox (aerodatabox.com)"
    assert result.rail_provenance is not None
    assert result.rail_provenance is not result.flight_provenance
    assert ojp_client.trip_calls[0]["departure_time"] == "2026-09-25T23:10:00+00:00"


def test_answered_result_includes_sbb_booking_link_and_cheapest_fare():
    ojp_client = StubOjpClient(
        fares=[
            FareProduct(product="Single ticket 1st", price_chf=51.0, class_of_travel="1"),
            FareProduct(product="Single ticket 2nd", price_chf=31.0, class_of_travel="2"),
        ]
    )
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAerodataboxClient(items=_LX15_ARRIVAL_ITEMS),
        ojp_client=ojp_client,
        settings=_settings(),
    )

    assert result.status == "answered"
    assert result.train_booking_url is not None
    assert result.train_booking_url.startswith("https://sbb.ch/en?")
    assert "nach=Bern" in result.train_booking_url
    # The buffered departure is 2026-09-25T23:10:00Z, which is already
    # 2026-09-26 in Europe/Zurich (CEST, UTC+2) -- the deep link date must
    # follow Swiss local time, not the raw UTC date.
    assert "date=2026-09-26" in result.train_booking_url
    assert result.train_price_chf == 31.0


def test_unavailable_fares_still_include_sbb_booking_link_without_price():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAerodataboxClient(items=_LX15_ARRIVAL_ITEMS),
        ojp_client=StubOjpClient(fares=[]),
        settings=_settings(),
    )

    assert result.status == "answered"
    assert result.train_booking_url is not None
    assert result.train_booking_url.startswith("https://sbb.ch/en?")
    assert result.train_price_chf is None


def test_confirmed_arrival_time_skips_flight_lookup():
    ojp_client = StubOjpClient()
    result = connect_flight_to_train(
        None, None, "2026-09-25T22:00:00+00:00", "Bern", 30, 3,
        aviation_client=StubAerodataboxClient(raise_error=AerodataboxSourceError("should not be called")),
        ojp_client=ojp_client,
        settings=_settings(),
    )

    assert result.status == "answered"
    assert result.flight is None
    assert ojp_client.trip_calls[0]["departure_time"] == "2026-09-25T22:30:00+00:00"


def test_flight_lookup_source_unavailable_asks_for_confirmed_time():
    result = connect_flight_to_train(
        "LX15", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAerodataboxClient(raise_error=AerodataboxSourceError("quota exceeded")),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"
    assert "confirmed_arrival_time" in result.message


def test_flight_not_found_returns_insufficient_evidence():
    result = connect_flight_to_train(
        "XX999", "2026-09-25", None, "Bern", 60, 3,
        aviation_client=StubAerodataboxClient(items=[]),
        ojp_client=StubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "insufficient_evidence"


# ── Faithful propagation of find_train_connections statuses ─────────────
# A previous version of this function collapsed every non-"ok" train
# result into "source_unavailable", hiding genuine needs_clarification
# (with candidates) and out_of_scope outcomes behind a generic error.

class _StatusStubOjpClient(StubOjpClient):
    """Stub whose trip_request is never reached: find_train_connections is
    monkeypatched to return a canned non-"ok" ConnectionSearchResult."""


def test_train_needs_clarification_propagates_as_needs_context_with_candidates(monkeypatch):
    import swiss_grounding_mcp.tools.connect_flight_to_train as module

    candidates = [
        StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=0.55),
        StopCandidate(name="Berlin Hbf", stop_ref="de:1:sloid:1", probability=0.5),
    ]
    monkeypatch.setattr(
        module,
        "find_train_connections",
        lambda *args, **kwargs: ConnectionSearchResult(
            status="needs_clarification",
            message="Multiple stations match destination 'Ber'. Please pick one.",
            candidates=candidates,
        ),
    )

    result = connect_flight_to_train(
        None, None, "2026-09-25T22:00:00+00:00", "Ber", 30, 3,
        aviation_client=StubAerodataboxClient(),
        ojp_client=_StatusStubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "needs_context"
    assert len(result.candidates) == 2
    assert {c.name for c in result.candidates} == {"Bern", "Berlin Hbf"}


def test_train_out_of_scope_propagates_as_out_of_scope(monkeypatch):
    import swiss_grounding_mcp.tools.connect_flight_to_train as module

    monkeypatch.setattr(
        module,
        "find_train_connections",
        lambda *args, **kwargs: ConnectionSearchResult(
            status="out_of_scope",
            message="This service covers Swiss public transport only.",
        ),
    )

    result = connect_flight_to_train(
        None, None, "2026-09-25T22:00:00+00:00", "Lyon Part-Dieu", 30, 3,
        aviation_client=StubAerodataboxClient(),
        ojp_client=_StatusStubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "out_of_scope"


def test_train_source_error_propagates_as_source_unavailable(monkeypatch):
    import swiss_grounding_mcp.tools.connect_flight_to_train as module

    monkeypatch.setattr(
        module,
        "find_train_connections",
        lambda *args, **kwargs: ConnectionSearchResult(
            status="source_error",
            message="OJP returned HTTP 503",
        ),
    )

    result = connect_flight_to_train(
        None, None, "2026-09-25T22:00:00+00:00", "Bern", 30, 3,
        aviation_client=StubAerodataboxClient(),
        ojp_client=_StatusStubOjpClient(),
        settings=_settings(),
    )

    assert result.status == "source_unavailable"
