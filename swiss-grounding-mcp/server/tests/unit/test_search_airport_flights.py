from datetime import datetime, timezone

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxSourceError
from swiss_grounding_mcp.tools.search_airport_flights import search_airport_flights


def _departure_item(
    number,
    arr_iata,
    arr_icao="XXXX",
    airline_iata="LX",
    dep_scheduled_utc="2026-09-25 10:20Z",
    dep_scheduled_local="2026-09-25 12:20+02:00",
    dep_revised_utc=None,
    dep_runway_utc=None,
):
    return {
        "number": number,
        "status": "Scheduled",
        "airline": {"name": "Swiss", "iata": airline_iata, "icao": "SWR"},
        "departure": {
            "airport": {"iata": "ZRH", "icao": "LSZH", "name": "Zurich"},
            "scheduledTime": {"utc": dep_scheduled_utc, "local": dep_scheduled_local},
            "revisedTime": {"utc": dep_revised_utc} if dep_revised_utc else None,
            "runwayTime": {"utc": dep_runway_utc} if dep_runway_utc else None,
            "terminal": "1",
            "gate": "A12",
        },
        "arrival": {
            "airport": {"iata": arr_iata, "icao": arr_icao, "name": arr_iata},
            "scheduledTime": {"utc": "2026-09-25 13:10Z"},
            "revisedTime": None,
            "runwayTime": None,
            "terminal": None,
            "gate": None,
        },
    }


_TWO_FLIGHTS_WINDOW_1 = {"departures": [_departure_item("LX14", "JFK")], "arrivals": []}
_TWO_FLIGHTS_WINDOW_2 = {"departures": [_departure_item("LX16", "LHR")], "arrivals": []}
_EMPTY_WINDOW = {"departures": [], "arrivals": []}


class StubAerodataboxClient:
    def __init__(self, windows=None, raise_error=None):
        # windows: list of dicts to return in sequence, one per call
        self.windows = list(windows) if windows is not None else []
        self.raise_error = raise_error
        self.calls = []

    def get_airport_flights(self, code_type, code, from_local, to_local, *, direction="Both"):
        self.calls.append(
            {
                "code_type": code_type,
                "code": code,
                "from_local": from_local,
                "to_local": to_local,
                "direction": direction,
            }
        )
        if self.raise_error is not None:
            raise self.raise_error
        return self.windows[len(self.calls) - 1]


def _settings() -> Settings:
    return Settings.from_env({"AERODATABOX_BASE_URL": "https://example.test"})


def test_missing_direction_returns_needs_context():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])

    result = search_airport_flights(
        "", "2026-09-25", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"
    assert client.calls == []


def test_missing_flight_date_returns_needs_context():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])

    result = search_airport_flights(
        "departure", "", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"


def test_no_filters_lists_all_flights_for_the_direction():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])

    result = search_airport_flights(
        "departure", "2026-09-25", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert len(result.flights) == 2
    assert client.calls[0]["direction"] == "Departure"


def test_no_filters_and_no_flights_returns_insufficient_evidence():
    client = StubAerodataboxClient(windows=[_EMPTY_WINDOW, _EMPTY_WINDOW])

    result = search_airport_flights(
        "departure", "2026-09-25", None, None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "insufficient_evidence"
    assert "ZRH" in result.message


def test_blank_filters_are_treated_as_unset():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])

    result = search_airport_flights(
        "departure", "2026-09-25", "  ", "", None, 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert len(result.flights) == 2


def test_zrh_iata_as_counterpart_filter_returns_needs_context():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])

    result = search_airport_flights(
        "departure", "2026-09-25", "ZRH", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"
    assert "ZRH" in result.message
    assert client.calls == []


def test_zrh_icao_as_counterpart_filter_returns_needs_context():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])

    result = search_airport_flights(
        "departure", "2026-09-25", None, "LSZH", None, 10, client=client, settings=_settings()
    )

    assert result.status == "needs_context"
    assert client.calls == []


def test_departure_search_covers_full_day_with_two_windows():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])

    result = search_airport_flights(
        "departure", "2026-09-25", None, None, "LX", 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert len(result.flights) == 2
    assert client.calls[0]["code_type"] == "iata"
    assert client.calls[0]["code"] == "ZRH"
    assert client.calls[0]["from_local"] == "2026-09-25T00:00"
    assert client.calls[0]["to_local"] == "2026-09-25T12:00"
    assert client.calls[0]["direction"] == "Departure"
    assert client.calls[1]["from_local"] == "2026-09-25T12:00"
    assert client.calls[1]["to_local"] == "2026-09-26T00:00"


def test_arrival_direction_maps_to_capitalized_arrival():
    client = StubAerodataboxClient(windows=[_EMPTY_WINDOW, _EMPTY_WINDOW])

    search_airport_flights(
        "arrival", "2026-09-25", None, None, "LX", 10, client=client, settings=_settings()
    )

    assert client.calls[0]["direction"] == "Arrival"


def test_destination_airport_filter_excludes_non_matching_flights():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])

    result = search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert len(result.flights) == 1
    assert result.flights[0].arrival.airport.iata == "JFK"


def test_answered_flights_include_https_booking_urls():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _EMPTY_WINDOW])

    result = search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert result.flights[0].booking_url == (
        "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+JFK+on+2026-09-25"
    )


def test_easyjet_flight_gets_prefilled_booking_url():
    windows = [
        {"departures": [_departure_item("U2456", "LGW", airline_iata="U2")], "arrivals": []},
        _EMPTY_WINDOW,
    ]
    client = StubAerodataboxClient(windows=windows)

    result = search_airport_flights(
        "departure", "2026-09-25", "LGW", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "answered"
    assert result.flights[0].booking_url == (
        "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+LGW+on+2026-09-25"
    )


def test_no_matching_flights_returns_insufficient_evidence():
    client = StubAerodataboxClient(windows=[_EMPTY_WINDOW, _EMPTY_WINDOW])

    result = search_airport_flights(
        "departure", "2026-09-25", "XXX", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "insufficient_evidence"
    assert result.flights == []


def test_source_failure_returns_source_unavailable():
    client = StubAerodataboxClient(raise_error=AerodataboxSourceError("network down"))

    result = search_airport_flights(
        "departure", "2026-09-25", "JFK", None, None, 10, client=client, settings=_settings()
    )

    assert result.status == "source_unavailable"


def test_today_excludes_already_departed_flights_and_sorts_by_time():
    # now is 10:00 UTC on 2026-09-28. One flight already left at 08:00,
    # two more haven't yet, given out of chronological order.
    windows = [
        {
            "departures": [
                _departure_item(
                    "LX16", "LHR", dep_scheduled_utc="2026-09-28 14:00Z",
                    dep_scheduled_local="2026-09-28 16:00+02:00",
                ),
                _departure_item(
                    "LX00", "GVA", dep_scheduled_utc="2026-09-28 08:00Z",
                    dep_scheduled_local="2026-09-28 10:00+02:00",
                ),
                _departure_item(
                    "LX14", "JFK", dep_scheduled_utc="2026-09-28 11:00Z",
                    dep_scheduled_local="2026-09-28 13:00+02:00",
                ),
            ],
            "arrivals": [],
        },
        _EMPTY_WINDOW,
    ]
    client = StubAerodataboxClient(windows=windows)
    now = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)

    result = search_airport_flights(
        "departure", "2026-09-28", None, None, None, 10,
        client=client, settings=_settings(), now=now,
    )

    assert result.status == "answered"
    assert [f.flight_number for f in result.flights] == ["LX14", "LX16"]


def test_today_all_flights_already_departed_returns_helpful_message():
    windows = [
        {
            "departures": [
                _departure_item(
                    "LX00", "GVA", dep_scheduled_utc="2026-09-28 08:00Z",
                    dep_scheduled_local="2026-09-28 10:00+02:00",
                ),
            ],
            "arrivals": [],
        },
        _EMPTY_WINDOW,
    ]
    client = StubAerodataboxClient(windows=windows)
    now = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)

    result = search_airport_flights(
        "departure", "2026-09-28", None, None, None, 10,
        client=client, settings=_settings(), now=now,
    )

    assert result.status == "insufficient_evidence"
    assert "already departed" in result.message


def test_past_date_is_not_time_filtered_even_if_before_now():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])
    now = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)

    result = search_airport_flights(
        "departure", "2026-09-25", None, None, None, 10,
        client=client, settings=_settings(), now=now,
    )

    assert result.status == "answered"
    assert len(result.flights) == 2


def test_limit_is_clamped_to_valid_range():
    client = StubAerodataboxClient(windows=[_TWO_FLIGHTS_WINDOW_1, _TWO_FLIGHTS_WINDOW_2])

    result = search_airport_flights(
        "departure", "2026-09-25", None, None, "LX", 1, client=client, settings=_settings()
    )

    assert len(result.flights) == 1
