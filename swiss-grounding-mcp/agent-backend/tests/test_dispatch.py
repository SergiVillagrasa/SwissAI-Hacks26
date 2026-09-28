import pytest

from agent_backend import dispatch as dispatch_module
from agent_backend.dispatch import UnknownToolError, dispatch


class _Sentinel:
    """Marker object so tests can assert exact identity was forwarded."""


def test_find_connections_forwards_arguments_and_clients(monkeypatch):
    captured = {}

    def fake_find_train_connections(origin, destination, departure_time, arrival_time, results, sort_by=None, *, client, settings):
        captured.update(
            origin=origin, destination=destination, departure_time=departure_time,
            arrival_time=arrival_time, results=results, sort_by=sort_by, client=client, settings=settings,
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
    assert captured["client"] is ojp_client
    assert captured["settings"] is settings


def test_find_connections_forwards_sort_by(monkeypatch):
    captured = {}

    def fake_find_train_connections(origin, destination, departure_time, arrival_time, results, sort_by=None, *, client, settings):
        captured["sort_by"] = sort_by
        return "connections-result"

    monkeypatch.setattr(dispatch_module, "find_train_connections", fake_find_train_connections)

    dispatch(
        "find_connections",
        {"origin": "Bern", "destination": "Zürich HB", "sort_by": "departure"},
        ojp_client=_Sentinel(), aviation_client=_Sentinel(), settings=_Sentinel(),
    )

    assert captured["sort_by"] == "departure"


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
