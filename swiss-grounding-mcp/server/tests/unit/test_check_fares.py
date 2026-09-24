from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import StopCandidate
from swiss_grounding_mcp.sources.ojp.client import OjpSourceError
from swiss_grounding_mcp.tools.check_fares import check_public_transport_fares


class StubOjpClient:
    def __init__(self, *, candidates_by_name=None, raise_on_location=None):
        self.candidates_by_name = candidates_by_name or {}
        self.raise_on_location = raise_on_location

    def location_information(self, name):
        if self.raise_on_location is not None:
            raise self.raise_on_location
        return self.candidates_by_name.get(name, [])


def _settings() -> Settings:
    return Settings.from_env({"OJP_BASE_URL": "https://example.test/ojp20"})


def _client_with_bern_zurich():
    return StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        }
    )


def test_missing_origin_returns_needs_clarification():
    client = StubOjpClient()

    result = check_public_transport_fares(
        "", "Zürich HB", client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert "origin" in result.message.lower()


def test_missing_destination_returns_needs_clarification():
    client = StubOjpClient()

    result = check_public_transport_fares(
        "Bern", "", client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert "destination" in result.message.lower()


def test_invalid_travel_class_returns_needs_clarification():
    client = _client_with_bern_zurich()

    result = check_public_transport_fares(
        "Bern", "Zürich HB", travel_class=3, client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert "travel_class" in result.message.lower()


def test_invalid_travel_date_returns_needs_clarification():
    client = _client_with_bern_zurich()

    result = check_public_transport_fares(
        "Bern", "Zürich HB", travel_date="not-a-date", client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert "travel_date" in result.message.lower()


def test_valid_route_returns_second_class_full_fare_by_default():
    client = _client_with_bern_zurich()

    result = check_public_transport_fares(
        "Bern", "Zürich HB", client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert result.origin == "Bern"
    assert result.destination == "Zürich HB"
    assert result.currency == "CHF"
    assert any(p.class_of_travel == 2 and p.discount == "none" for p in result.products)
    assert result.provenance.source_url == "https://www.sbb.ch/en/tickets-railtravel/fares.html"


def test_half_fare_filter_returns_reduced_price():
    client = _client_with_bern_zurich()

    result = check_public_transport_fares(
        "Bern", "Zürich HB", discount="halbtax", client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert len(result.products) == 1
    assert result.products[0].discount == "half-fare"
    assert result.products[0].price_chf == 25.5


def test_first_class_returns_first_class_fares():
    client = _client_with_bern_zurich()

    result = check_public_transport_fares(
        "Bern", "Zürich HB", travel_class=1, client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert all(p.class_of_travel == 1 for p in result.products)


def test_unresolvable_station_returns_not_found():
    client = StubOjpClient(candidates_by_name={"Atlantis": [], "Bern": [
        StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)
    ]})

    result = check_public_transport_fares(
        "Atlantis", "Bern", client=client, settings=_settings()
    )

    assert result.status == "not_found"


def test_unknown_route_returns_not_found():
    client = StubOjpClient(
        candidates_by_name={
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
            "Lugano": [StopCandidate(name="Lugano", stop_ref="ch:1:sloid:8500", probability=1.0)],
        }
    )

    result = check_public_transport_fares(
        "Bern", "Lugano", client=client, settings=_settings()
    )

    assert result.status == "not_found"
    assert "No fare information" in result.message


def test_ambiguous_station_returns_needs_clarification_with_candidates():
    client = StubOjpClient(
        candidates_by_name={
            "Fribourg": [
                StopCandidate(name="Fribourg/Freiburg", stop_ref="ch:1:sloid:7100", probability=0.62),
                StopCandidate(
                    name="Freiburg(Breisgau) Hbf", stop_ref="de:1:sloid:1", probability=0.58
                ),
            ],
            "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
        }
    )

    result = check_public_transport_fares(
        "Fribourg", "Bern", client=client, settings=_settings()
    )

    assert result.status == "needs_clarification"
    assert len(result.candidates) == 2


def test_accented_station_names_resolve():
    client = StubOjpClient(
        candidates_by_name={
            "Geneve": [
                StopCandidate(name="Genève", stop_ref="ch:1:sloid:9000", probability=0.55),
                StopCandidate(
                    name="Genève-Aéroport", stop_ref="ch:1:sloid:9001", probability=0.50
                ),
            ],
            "Zürich HB": [
                StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)
            ],
        }
    )

    result = check_public_transport_fares(
        "Geneve", "Zürich HB", client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert result.origin == "Genève"
    assert result.destination == "Zürich HB"
    assert any(p.price_chf == 92.0 for p in result.products)


def test_source_error_from_location_information_returns_source_error_status():
    client = StubOjpClient(raise_on_location=OjpSourceError("OJP returned HTTP 403"))

    result = check_public_transport_fares(
        "Bern", "Zürich HB", client=client, settings=_settings()
    )

    assert result.status == "source_error"
    assert "403" in result.message


def test_ga_discount_returns_zero_fare_product():
    client = _client_with_bern_zurich()

    result = check_public_transport_fares(
        "Bern", "Zürich HB", discount="GA", client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert len(result.products) == 1
    assert result.products[0].discount == "ga"
    assert result.products[0].price_chf == 0.0


def test_reverse_direction_uses_same_fare_table():
    client = _client_with_bern_zurich()

    result = check_public_transport_fares(
        "Zürich HB", "Bern", travel_class=2, discount="half-fare", client=client, settings=_settings()
    )

    assert result.status == "ok"
    assert any(p.price_chf == 25.5 and p.discount == "half-fare" for p in result.products)
