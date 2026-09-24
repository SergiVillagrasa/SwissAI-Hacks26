from swiss_grounding_mcp.domain.models import (
    AirlineInfo,
    AirportGuidanceResult,
    AirportInfo,
    AviationProvenance,
    Flight,
    FlightEndpoint,
    FlightLookupResult,
    FlightSearchResult,
    FlightToTrainResult,
)


def _endpoint(**overrides) -> FlightEndpoint:
    defaults = dict(
        airport=AirportInfo(iata="ZRH", icao="LSZH", name="Zurich Airport", timezone="Europe/Zurich"),
        scheduled="2026-09-25T10:20:00+02:00",
        estimated=None,
        actual=None,
        terminal="1",
        gate=None,
        delay_minutes=None,
    )
    defaults.update(overrides)
    return FlightEndpoint(**defaults)


def _flight() -> Flight:
    return Flight(
        flight_number="LX14",
        flight_date="2026-09-25",
        airline=AirlineInfo(name="SWISS", iata="LX", icao="SWR"),
        departure=_endpoint(),
        arrival=_endpoint(airport=AirportInfo(iata="JFK", icao="KJFK", name="JFK", timezone="America/New_York")),
        flight_status="scheduled",
    )


def test_flight_lookup_result_answered_carries_flight_and_field_lists():
    result = FlightLookupResult(
        status="answered",
        message=None,
        flight=_flight(),
        fields_present=["departure.scheduled"],
        fields_missing=["departure.actual"],
        provenance=AviationProvenance(
            source="AeroDataBox (aerodatabox.com)",
            source_url="https://aerodatabox.com",
            retrieved_at="2026-09-24T22:15:00Z",
            applicable_date="2026-09-25",
            timezone="Europe/Zurich",
        ),
    )

    dumped = result.model_dump()
    assert dumped["status"] == "answered"
    assert dumped["flight"]["flight_number"] == "LX14"
    assert dumped["fields_missing"] == ["departure.actual"]
    assert dumped["provenance"]["timezone"] == "Europe/Zurich"


def test_flight_search_result_defaults_to_empty_flights_and_no_provenance():
    result = FlightSearchResult(status="needs_context", message="Provide an airport code.")

    dumped = result.model_dump()
    assert dumped["flights"] == []
    assert dumped["provenance"] is None


def test_airport_guidance_result_out_of_scope_has_no_guidance_text():
    result = AirportGuidanceResult(
        status="out_of_scope",
        topic="visa_requirements",
        message="Topic not covered by this tool.",
    )

    dumped = result.model_dump()
    assert dumped["guidance"] is None
    assert dumped["source_url"] is None


def test_flight_to_train_result_keeps_separate_provenance_fields():
    result = FlightToTrainResult(
        status="answered",
        message=None,
        flight=_flight(),
        train_connections=[],
        flight_provenance=AviationProvenance(
            source="AeroDataBox (aerodatabox.com)",
            source_url="https://aerodatabox.com",
            retrieved_at="2026-09-24T22:15:00Z",
            applicable_date="2026-09-25",
            timezone="Europe/Zurich",
        ),
        rail_provenance=None,
    )

    dumped = result.model_dump()
    assert dumped["flight_provenance"]["source"] == "AeroDataBox (aerodatabox.com)"
    assert dumped["rail_provenance"] is None
