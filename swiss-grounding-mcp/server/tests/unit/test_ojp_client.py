from pathlib import Path

import httpx
import pytest

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.ojp.client import OjpClient, OjpSourceError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ojp"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _settings() -> Settings:
    return Settings.from_env(
        {"OJP_API_TOKEN": "test-token", "OJP_BASE_URL": "https://example.test/ojp20"}
    )


def _client_with_transport(handler) -> OjpClient:
    transport = httpx.MockTransport(handler)
    client = OjpClient(_settings())
    client._http = httpx.Client(transport=transport)
    return client


def test_location_information_returns_parsed_candidates():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.headers["content-type"] == "application/xml"
        return httpx.Response(200, content=_read("lir_response_single_match.xml"))

    client = _client_with_transport(handler)

    candidates = client.location_information("Bern")

    assert len(candidates) == 1
    assert candidates[0].name == "Bern"


def test_trip_request_returns_parsed_connections():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_read("trip_response_two_trips.xml"))

    client = _client_with_transport(handler)

    connections = client.trip_request("ch:1:sloid:7000", "ch:1:sloid:8503000")

    assert len(connections) == 2


def test_trip_request_forwards_via_ref_in_request_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, content=_read("trip_response_two_trips.xml"))

    client = _client_with_transport(handler)

    client.trip_request(
        "ch:1:sloid:9000",
        "ch:1:sloid:8503000",
        via_ref="ch:1:sloid:7000",
        via_name="Bern",
    )

    assert b"<Via>" in captured["body"]
    assert b"ch:1:sloid:7000" in captured["body"]
    assert b"Bern" in captured["body"]


def test_non_2xx_response_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"service unavailable")

    client = _client_with_transport(handler)

    with pytest.raises(OjpSourceError):
        client.location_information("Bern")


def test_embedded_service_delivery_error_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_read("lir_response_error.xml"))

    client = _client_with_transport(handler)

    with pytest.raises(OjpSourceError, match="Invalid API token"):
        client.location_information("Bern")


def test_network_error_raises_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client_with_transport(handler)

    with pytest.raises(OjpSourceError):
        client.location_information("Bern")
