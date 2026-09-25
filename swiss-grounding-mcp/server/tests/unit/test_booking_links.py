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
