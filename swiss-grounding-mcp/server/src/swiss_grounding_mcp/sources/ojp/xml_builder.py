from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

OJP_NS = "http://www.vdv.de/ojp"
SIRI_NS = "http://www.siri.org.uk/siri"

ET.register_namespace("", OJP_NS)
ET.register_namespace("siri", SIRI_NS)


def _ojp(tag: str) -> str:
    return f"{{{OJP_NS}}}{tag}"


def _siri(tag: str) -> str:
    return f"{{{SIRI_NS}}}{tag}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_message_identifier(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _service_request_root(requestor_ref: str, timestamp: str) -> tuple[ET.Element, ET.Element]:
    root = ET.Element(_ojp("OJP"), {"version": "2.0"})
    ojp_request = ET.SubElement(root, _ojp("OJPRequest"))
    service_request = ET.SubElement(ojp_request, _siri("ServiceRequest"))
    ET.SubElement(service_request, _siri("RequestTimestamp")).text = timestamp
    ET.SubElement(service_request, _siri("RequestorRef")).text = requestor_ref
    return root, service_request


def _serialize(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_location_information_request(
    name: str,
    requestor_ref: str,
    *,
    number_of_results: int = 5,
    message_identifier: str | None = None,
    timestamp: str | None = None,
) -> bytes:
    timestamp = timestamp or _now_iso()
    root, service_request = _service_request_root(requestor_ref, timestamp)

    lir = ET.SubElement(service_request, _ojp("OJPLocationInformationRequest"))
    ET.SubElement(lir, _siri("RequestTimestamp")).text = timestamp
    ET.SubElement(lir, _siri("MessageIdentifier")).text = (
        message_identifier or _new_message_identifier("LIR")
    )

    initial_input = ET.SubElement(lir, _ojp("InitialInput"))
    ET.SubElement(initial_input, _ojp("Name")).text = name

    restrictions = ET.SubElement(lir, _ojp("Restrictions"))
    ET.SubElement(restrictions, _ojp("Type")).text = "stop"
    ET.SubElement(restrictions, _ojp("NumberOfResults")).text = str(number_of_results)

    return _serialize(root)


def build_trip_request(
    origin_ref: str,
    destination_ref: str,
    requestor_ref: str,
    *,
    origin_name: str = "",
    destination_name: str = "",
    departure_time: str | None = None,
    arrival_time: str | None = None,
    number_of_results: int = 3,
    message_identifier: str | None = None,
    timestamp: str | None = None,
) -> bytes:
    timestamp = timestamp or _now_iso()
    root, service_request = _service_request_root(requestor_ref, timestamp)

    trip_request = ET.SubElement(service_request, _ojp("OJPTripRequest"))
    ET.SubElement(trip_request, _siri("RequestTimestamp")).text = timestamp
    ET.SubElement(trip_request, _siri("MessageIdentifier")).text = (
        message_identifier or _new_message_identifier("TR")
    )

    origin = ET.SubElement(trip_request, _ojp("Origin"))
    origin_place_ref = ET.SubElement(origin, _ojp("PlaceRef"))
    ET.SubElement(origin_place_ref, _siri("StopPointRef")).text = origin_ref
    ET.SubElement(ET.SubElement(origin_place_ref, _ojp("Name")), _ojp("Text")).text = (
        origin_name or origin_ref
    )
    if departure_time is not None:
        ET.SubElement(origin, _ojp("DepArrTime")).text = departure_time

    destination = ET.SubElement(trip_request, _ojp("Destination"))
    destination_place_ref = ET.SubElement(destination, _ojp("PlaceRef"))
    ET.SubElement(destination_place_ref, _siri("StopPointRef")).text = destination_ref
    ET.SubElement(
        ET.SubElement(destination_place_ref, _ojp("Name")), _ojp("Text")
    ).text = (destination_name or destination_ref)
    if departure_time is None and arrival_time is not None:
        ET.SubElement(destination, _ojp("DepArrTime")).text = arrival_time

    params = ET.SubElement(trip_request, _ojp("Params"))
    ET.SubElement(params, _ojp("NumberOfResults")).text = str(number_of_results)
    ET.SubElement(params, _ojp("IncludeIntermediateStops")).text = "false"

    return _serialize(root)


def build_stop_event_request(
    stop_ref: str,
    requestor_ref: str,
    *,
    station_name: str = "",
    event_type: str = "departure",
    when: str | None = None,
    number_of_results: int = 5,
    message_identifier: str | None = None,
    timestamp: str | None = None,
) -> bytes:
    timestamp = timestamp or _now_iso()
    root, service_request = _service_request_root(requestor_ref, timestamp)

    stop_event = ET.SubElement(service_request, _ojp("OJPStopEventRequest"))
    ET.SubElement(stop_event, _siri("RequestTimestamp")).text = timestamp
    ET.SubElement(stop_event, _siri("MessageIdentifier")).text = (
        message_identifier or _new_message_identifier("SER")
    )

    location = ET.SubElement(stop_event, _ojp("Location"))
    place_ref = ET.SubElement(location, _ojp("PlaceRef"))
    ET.SubElement(place_ref, _siri("StopPointRef")).text = stop_ref
    ET.SubElement(ET.SubElement(place_ref, _ojp("Name")), _ojp("Text")).text = (
        station_name or stop_ref
    )
    ET.SubElement(location, _ojp("DepArrTime")).text = when or timestamp

    params = ET.SubElement(stop_event, _ojp("Params"))
    ET.SubElement(params, _ojp("NumberOfResults")).text = str(number_of_results)
    ET.SubElement(params, _ojp("StopEventType")).text = event_type
    ET.SubElement(params, _ojp("IncludeRealtimeData")).text = "true"
    ET.SubElement(params, _ojp("IncludePreviousCalls")).text = "true"
    ET.SubElement(params, _ojp("IncludeOnwardCalls")).text = "true"

    return _serialize(root)
