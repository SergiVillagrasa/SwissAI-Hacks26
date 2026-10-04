import pytest

from agent_backend import dispatch as dispatch_module
from agent_backend.dispatch import UnknownToolError, dispatch


class _Sentinel:
    """Marker object so tests can assert exact identity was forwarded."""


def test_find_connections_forwards_arguments_and_clients(monkeypatch):
    captured = {}

    def fake_find_train_connections(origin, destination, departure_time, arrival_time, results, sort_by=None, via=None, *, client, settings):
        captured.update(
            origin=origin, destination=destination, departure_time=departure_time,
            arrival_time=arrival_time, results=results, sort_by=sort_by, via=via, client=client, settings=settings,
        )
        return "connections-result"

    monkeypatch.setattr(dispatch_module, "find_train_connections", fake_find_train_connections)

    ojp_client, aviation_client, settings = _Sentinel(), _Sentinel(), _Sentinel()
    result = dispatch(
        "find_connections",
        {"origin": "Bern", "destination": "Zürich HB", "results": 2},
        ojp_client=ojp_client, aviation_client=aviation_client, settings=settings,
    )

    assert result == "connections-result"
    assert captured["origin"] == "Bern"
    assert captured["destination"] == "Zürich HB"
    assert captured["departure_time"] is None
    assert captured["arrival_time"] is None
    assert captured["results"] == 2
    assert captured["sort_by"] is None
    assert captured["via"] is None
    assert captured["client"] is ojp_client
    assert captured["settings"] is settings


def test_find_connections_forwards_sort_by(monkeypatch):
    captured = {}

    def fake_find_train_connections(origin, destination, departure_time, arrival_time, results, sort_by=None, via=None, *, client, settings):
        captured["sort_by"] = sort_by
        return "connections-result"

    monkeypatch.setattr(dispatch_module, "find_train_connections", fake_find_train_connections)

    dispatch(
        "find_connections",
        {"origin": "Bern", "destination": "Zürich HB", "sort_by": "departure"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert captured["sort_by"] == "departure"


def test_find_connections_forwards_via(monkeypatch):
    captured = {}

    def fake_find_train_connections(origin, destination, departure_time, arrival_time, results, sort_by=None, via=None, *, client, settings):
        captured["via"] = via
        return "connections-result"

    monkeypatch.setattr(dispatch_module, "find_train_connections", fake_find_train_connections)

    dispatch(
        "find_connections",
        {"origin": "Geneve", "destination": "Zürich HB", "via": "Bern"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert captured["via"] == "Bern"


def test_check_public_transport_fares_forwards_sort_by(monkeypatch):
    captured = {}

    def fake_check_fares(origin, destination, departure_time=None, travel_class="2", discount_card=None, sort_by=None, *, client, settings):
        captured.update(origin=origin, destination=destination, sort_by=sort_by)
        return "fares-result"

    monkeypatch.setattr(dispatch_module, "check_public_transport_fares", fake_check_fares)

    result = dispatch(
        "check_public_transport_fares",
        {"origin": "Bern", "destination": "Zürich HB", "sort_by": "price"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert result == "fares-result"
    assert captured["sort_by"] == "price"


def test_find_flight_by_number_uses_aviation_client(monkeypatch):
    captured = {}

    def fake_find_flight_by_number(flight_number, flight_date, direction, *, client, settings):
        captured.update(flight_number=flight_number, flight_date=flight_date, direction=direction, client=client)
        return "flight-result"

    monkeypatch.setattr(dispatch_module, "find_flight_by_number", fake_find_flight_by_number)

    aviation_client = _Sentinel()
    result = dispatch(
        "find_flight_by_number",
        {"flight_number": "LX14", "flight_date": "2026-09-25"},
        ojp_client=_Sentinel(), aviation_client=aviation_client, settings=_Sentinel(),
    )

    assert result == "flight-result"
    assert captured["flight_number"] == "LX14"
    assert captured["direction"] is None
    assert captured["client"] is aviation_client


def test_connect_flight_to_train_uses_both_clients(monkeypatch):
    captured = {}

    def fake_connect_flight_to_train(
        flight_number, flight_date, confirmed_arrival_time, destination_station,
        transfer_buffer_minutes, rail_results, *, aviation_client, ojp_client, settings,
    ):
        captured.update(
            destination_station=destination_station,
            transfer_buffer_minutes=transfer_buffer_minutes,
            aviation_client=aviation_client,
            ojp_client=ojp_client,
        )
        return "flight-to-train-result"

    monkeypatch.setattr(dispatch_module, "connect_flight_to_train", fake_connect_flight_to_train)

    ojp_client, aviation_client = _Sentinel(), _Sentinel()
    result = dispatch(
        "connect_flight_to_train",
        {"destination_station": "Luzern", "transfer_buffer_minutes": 45, "flight_number": "LX14", "flight_date": "2026-09-25"},
        ojp_client=ojp_client, aviation_client=aviation_client, settings=_Sentinel(),
    )

    assert result == "flight-to-train-result"
    assert captured["destination_station"] == "Luzern"
    assert captured["transfer_buffer_minutes"] == 45
    assert captured["ojp_client"] is ojp_client
    assert captured["aviation_client"] is aviation_client


def test_get_flight_fares_uses_flight_fares_client(monkeypatch):
    captured = {}

    def fake_get_flight_fares(origin_city, destination_city, outbound_date, currency, *, client, settings):
        captured.update(
            origin_city=origin_city, destination_city=destination_city,
            outbound_date=outbound_date, currency=currency, client=client, settings=settings,
        )
        return "flight-fares-result"

    monkeypatch.setattr(dispatch_module, "get_flight_fares", fake_get_flight_fares)

    flight_fares_client, settings = _Sentinel(), _Sentinel()
    result = dispatch(
        "get_flight_fares",
        {"origin_city": "Zurich", "destination_city": "Geneva"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=settings,
        flight_fares_client=flight_fares_client,
    )

    assert result == "flight-fares-result"
    assert captured["origin_city"] == "Zurich"
    assert captured["destination_city"] == "Geneva"
    assert captured["outbound_date"] is None
    assert captured["currency"] == "CHF"
    assert captured["client"] is flight_fares_client
    assert captured["settings"] is settings


def test_unknown_tool_raises():
    with pytest.raises(UnknownToolError):
        dispatch("not_a_real_tool", {}, ojp_client=None, aviation_client=None, settings=None)


# ── Numeric argument coercion (LLM tool-calling args are JSON, but a ────
# ── numeric field can still arrive as a string) ─────────────────────────

def test_find_connections_coerces_string_results_to_int(monkeypatch):
    captured = {}

    def fake_find_train_connections(origin, destination, departure_time, arrival_time, results, sort_by=None, via=None, *, client, settings):
        captured["results"] = results
        return "connections-result"

    monkeypatch.setattr(dispatch_module, "find_train_connections", fake_find_train_connections)

    dispatch(
        "find_connections",
        {"origin": "Bern", "destination": "Zürich HB", "results": "2"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert captured["results"] == 2
    assert isinstance(captured["results"], int)


def test_find_connections_falls_back_to_default_on_uncoercible_results(monkeypatch):
    captured = {}

    def fake_find_train_connections(origin, destination, departure_time, arrival_time, results, sort_by=None, via=None, *, client, settings):
        captured["results"] = results
        return "connections-result"

    monkeypatch.setattr(dispatch_module, "find_train_connections", fake_find_train_connections)

    dispatch(
        "find_connections",
        {"origin": "Bern", "destination": "Zürich HB", "results": "a lot"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert captured["results"] == 3


def test_get_station_board_coerces_string_results_to_int(monkeypatch):
    captured = {}

    def fake_get_station_board(station, mode, when, results, *, client, settings):
        captured.update(station=station, mode=mode, when=when, results=results)
        return "station-board-result"

    monkeypatch.setattr(dispatch_module, "get_station_board", fake_get_station_board)

    result = dispatch(
        "get_station_board",
        {"station": "Bern", "results": "3"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert result == "station-board-result"
    assert captured["results"] == 3
    assert isinstance(captured["results"], int)


def test_get_station_board_falls_back_to_default_on_uncoercible_results(monkeypatch):
    captured = {}

    def fake_get_station_board(station, mode, when, results, *, client, settings):
        captured["results"] = results
        return "station-board-result"

    monkeypatch.setattr(dispatch_module, "get_station_board", fake_get_station_board)

    dispatch(
        "get_station_board",
        {"station": "Bern", "results": "a lot"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert captured["results"] == 5


def test_find_connections_falls_back_to_default_on_non_finite_float_results(monkeypatch):
    # int(float("inf")) raises OverflowError, not ValueError/TypeError --
    # _coerce_int must catch that too instead of crashing the whole turn.
    captured = {}

    def fake_find_train_connections(origin, destination, departure_time, arrival_time, results, sort_by=None, via=None, *, client, settings):
        captured["results"] = results
        return "connections-result"

    monkeypatch.setattr(dispatch_module, "find_train_connections", fake_find_train_connections)

    dispatch(
        "find_connections",
        {"origin": "Bern", "destination": "Zürich HB", "results": float("inf")},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert captured["results"] == 3


def test_search_airport_flights_coerces_string_limit(monkeypatch):
    captured = {}

    def fake_search_airport_flights(direction, flight_date, airport_iata, airport_icao, airline_iata, limit, *, client, settings):
        captured["limit"] = limit
        return "flight-search-result"

    monkeypatch.setattr(dispatch_module, "search_airport_flights", fake_search_airport_flights)

    dispatch(
        "search_airport_flights",
        {"direction": "departure", "flight_date": "2026-09-25", "limit": "7"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert captured["limit"] == 7


def test_connect_flight_to_train_coerces_string_buffer_and_rail_results(monkeypatch):
    captured = {}

    def fake_connect_flight_to_train(
        flight_number, flight_date, confirmed_arrival_time, destination_station,
        transfer_buffer_minutes, rail_results, *, aviation_client, ojp_client, settings,
    ):
        captured.update(transfer_buffer_minutes=transfer_buffer_minutes, rail_results=rail_results)
        return "flight-to-train-result"

    monkeypatch.setattr(dispatch_module, "connect_flight_to_train", fake_connect_flight_to_train)

    dispatch(
        "connect_flight_to_train",
        {
            "destination_station": "Luzern",
            "transfer_buffer_minutes": "45",
            "rail_results": "4",
            "flight_number": "LX14",
            "flight_date": "2026-09-25",
        },
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert captured["transfer_buffer_minutes"] == 45
    assert captured["rail_results"] == 4
