from __future__ import annotations

from typing import NamedTuple


class GuidanceRecord(NamedTuple):
    text: str
    source: str
    source_url: str
    limitations: str


GUIDANCE_TOPICS: dict[str, GuidanceRecord] = {
    "arrival_process": GuidanceRecord(
        text=(
            "After landing at Zurich Airport, follow signs to Arrivals. Passengers "
            "arriving from outside the Schengen area go through passport control "
            "before baggage claim; passengers arriving within Schengen go directly "
            "to baggage claim. From Arrivals you can reach trains, buses, trams, "
            "taxis, and the car parks."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers",
        limitations=(
            "Passport/visa requirements depend on nationality and are set by "
            "Swiss federal authorities, not the airport; verify with the FDFA or "
            "your airline."
        ),
    ),
    "transfers": GuidanceRecord(
        text=(
            "If you already have a boarding pass for your connecting flight, "
            "check the departure time and gate on the flight information screens "
            "or the Zurich Airport website; your gate is shown at least 60 "
            "minutes before departure. If you do not have a boarding pass, "
            "collect it from your departure gate or a Transfer Desk (located in "
            "gate areas A, B, D and E). Self-connecting passengers whose baggage "
            "is not checked through to the final destination must leave the "
            "transit area and recheck their luggage, and should allow extra time "
            "and check current entry regulations for Switzerland."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers/fly/all-about-the-flight/transfer",
        limitations="Airline-specific transfer and rebooking rules are out of scope; verify with your airline.",
    ),
    "baggage": GuidanceRecord(
        text=(
            "Baggage trolleys are available free of charge at airport entrances "
            "and exits. Porter and concierge escort services (CGS) can assist "
            "with baggage on departure, arrival, or transfer; pre-booking is "
            "recommended. A home baggage collection and check-in service is "
            "available for selected airlines and Swiss addresses, with luggage "
            "collected the day before or the day of departure."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers/practical/services/services-for-travellers/baggageservices",
        limitations=(
            "Checked-baggage allowances, fees, and lost-baggage claims are set "
            "by individual airlines and are out of scope; verify with your "
            "airline."
        ),
    ),
    "airport_rail_access": GuidanceRecord(
        text=(
            "Zurich Airport has its own railway station (Zürich Flughafen) "
            "directly beneath the terminal, served by SBB trains including "
            "direct connections to Zürich HB and onward across Switzerland. "
            "From Arrivals, follow signage to the SBB platforms; step-free "
            "access is available via the car-park elevators to Check-in Level 3."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers/practical/parking-and-transport",
        limitations=(
            "For live train times and connections beyond Zürich HB, use this "
            "server's train-connections tool, which is grounded in "
            "opentransportdata.swiss OJP 2.0."
        ),
    ),
    "flight_status_verification": GuidanceRecord(
        text=(
            "To verify the latest scheduled, estimated, or actual time for a "
            "specific flight, use this server's flight-lookup tool, or check "
            "the official Zurich Airport arrivals/departures pages directly."
        ),
        source="Flughafen Zürich AG",
        source_url="https://www.flughafen-zuerich.ch/en/passengers/fly/flightinformation/arrivals",
        limitations=(
            "This server's own flight-lookup tool is sourced from "
            "aviationstack.com, a third-party aggregator, not from Zurich "
            "Airport's operational systems; always treat times as estimates "
            "until confirmed by the airline or airport display."
        ),
    ),
}
