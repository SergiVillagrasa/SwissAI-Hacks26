from __future__ import annotations

import re
from datetime import timedelta

from defusedxml import ElementTree as SafeET

from swiss_grounding_mcp.domain.models import Connection, Leg, StopCandidate
from swiss_grounding_mcp.sources.ojp.xml_builder import OJP_NS, SIRI_NS

NS = {"ojp": OJP_NS, "siri": SIRI_NS}

_ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def _parse_iso_duration_minutes(value: str) -> int:
    match = _ISO_DURATION_RE.match(value)
    if not match:
        return 0
    parts = {k: float(v) if v else 0.0 for k, v in match.groupdict().items()}
    delta = timedelta(
        days=parts["days"],
        hours=parts["hours"],
        minutes=parts["minutes"],
        seconds=parts["seconds"],
    )
    return round(delta.total_seconds() / 60)


def _text_of(element, path: str) -> str | None:
    found = element.find(path, NS)
    return found.text if found is not None else None


def parse_location_information_response(xml_bytes: bytes) -> list[StopCandidate]:
    root = SafeET.fromstring(xml_bytes)
    candidates: list[StopCandidate] = []

    for place_result in root.findall(".//ojp:PlaceResult", NS):
        name = _text_of(place_result, "ojp:Place/ojp:Name/ojp:Text")
        stop_ref = _text_of(place_result, "ojp:Place/ojp:StopPlace/ojp:StopPlaceRef")
        if name is None or stop_ref is None:
            continue

        probability_text = _text_of(place_result, "ojp:Probability")
        probability = float(probability_text) if probability_text is not None else None

        candidates.append(StopCandidate(name=name, stop_ref=stop_ref, probability=probability))

    return candidates


def has_service_delivery_error(xml_bytes: bytes) -> str | None:
    root = SafeET.fromstring(xml_bytes)
    error_text = root.find(
        ".//siri:ServiceDelivery/siri:ErrorCondition//siri:ErrorText", NS
    )
    return error_text.text if error_text is not None else None


def _parse_leg(leg_element) -> Leg | None:
    timed_leg = leg_element.find("ojp:TimedLeg", NS)
    if timed_leg is not None:
        board = timed_leg.find("ojp:LegBoard", NS)
        alight = timed_leg.find("ojp:LegAlight", NS)
        service = timed_leg.find("ojp:Service", NS)

        from_name = _text_of(board, "ojp:StopPointName/ojp:Text") or ""
        to_name = _text_of(alight, "ojp:StopPointName/ojp:Text") or ""
        departure = _text_of(
            board, "ojp:ServiceDeparture/ojp:EstimatedTime"
        ) or _text_of(board, "ojp:ServiceDeparture/ojp:TimetabledTime")
        arrival = _text_of(
            alight, "ojp:ServiceArrival/ojp:EstimatedTime"
        ) or _text_of(alight, "ojp:ServiceArrival/ojp:TimetabledTime")
        mode = _text_of(service, "ojp:Mode/ojp:PtMode") or "unknown"
        line = _text_of(service, "ojp:PublishedServiceName/ojp:Text")

        return Leg(
            mode=mode,
            line=line,
            from_name=from_name,
            to_name=to_name,
            departure=departure,
            arrival=arrival,
        )

    continuous_leg = leg_element.find("ojp:ContinuousLeg", NS)
    if continuous_leg is not None:
        start = continuous_leg.find("ojp:LegStart", NS)
        end = continuous_leg.find("ojp:LegEnd", NS)
        service = continuous_leg.find("ojp:Service", NS)

        from_name = _text_of(start, "ojp:Name/ojp:Text") or ""
        to_name = _text_of(end, "ojp:Name/ojp:Text") or ""
        mode = _text_of(service, "ojp:PersonalMode") or "walk"

        return Leg(mode=mode, line=None, from_name=from_name, to_name=to_name)

    return None


def parse_trip_response(xml_bytes: bytes) -> list[Connection]:
    root = SafeET.fromstring(xml_bytes)
    connections: list[Connection] = []

    for trip_result in root.findall(".//ojp:TripResult", NS):
        trip = trip_result.find("ojp:Trip", NS)
        if trip is None:
            continue

        start_time = _text_of(trip, "ojp:StartTime") or ""
        end_time = _text_of(trip, "ojp:EndTime") or ""
        duration_text = _text_of(trip, "ojp:Duration") or "PT0S"
        duration_minutes = _parse_iso_duration_minutes(duration_text)

        legs = [
            leg
            for leg_element in trip.findall("ojp:Leg", NS)
            if (leg := _parse_leg(leg_element)) is not None
        ]
        timed_leg_count = sum(1 for leg in legs if leg.mode != "walk" and leg.mode != "foot")
        changes = max(0, timed_leg_count - 1)

        connections.append(
            Connection(
                departure=start_time,
                arrival=end_time,
                duration_minutes=duration_minutes,
                changes=changes,
                legs=legs,
            )
        )

    return connections
