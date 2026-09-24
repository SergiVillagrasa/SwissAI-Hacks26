from swiss_grounding_mcp.domain.models import (
    Connection,
    ConnectionSearchResult,
    Leg,
    Provenance,
    StopCandidate,
)


def test_ok_result_serializes_connections_and_provenance():
    leg = Leg(
        mode="rail",
        line="IC 8",
        from_name="Bern",
        to_name="Zürich HB",
        departure="2026-09-24T18:04:00Z",
        arrival="2026-09-24T18:57:00Z",
    )
    connection = Connection(
        departure="2026-09-24T18:04:00Z",
        arrival="2026-09-24T19:47:00Z",
        duration_minutes=103,
        changes=1,
        legs=[leg],
    )
    provenance = Provenance(
        source="opentransportdata.swiss OJP 2.0",
        source_url="https://api.opentransportdata.swiss/ojp20",
        retrieved_at="2026-09-24T18:03:12Z",
    )

    result = ConnectionSearchResult(
        status="ok",
        connections=[connection],
        provenance=provenance,
    )

    dumped = result.model_dump()
    assert dumped["status"] == "ok"
    assert dumped["connections"][0]["legs"][0]["line"] == "IC 8"
    assert dumped["candidates"] == []
    assert dumped["provenance"]["source_url"] == "https://api.opentransportdata.swiss/ojp20"


def test_needs_clarification_result_carries_candidates_and_no_connections():
    result = ConnectionSearchResult(
        status="needs_clarification",
        message="Multiple stations match 'Fribourg'.",
        candidates=[
            StopCandidate(name="Fribourg/Freiburg", stop_ref="ch:1:sloid:7000"),
            StopCandidate(name="Freiburg im Breisgau Hbf", stop_ref="de:1:sloid:1"),
        ],
    )

    dumped = result.model_dump()
    assert dumped["status"] == "needs_clarification"
    assert dumped["connections"] == []
    assert len(dumped["candidates"]) == 2
    assert dumped["provenance"] is None
