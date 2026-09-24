import json
from pathlib import Path

import httpx
import pytest

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.aerodatabox.client import (
    AerodataboxClient,
    AerodataboxSourceError,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "aerodatabox"


def _read_json(name: str):
    return json.loads((FIXTURES / name).read_text())


def _settings(**overrides) -> Settings:
    env = {
        "AERODATABOX_API_KEY": "test-key",
        "AERODATABOX_HOST": "aerodatabox.p.rapidapi.com",
        "AERODATABOX_BASE_URL": "https://example.test",
        "AERODATABOX_CACHE_SECONDS": "60",
    }
    env.update(overrides)
    return Settings.from_env(env)


def _client_with_transport(handler, settings=None) -> AerodataboxClient:
    transport = httpx.MockTransport(handler)
    client = AerodataboxClient(settings or _settings())
    client._http = httpx.Client(transport=transport)
    return client


def test_get_flight_by_number_sends_rapidapi_headers_and_path():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json=_read_json("lx14_by_number.json"))

    client = _client_with_transport(handler)

    data = client.get_flight_by_number("LX14", "2026-09-25")

    assert seen["path"] == "/flights/number/LX14/2026-09-25"
    assert seen["headers"]["x-rapidapi-key"] == "test-key"
    assert seen["headers"]["x-rapidapi-host"] == "aerodatabox.p.rapidapi.com"
    assert len(data) == 1
    assert data[0]["number"] == "LX 14"


def test_get_flight_by_number_empty_array_does_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_read_json("empty_by_number.json"))

    client = _client_with_transport(handler)

    assert client.get_flight_by_number("XX9999", "2026-09-25") == []


def test_get_flight_by_number_204_no_content_returns_empty_list_not_error():
    # Confirmed live: AeroDataBox returns HTTP 204 with an empty body for
    # "no such flight", not a 200 with an empty array. This must be
    # treated as "no match", not a provider failure.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, content=b"")

    client = _client_with_transport(handler)

    assert client.get_flight_by_number("ZZ9999", "2026-09-25") == []


def test_get_airport_flights_sends_correct_path_and_query():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=_read_json("zrh_fids.json"))

    client = _client_with_transport(handler)

    body = client.get_airport_flights(
        "iata", "ZRH", "2026-09-25T00:00", "2026-09-25T12:00", direction="Departure"
    )

    assert seen["path"] == "/flights/airports/iata/ZRH/2026-09-25T00:00/2026-09-25T12:00"
    assert seen["params"]["direction"] == "Departure"
    assert len(body["departures"]) == 2


def test_non_2xx_response_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text='{"message":"not subscribed"}')

    client = _client_with_transport(handler)

    with pytest.raises(AerodataboxSourceError):
        client.get_flight_by_number("LX14", "2026-09-25")


def test_network_error_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client_with_transport(handler)

    with pytest.raises(AerodataboxSourceError):
        client.get_flight_by_number("LX14", "2026-09-25")


def test_disabled_client_raises_source_error_without_http_call():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP call should not happen when disabled")

    client = _client_with_transport(handler, settings=_settings(AERODATABOX_ENABLE="false"))

    with pytest.raises(AerodataboxSourceError, match="disabled"):
        client.get_flight_by_number("LX14", "2026-09-25")


def test_missing_api_key_raises_source_error_without_http_call():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP call should not happen without an API key")

    client = _client_with_transport(handler, settings=_settings(AERODATABOX_API_KEY=""))

    with pytest.raises(AerodataboxSourceError, match="API key"):
        client.get_flight_by_number("LX14", "2026-09-25")


def test_repeated_call_within_cache_window_reuses_response():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_read_json("lx14_by_number.json"))

    client = _client_with_transport(handler)

    client.get_flight_by_number("LX14", "2026-09-25")
    client.get_flight_by_number("LX14", "2026-09-25")

    assert call_count["n"] == 1


def test_call_after_cache_expiry_hits_http_again():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_read_json("lx14_by_number.json"))

    client = _client_with_transport(handler, settings=_settings(AERODATABOX_CACHE_SECONDS="0"))

    client.get_flight_by_number("LX14", "2026-09-25")
    client.get_flight_by_number("LX14", "2026-09-25")

    assert call_count["n"] == 2
