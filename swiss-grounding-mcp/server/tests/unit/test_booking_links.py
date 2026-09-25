from swiss_grounding_mcp.domain.booking_links import build_flight_booking_url


def test_swiss_flight_gets_prefilled_google_flights_link():
    url = build_flight_booking_url("LX", "SWR", "ZRH", "JFK", "2026-09-25")

    assert url == (
        "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+JFK+on+2026-09-25"
    )


def test_lufthansa_flight_gets_prefilled_google_flights_link():
    url = build_flight_booking_url("LH", "DLH", "ZRH", "FRA", "2026-09-25")

    assert url == (
        "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+FRA+on+2026-09-25"
    )


def test_prefilled_route_omits_missing_date():
    url = build_flight_booking_url("LX", None, "ZRH", "JFK", None)

    assert url == "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+JFK"


def test_swiss_without_route_falls_back_to_swiss_booking_portal():
    url = build_flight_booking_url("LX", "SWR", None, None, None)

    assert url == "https://www.swiss.com/ch/en/book-flights"


def test_swiss_via_icao_only_still_finds_swiss_portal():
    url = build_flight_booking_url(None, "SWR", None, None, None)

    assert url == "https://www.swiss.com/ch/en/book-flights"


def test_easyjet_iata_and_icao_map_to_easyjet_portal():
    assert build_flight_booking_url("U2", "EZY", None, None, None) == "https://www.easyjet.com"
    assert build_flight_booking_url(None, "EZY", None, None, None) == "https://www.easyjet.com"


def test_british_airways_maps_to_ba_portal():
    assert build_flight_booking_url("BA", "BAW", None, None, None) == "https://www.britishairways.com"


def test_unknown_airline_falls_back_to_google_flights_with_route_and_date():
    url = build_flight_booking_url("XY", None, "ZRH", "LIS", "2026-09-25")

    assert url == (
        "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+LIS+on+2026-09-25"
    )


def test_unknown_airline_without_route_falls_back_to_google_flights_root():
    url = build_flight_booking_url("XY", None, None, None, None)

    assert url == "https://www.google.com/travel/flights"


def test_missing_destination_iata_defaults_to_zurich():
    url = build_flight_booking_url("LX", "SWR", "LHR", None, "2026-09-25")

    assert url == (
        "https://www.google.com/travel/flights?q=Flights+from+LHR+to+ZRH+on+2026-09-25"
    )


def test_missing_origin_iata_defaults_to_zurich():
    url = build_flight_booking_url("LX", "SWR", None, "LHR", "2026-09-25")

    assert url == (
        "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+LHR+on+2026-09-25"
    )


def test_icao_code_used_when_iata_missing():
    url = build_flight_booking_url(
        "LX", "SWR", None, "LHR", "2026-09-25", origin_icao="LSZH"
    )

    assert url == (
        "https://www.google.com/travel/flights?q=Flights+from+LSZH+to+LHR+on+2026-09-25"
    )


def test_no_route_at_all_falls_back_to_airline_portal():
    url = build_flight_booking_url("LX", None, None, None, None)

    assert url == "https://www.swiss.com/ch/en/book-flights"


def test_missing_origin_with_zrh_destination_falls_back_to_portal():
    # Destination resolves to ZRH while origin is unknown: no route to
    # preload, so the airline portal is safer than a ZRH->ZRH query.
    url = build_flight_booking_url("U2", "EZY", None, "ZRH", "2026-09-25")

    assert url == "https://www.easyjet.com"


def test_every_branch_returns_a_https_url_without_invented_paths():
    for url in (
        build_flight_booking_url("LX", None, "ZRH", "JFK", "2026-09-25"),
        build_flight_booking_url("U2", None, "GVA", "LGW", "2026-09-25"),
        build_flight_booking_url("XX", None, "ZRH", "LIS", "2026-09-25"),
        build_flight_booking_url("LX", None, None, None, None),
        build_flight_booking_url(None, None, None, None, None),
    ):
        assert url.startswith("https://")
        # static airline Book/ deep-link paths 404 without a session
        assert "/Book/" not in url
