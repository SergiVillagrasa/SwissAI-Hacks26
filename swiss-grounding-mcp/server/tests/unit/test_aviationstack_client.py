import json
from pathlib import Path

import httpx
import pytest

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.aviationstack.client import (
    AviationstackClient,
    AviationstackSourceError,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "aviationstack"


def _read_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _settings(**overrides) -> Settings:
    env = {
        "AVIATIONSTACK_API_KEY": "test-key",
        "AVIATIONSTACK_BASE_URL": "https://example.test/v1",
        "AVIATIONSTACK_CACHE_SECONDS": "60",
    }
    env.update(overrides)
    return Settings.from_env(env)


def _client_with_transport(handler, settings=None) -> AviationstackClient:
    transport = httpx.MockTransport(handler)
    client = AviationstackClient(settings or _settings())
    client._http = httpx.Client(transport=transport)
    return client


def test_get_flights_returns_parsed_json_and_sends_access_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=_read_json("lx14_zrh_jfk.json"))

    client = _client_with_transport(handler)

    body = client.get_flights({"flight_iata": "LX14", "flight_date": "2026-09-25"})

    assert seen["params"]["access_key"] == "test-key"
    assert seen["params"]["flight_iata"] == "LX14"
    assert len(body["data"]) == 1


def test_empty_data_array_does_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_read_json("empty.json"))

    client = _client_with_transport(handler)

    body = client.get_flights({"flight_iata": "XX0000"})

    assert body["data"] == []


def test_embedded_error_object_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_read_json("error_quota.json"))

    client = _client_with_transport(handler)

    with pytest.raises(AviationstackSourceError, match="usage_limit_reached"):
        client.get_flights({"flight_iata": "LX14"})


def test_non_2xx_response_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    client = _client_with_transport(handler)

    with pytest.raises(AviationstackSourceError):
        client.get_flights({"flight_iata": "LX14"})


def test_network_error_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client_with_transport(handler)

    with pytest.raises(AviationstackSourceError):
        client.get_flights({"flight_iata": "LX14"})


def test_disabled_client_raises_source_error_without_http_call():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP call should not happen when disabled")

    client = _client_with_transport(handler, settings=_settings(AVIATIONSTACK_ENABLE="false"))

    with pytest.raises(AviationstackSourceError, match="disabled"):
        client.get_flights({"flight_iata": "LX14"})


def test_missing_api_key_raises_source_error_without_http_call():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP call should not happen without an API key")

    client = _client_with_transport(handler, settings=_settings(AVIATIONSTACK_API_KEY=""))

    with pytest.raises(AviationstackSourceError, match="API key"):
        client.get_flights({"flight_iata": "LX14"})


def test_repeated_call_within_cache_window_reuses_response():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_read_json("lx14_zrh_jfk.json"))

    client = _client_with_transport(handler)

    client.get_flights({"flight_iata": "LX14", "flight_date": "2026-09-25"})
    client.get_flights({"flight_iata": "LX14", "flight_date": "2026-09-25"})

    assert call_count["n"] == 1


def test_call_after_cache_expiry_hits_http_again():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_read_json("lx14_zrh_jfk.json"))

    client = _client_with_transport(handler, settings=_settings(AVIATIONSTACK_CACHE_SECONDS="0"))

    client.get_flights({"flight_iata": "LX14"})
    client.get_flights({"flight_iata": "LX14"})

    assert call_count["n"] == 2
