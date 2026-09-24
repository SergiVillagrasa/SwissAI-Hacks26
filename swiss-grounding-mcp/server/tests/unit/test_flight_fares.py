from datetime import date, timedelta

import httpx

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.sources.serpapi.flight_client import SerpApiFlightClient
from swiss_grounding_mcp.tools.flight_fares import get_flight_fares


SERPAPI_RESPONSE = {
    "best_flights": [
        {
            "flights": [
                {
                    "departure_airport": {"id": "ZRH", "time": "2026-09-25 08:00"},
                    "arrival_airport": {"id": "GVA", "time": "2026-09-25 08:50"},
                    "airline": "SWISS",
                    "flight_number": "LX 2802",
                }
            ],
            "total_duration": 50,
            "carbon_emissions": {"this_flight": 42000},
            "price": 149,
        }
    ],
    "other_flights": [
        {
            "flights": [
                {
                    "departure_airport": {"id": "ZRH", "time": "2026-09-25 10:00"},
                    "arrival_airport": {"id": "GVA", "time": "2026-09-25 10:55"},
                    "airline": "SWISS",
                    "flight_number": "LX 2806",
                }
            ],
            "total_duration": 55,
            "price": 172,
        }
    ],
}


class StubSerpApiClient:
    def __init__(self, response=None):
        self.response = response if response is not None else {}
        self.calls = []

    def search_flights(self, departure_id, arrival_id, outbound_date, currency):
        self.calls.append(
            {
                "departure_id": departure_id,
                "arrival_id": arrival_id,
                "outbound_date": outbound_date,
                "currency": currency,
            }
        )
        return self.response


def _settings(**overrides) -> Settings:
    env = {"SERPAPI_API_KEY": "test-key", "SERPAPI_BASE_URL": "https://example.test/search.json"}
    env.update(overrides)
    return Settings.from_env(env)


def test_serpapi_client_sends_google_flights_query():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json=SERPAPI_RESPONSE)

    client = SerpApiFlightClient(_settings())
    client._http = httpx.Client(transport=httpx.MockTransport(handler))

    response = client.search_flights("ZRH", "GVA", "2026-09-25", "CHF")

    assert seen == {
        "engine": "google_flights",
        "departure_id": "ZRH",
        "arrival_id": "GVA",
        "outbound_date": "2026-09-25",
        "currency": "CHF",
        "type": "2",
        "api_key": "test-key",
    }
    assert response == SERPAPI_RESPONSE


def test_mock_serpapi_response_is_parsed_to_essential_fields():
    result = get_flight_fares(
        "Zurich",
        "Geneva",
        "2026-09-25",
        client=StubSerpApiClient(SERPAPI_RESPONSE),
        settings=_settings(),
    )

    assert result.status == "ok"
    assert len(result.flights) == 2
    assert result.flights[0].model_dump() == {
        "airline": "SWISS",
        "flight_number": "LX 2802",
        "departure_time": "2026-09-25 08:00",
        "arrival_time": "2026-09-25 08:50",
        "price": 149.0,
        "currency": "CHF",
        "duration_minutes": 50,
        "carbon_emissions_grams": 42000,
    }
    assert result.provenance.source == "SerpApi (Google Flights)"
    assert result.provenance.source_url == "https://serpapi.com"
    assert result.provenance.retrieved_at.endswith("Z")


def test_domestic_swiss_route_aliases_are_normalized():
    client = StubSerpApiClient(SERPAPI_RESPONSE)

    result = get_flight_fares(
        "eap", "Lugano", "2026-09-25", client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert client.calls[0]["departure_id"] == "BSL"
    assert client.calls[0]["arrival_id"] == "LUG"


def test_foreign_flight_is_refused_without_api_call():
    client = StubSerpApiClient(SERPAPI_RESPONSE)

    result = get_flight_fares(
        "Zurich", "Paris", "2026-09-25", client=client, settings=_settings()
    )

    assert result.status == "out_of_scope"
    assert result.message == "This tool only covers domestic flight connections and fares within Switzerland."
    assert client.calls == []


def test_missing_origin_returns_needs_clarification():
    client = StubSerpApiClient(SERPAPI_RESPONSE)

    result = get_flight_fares(
        "", "Geneva", "2026-09-25", client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert "ZRH" in result.message
    assert client.calls == []


def test_unrecognized_destination_returns_needs_clarification():
    client = StubSerpApiClient(SERPAPI_RESPONSE)

    result = get_flight_fares(
        "Zurich", "somewhere", "2026-09-25", client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert "GVA" in result.message
    assert client.calls == []


def test_omitted_date_defaults_to_tomorrow():
    client = StubSerpApiClient(SERPAPI_RESPONSE)

    get_flight_fares("ZRH", "GVA", client=client, settings=_settings())

    assert client.calls[0]["outbound_date"] == (date.today() + timedelta(days=1)).isoformat()


def test_empty_results_return_not_found():
    result = get_flight_fares(
        "ZRH",
        "Sion",
        "2026-09-25",
        client=StubSerpApiClient({}),
        settings=_settings(),
    )

    assert result.status == "not_found"
    assert "No commercial domestic flights" in result.message
    assert result.flights == []
