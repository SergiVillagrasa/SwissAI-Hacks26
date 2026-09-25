from swiss_grounding_mcp.domain.booking_links import build_flight_booking_url


def test_swiss_flight_gets_swiss_booking_deep_link():
    url = build_flight_booking_url("LX", "SWR", "ZRH", "JFK", "2026-09-25")

    assert url.startswith("https://")
    assert url == "https://www.swiss.com/us/en/Book/ZRH-JFK/from-2026-09-25"


def test_swiss_via_icao_code_gets_swiss_deep_link():
    url = build_flight_booking_url(None, "SWR", "ZRH", "JFK", "2026-09-25")

    assert url.startswith("https://www.swiss.com/")


def test_lufthansa_flight_gets_lufthansa_booking_deep_link():
    url = build_flight_booking_url("LH", "DLH", "ZRH", "FRA", "2026-09-25")

    assert url == "https://www.lufthansa.com/us/en/Book/ZRH-FRA/from-2026-09-25"


def test_lh_group_flight_without_route_details_falls_back_to_portal_root():
    url = build_flight_booking_url("LX", None, None, "JFK", "2026-09-25")

    assert url == "https://www.swiss.com"


def test_easyjet_iata_and_icao_map_to_easyjet_portal():
    assert build_flight_booking_url("U2", "EZY", "GVA", "LGW", "2026-09-25") == "https://www.easyjet.com"
    assert build_flight_booking_url(None, "EZY", "GVA", "LGW", "2026-09-25") == "https://www.easyjet.com"


def test_british_airways_maps_to_ba_portal():
    assert build_flight_booking_url("BA", "BAW", "ZRH", "LHR", "2026-09-25") == "https://www.britishairways.com"


def test_unknown_airline_falls_back_to_google_flights_with_route_and_date():
    url = build_flight_booking_url("XY", None, "ZRH", "LIS", "2026-09-25")

    assert url == (
        "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+LIS+on+2026-09-25"
    )


def test_unknown_airline_without_route_falls_back_to_google_flights_root():
    url = build_flight_booking_url("XY", None, None, None, None)

    assert url == "https://www.google.com/travel/flights"


def test_every_branch_returns_a_https_url():
    for url in (
        build_flight_booking_url("LX", None, "ZRH", "JFK", "2026-09-25"),
        build_flight_booking_url("U2", None, "GVA", "LGW", "2026-09-25"),
        build_flight_booking_url("XX", None, "ZRH", "LIS", "2026-09-25"),
        build_flight_booking_url(None, None, None, None, None),
    ):
        assert url.startswith("https://")
