import xml.etree.ElementTree as ET

from swiss_grounding_mcp.sources.ojp.xml_builder import (
    OJP_NS,
    SIRI_NS,
    build_location_information_request,
    build_trip_request,
)

NS = {"ojp": OJP_NS, "siri": SIRI_NS}


def test_location_information_request_contains_escaped_name():
    xml_bytes = build_location_information_request(
        "Zürich <HB> & Co",
        "swiss-grounding-mcp",
        number_of_results=5,
        message_identifier="LIR-1",
        timestamp="2026-09-24T12:00:00Z",
    )

    root = ET.fromstring(xml_bytes)
    name_el = root.find(
        ".//ojp:OJPLocationInformationRequest/ojp:InitialInput/ojp:Name", NS
    )
    assert name_el is not None
    assert name_el.text == "Zürich <HB> & Co"

    requestor_ref = root.find(".//siri:ServiceRequest/siri:RequestorRef", NS)
    assert requestor_ref.text == "swiss-grounding-mcp"

    number_of_results = root.find(
        ".//ojp:OJPLocationInformationRequest/ojp:Restrictions/ojp:NumberOfResults", NS
    )
    assert number_of_results.text == "5"


def test_trip_request_contains_origin_destination_and_departure_time():
    xml_bytes = build_trip_request(
        "ch:1:sloid:7000",
        "ch:1:sloid:8503000",
        "swiss-grounding-mcp",
        origin_name="Bern",
        destination_name="Zürich HB",
        departure_time="2026-09-24T18:00:00Z",
        number_of_results=3,
        message_identifier="TR-1",
        timestamp="2026-09-24T12:00:00Z",
    )

    root = ET.fromstring(xml_bytes)
    origin_ref = root.find(
        ".//ojp:OJPTripRequest/ojp:Origin/ojp:PlaceRef/siri:StopPointRef", NS
    )
    assert origin_ref.text == "ch:1:sloid:7000"

    destination_ref = root.find(
        ".//ojp:OJPTripRequest/ojp:Destination/ojp:PlaceRef/siri:StopPointRef", NS
    )
    assert destination_ref.text == "ch:1:sloid:8503000"

    dep_time = root.find(".//ojp:OJPTripRequest/ojp:Origin/ojp:DepArrTime", NS)
    assert dep_time.text == "2026-09-24T18:00:00Z"

    number_of_results = root.find(
        ".//ojp:OJPTripRequest/ojp:Params/ojp:NumberOfResults", NS
    )
    assert number_of_results.text == "3"


def test_trip_request_with_arrival_time_omits_dep_arr_time_on_origin():
    xml_bytes = build_trip_request(
        "ch:1:sloid:7000",
        "ch:1:sloid:8503000",
        "swiss-grounding-mcp",
        arrival_time="2026-09-24T20:00:00Z",
        timestamp="2026-09-24T12:00:00Z",
    )

    root = ET.fromstring(xml_bytes)
    dep_time = root.find(".//ojp:OJPTripRequest/ojp:Origin/ojp:DepArrTime", NS)
    assert dep_time is None

    arr_time = root.find(".//ojp:OJPTripRequest/ojp:Destination/ojp:DepArrTime", NS)
    assert arr_time.text == "2026-09-24T20:00:00Z"
