from pathlib import Path

import httpx
import pytest

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import FareProduct, StopCandidate
from swiss_grounding_mcp.sources.ojp.client import OjpClient, OjpSourceError
from swiss_grounding_mcp.tools.fares import (
    build_sbb_deep_link,
    check_public_transport_fares,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ojp"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _settings() -> Settings:
    return Settings.from_env(
        {"OJP_BASE_URL": "https://example.test/ojp20"}
    )


class StubOjpClient:
    def __init__(self, *, candidates_by_name=None, fares=None, raise_on_fare=None):
        self.candidates_by_name = candidates_by_name or {}
        self.fares = fares if fares is not None else []
        self.raise_on_fare = raise_on_fare
        self.fare_calls = []

    def location_information(self, name):
        return self.candidates_by_name.get(name, [])

    def fare_request(self, origin_ref, destination_ref, **kwargs):
        self.fare_calls.append({"origin_ref": origin_ref, "destination_ref": destination_ref, **kwargs})
        if self.raise_on_fare is not None:
            raise self.raise_on_fare
        return self.fares


def _client_with_transport(handler) -> OjpClient:
    transport = httpx.MockTransport(handler)
    client = OjpClient(_settings())
    client._http = httpx.Client(transport=transport)
    return client


def test_build_sbb_deep_link_encodes_parameters():
    url = build_sbb_deep_link("Bern", "Zürich HB", "2026-10-15", "14:30")

    assert url.startswith("https://www.sbb.ch/en/timetable.html?")
    assert "from=Bern" in url
    assert "Z%C3%BCrich" in url
    assert "date=2026-10-15" in url
    assert "time=" in url
    assert "14" in url.split("time=")[1].split("&")[0]


def test_check_public_transport_fares_success_returns_priced_products():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)],
        },
        fares=[
            FareProduct(product="Single ticket", price_chf=31.0, class_of_travel="2", discount=None),
            FareProduct(product="Single ticket", price_chf=51.0, class_of_travel="1", discount=None),
        ],
    )

    result = check_public_transport_fares(
        "Bern",
        "Zürich HB",
        "2026-10-15T14:30:00+02:00",
        client=client,
        settings=_settings(),
    )

    assert result.status == "success"
    assert len(result.fares) == 2
    assert result.fares[0].price_chf == 31.0
    assert result.fares[0].class_of_travel == "2"
    assert result.provenance is not None
    assert "opentransportdata.swiss" in result.provenance.source
    assert result.provenance.booking_url is not None
    assert "sbb.ch" in result.provenance.booking_url


def test_check_public_transport_fares_api_500_returns_fallback_link():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)],
        },
        raise_on_fare=OjpSourceError("OJP returned HTTP 500"),
    )

    result = check_public_transport_fares(
        "Bern",
        "Zürich HB",
        "2026-10-15T14:30:00+02:00",
        client=client,
        settings=_settings(),
    )

    assert result.status == "fallback_link"
    assert result.booking_url is not None
    assert "sbb.ch" in result.booking_url
    assert result.provenance is not None
    assert result.provenance.booking_url == result.booking_url
    assert "OJP Fare Beta" in result.message
    assert result.fares == []


def test_check_public_transport_fares_international_route_returns_out_of_scope():
    client = StubOjpClient(
        candidates_by_name={
            "Zürich HB": [StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)],
            "Berlin Hbf": [StopCandidate(name="Berlin Hbf", stop_ref="de:1:sloid:1", probability=1.0)],
        },
    )

    result = check_public_transport_fares(
        "Zürich HB",
        "Berlin Hbf",
        "2026-10-15T14:30:00+02:00",
        client=client,
        settings=_settings(),
    )

    assert result.status == "out_of_scope"
    assert result.booking_url is not None
    assert result.provenance is not None
    assert result.provenance.booking_url == result.booking_url
    assert "international" in result.message.lower()
    assert result.fares == []
    assert client.fare_calls == []


def test_check_public_transport_fares_ambiguous_station_returns_needs_clarification():
    client = StubOjpClient(
        candidates_by_name={
            "Fribourg": [
                StopCandidate(name="Fribourg/Freiburg", stop_ref="ch:1:sloid:7100", probability=0.62),
                StopCandidate(name="Freiburg(Breisgau) Hbf", stop_ref="de:1:sloid:1", probability=0.58),
            ],
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
        },
    )

    result = check_public_transport_fares(
        "Fribourg",
        "Bern",
        "2026-10-15T14:30:00+02:00",
        client=client,
        settings=_settings(),
    )

    assert result.status == "needs_clarification"
    assert len(result.candidates) == 2
    assert result.fares == []


def test_fare_request_parses_valid_fare_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_read("fare_response_single_fare.xml"))

    client = _client_with_transport(handler)

    fares = client.fare_request(
        "ch:1:sloid:7000",
        "ch:1:sloid:8503000",
        departure_time="2026-09-24T14:30:00+02:00",
    )

    assert len(fares) == 2
    assert fares[0].product == "Single ticket"
    assert fares[0].price_chf == 31.0
    assert fares[0].class_of_travel == "2"


def test_fare_request_http_500_returns_empty_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"internal server error")

    client = _client_with_transport(handler)

    fares = client.fare_request(
        "ch:1:sloid:7000",
        "ch:1:sloid:8503000",
        departure_time="2026-09-24T14:30:00+02:00",
    )

    assert fares == []


def test_fare_request_network_error_returns_empty_list():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client_with_transport(handler)

    fares = client.fare_request(
        "ch:1:sloid:7000",
        "ch:1:sloid:8503000",
        departure_time="2026-09-24T14:30:00+02:00",
    )

    assert fares == []


def test_fare_request_malformed_xml_returns_empty_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<not-xml")

    client = _client_with_transport(handler)

    fares = client.fare_request(
        "ch:1:sloid:7000",
        "ch:1:sloid:8503000",
        departure_time="2026-09-24T14:30:00+02:00",
    )

    assert fares == []
