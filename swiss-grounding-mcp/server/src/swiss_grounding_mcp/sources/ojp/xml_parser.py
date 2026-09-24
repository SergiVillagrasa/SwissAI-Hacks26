from __future__ import annotations

import re
from datetime import datetime, timedelta

from defusedxml import ElementTree as SafeET

from swiss_grounding_mcp.domain.models import (
    Connection,
    Disruption,
    Leg,
    StopCandidate,
    StopEvent,
)
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
        name = (
            _text_of(place_result, "ojp:Place/ojp:StopPlace/ojp:StopPlaceName/ojp:Text")
            or _text_of(place_result, "ojp:Place/ojp:Name/ojp:Text")
        )
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


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _delay_minutes(planned: str | None, estimated: str | None) -> int | None:
    planned_dt = _parse_iso_datetime(planned)
    estimated_dt = _parse_iso_datetime(estimated)
    if planned_dt is None or estimated_dt is None:
        return None
    return round((estimated_dt - planned_dt).total_seconds() / 60)


def _call_point_names(stop_event, path: str) -> list[str]:
    return [
        el.text
        for el in stop_event.findall(path, NS)
        if el.text
    ]


def parse_stop_event_response(
    xml_bytes: bytes, event_type: str = "departure"
) -> list[StopEvent]:
    root = SafeET.fromstring(xml_bytes)
    events: list[StopEvent] = []

    primary_tag = "ojp:ServiceDeparture" if event_type == "departure" else "ojp:ServiceArrival"
    fallback_tag = "ojp:ServiceArrival" if event_type == "departure" else "ojp:ServiceDeparture"

    for stop_event in root.findall(".//ojp:StopEvent", NS):
        call = stop_event.find("ojp:ThisCall/ojp:CallAtStop", NS)
        service = stop_event.find("ojp:Service", NS)
        if call is None or service is None:
            continue

        timing = call.find(primary_tag, NS)
        if timing is None:
            timing = call.find(fallback_tag, NS)

        planned = _text_of(timing, "ojp:TimetabledTime") if timing is not None else None
        estimated = _text_of(timing, "ojp:EstimatedTime") if timing is not None else None

        if event_type == "departure":
            onward = _call_point_names(
                stop_event, "ojp:OnwardCall/ojp:CallAtStop/ojp:StopPointName/ojp:Text"
            )
            direction = _text_of(service, "ojp:DestinationText/ojp:Text") or (
                onward[-1] if onward else None
            )
        else:
            previous = _call_point_names(
                stop_event, "ojp:PreviousCall/ojp:CallAtStop/ojp:StopPointName/ojp:Text"
            )
            direction = _text_of(service, "ojp:OriginText/ojp:Text") or (
                previous[0] if previous else None
            )

        platform = _text_of(call, "ojp:EstimatedQuay/ojp:Text") or _text_of(
            call, "ojp:PlannedQuay/ojp:Text"
        )

        events.append(
            StopEvent(
                line=_text_of(service, "ojp:PublishedServiceName/ojp:Text"),
                mode=_text_of(service, "ojp:Mode/ojp:PtMode"),
                direction_name=direction,
                planned_time=planned,
                estimated_time=estimated,
                platform=platform,
                delay_minutes=_delay_minutes(planned, estimated),
            )
        )

    return events


def _parse_bool(element, path: str) -> bool:
    value = _text_of(element, path)

    if value is None:
        return False

    return value.strip().lower() == "true"


def parse_disruption_stop_event_response(xml_bytes: bytes) -> list[Disruption]:
    root = SafeET.fromstring(xml_bytes)

    disruptions: list[Disruption] = []

    for result in root.findall(".//ojp:StopEventResult", NS):
        stop_event = result.find("ojp:StopEvent", NS)

        if stop_event is None:
            continue

        this_call = stop_event.find("ojp:ThisCall/ojp:CallAtStop", NS)

        if this_call is None:
            continue

        service = stop_event.find("ojp:Service", NS)

        if service is None:
            continue

        line = _text_of(
            service,
            "ojp:PublishedServiceName/ojp:Text",
        )

        journey_ref = _text_of(
            service,
            "ojp:JourneyRef",
        )

        stop_name = _text_of(
            this_call,
            "ojp:StopPointName/ojp:Text",
        )

        timetabled_departure = _text_of(
            this_call,
            "ojp:ServiceDeparture/ojp:TimetabledTime",
        )

        estimated_departure = _text_of(
            this_call,
            "ojp:ServiceDeparture/ojp:EstimatedTime",
        )

        timetabled_arrival = _text_of(
            this_call,
            "ojp:ServiceArrival/ojp:TimetabledTime",
        )

        estimated_arrival = _text_of(
            this_call,
            "ojp:ServiceArrival/ojp:EstimatedTime",
        )

        cancelled = _parse_bool(
            this_call,
            "ojp:NotServicedStop",
        )

        no_boarding = _parse_bool(
            this_call,
            "ojp:NoBoardingAtStop",
        )

        no_alighting = _parse_bool(
            this_call,
            "ojp:NoAlightingAtStop",
        )

        delay_minutes: int | None = None

        for scheduled, estimated in [
            (timetabled_departure, estimated_departure),
            (timetabled_arrival, estimated_arrival),
        ]:
            if scheduled is None or estimated is None:
                continue

            try:
                scheduled_dt = datetime.fromisoformat(
                    scheduled.replace("Z", "+00:00")
                )
                estimated_dt = datetime.fromisoformat(
                    estimated.replace("Z", "+00:00")
                )

                delay = round(
                    (estimated_dt - scheduled_dt).total_seconds() / 60
                )

                if delay != 0:
                    delay_minutes = delay
                    break

            except ValueError:
                continue

        if not (
            cancelled
            or no_boarding
            or no_alighting
            or delay_minutes is not None
        ):
            continue

        if cancelled:
            status = "cancelled"
            severity = "high"
            title = f"Cancelled service{f' {line}' if line else ''}"

        elif no_boarding:
            status = "no_boarding"
            severity = "high"
            title = f"Boarding unavailable{f' on line {line}' if line else ''}"

        elif no_alighting:
            status = "no_alighting"
            severity = "high"
            title = f"Alighting unavailable{f' on line {line}' if line else ''}"

        else:
            status = "delayed"
            severity = "medium"
            title = (
                f"Service {line} delayed by "
                f"{delay_minutes} minute(s)"
                if line
                else f"Service delayed by {delay_minutes} minute(s)"
            )

        description_parts = []

        if stop_name:
            description_parts.append(f"At {stop_name}.")

        if delay_minutes is not None:
            description_parts.append(
                f"Estimated delay: {delay_minutes} minute(s)."
            )

        if cancelled:
            description_parts.append("The service is not operating at this stop.")

        if no_boarding:
            description_parts.append(
                "Boarding is not possible at this stop."
            )

        if no_alighting:
            description_parts.append(
                "Alighting is not possible at this stop."
            )

        description = " ".join(description_parts)

        disruption_id = journey_ref or line or f"stop-event-{len(disruptions)}"

        disruptions.append(
            Disruption(
                id=disruption_id,
                title=title,
                description=description,
                severity=severity,
                start_time=timetabled_departure or timetabled_arrival,
                status=status,
                affected_lines=[line] if line else [],
                affected_stops=[stop_name] if stop_name else [],
            )
        )

    return disruptions
