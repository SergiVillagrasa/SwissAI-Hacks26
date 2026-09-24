from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxSourceError
from swiss_grounding_mcp.tools.find_flight_by_number import find_flight_by_number

_LX14_ITEMS = [
    {
        "number": "LX 14",
        "callSign": "SWR14",
        "status": "Scheduled",
        "codeshareStatus": "IsOperator",
        "isCargo": False,
        "aircraft": {"model": "Airbus A220-300"},
        "airline": {"name": "Swiss", "iata": "LX", "icao": "SWR"},
        "departure": {
            "airport": {"iata": "ZRH", "icao": "LSZH", "name": "Zurich"},
            "scheduledTime": {"utc": "2026-09-25 10:20Z", "local": "2026-09-25 12:20+02:00"},
            "revisedTime": {"utc": "2026-09-25 10:25Z", "local": "2026-09-25 12:25+02:00"},
            "runwayTime": None,
            "terminal": "1",
            "checkInDesk": "12-18",
            "gate": "A12",
            "quality": ["Basic", "Live"],
        },
        "arrival": {
            "airport": {"iata": "JFK", "icao": "KJFK", "name": "John F Kennedy Intl"},
            "scheduledTime": {"utc": "2026-09-25 13:10Z", "local": "2026-09-25 09:10-04:00"},
            "revisedTime": None,
            "runwayTime": None,
            "terminal": "4",
            "gate": None,
            "baggageBelt": None,
            "quality": ["Basic"],
        },
    }
]

_EMPTY_ITEMS: list = []


class StubAerodataboxClient:
    def __init__(self, items=None, raise_error=None):
        self.items = items if items is not None else []
        self.raise_error = raise_error
        self.calls = []

    def get_flight_by_number(self, flight_number, date_local):
        self.calls.append({"flight_number": flight_number, "date_local": date_local})
        if self.raise_error is not None:
            raise self.raise_error
        return self.items


def _settings() -> Settings:
    return Settings.from_env({"AERODATABOX_BASE_URL": "https://example.test"})


def test_missing_flight_number_returns_needs_context():
    client = StubAerodataboxClient(items=_LX14_ITEMS)

    result = find_flight_by_number("", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "needs_context"
    assert client.calls == []


def test_missing_flight_date_returns_needs_context():
    client = StubAerodataboxClient(items=_LX14_ITEMS)

    result = find_flight_by_number("LX14", "", None, client=client, settings=_settings())

    assert result.status == "needs_context"


def test_found_flight_returns_answered_with_provenance_and_field_lists():
    client = StubAerodataboxClient(items=_LX14_ITEMS)

    result = find_flight_by_number("LX14", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "answered"
    assert result.flight.flight_number == "LX14"
    assert "departure.scheduled" in result.fields_present
    assert "departure.actual" in result.fields_missing
    assert result.provenance.source == "AeroDataBox (aerodatabox.com)"
    assert result.provenance.applicable_date == "2026-09-25"
    assert result.provenance.timezone == "Europe/Zurich"
    assert client.calls[0]["flight_number"] == "LX14"
    assert client.calls[0]["date_local"] == "2026-09-25"


def test_flight_number_is_normalized_before_query():
    client = StubAerodataboxClient(items=_LX14_ITEMS)

    find_flight_by_number("lx 14", "2026-09-25", None, client=client, settings=_settings())

    assert client.calls[0]["flight_number"] == "LX14"


def test_direction_arrival_filters_by_zrh_arrival():
    client = StubAerodataboxClient(items=_LX14_ITEMS)

    result = find_flight_by_number(
        "LX14", "2026-09-25", "arrival", client=client, settings=_settings()
    )

    # LX14 in the fixture departs from ZRH (not arrives), so an
    # arrival-at-ZRH filter must exclude it.
    assert result.status == "insufficient_evidence"


def test_direction_departure_matches_zrh_departure():
    client = StubAerodataboxClient(items=_LX14_ITEMS)

    result = find_flight_by_number(
        "LX14", "2026-09-25", "departure", client=client, settings=_settings()
    )

    assert result.status == "answered"


def test_no_matching_flight_returns_insufficient_evidence():
    client = StubAerodataboxClient(items=_EMPTY_ITEMS)

    result = find_flight_by_number("XX9999", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "insufficient_evidence"
    assert result.flight is None


def test_source_failure_returns_source_unavailable():
    client = StubAerodataboxClient(raise_error=AerodataboxSourceError("quota exceeded"))

    result = find_flight_by_number("LX14", "2026-09-25", None, client=client, settings=_settings())

    assert result.status == "source_unavailable"
    assert "quota exceeded" in result.message
