from swiss_grounding_mcp.tools.get_airport_guidance import get_airport_guidance

_VALID_TOPICS = [
    "arrival_process",
    "transfers",
    "baggage",
    "airport_rail_access",
    "flight_status_verification",
]


def test_every_valid_topic_returns_answered_with_zrh_citation():
    for topic in _VALID_TOPICS:
        result = get_airport_guidance(topic)

        assert result.status == "answered", topic
        assert result.guidance
        assert "flughafen-zuerich.ch" in result.source_url
        assert result.applicable_airport == "ZRH / LSZH"
        assert result.retrieved_at is not None


def test_unknown_topic_returns_out_of_scope():
    result = get_airport_guidance("visa_requirements")

    assert result.status == "out_of_scope"
    assert result.guidance is None
    assert "visa_requirements" in result.message


def test_empty_topic_returns_needs_context():
    result = get_airport_guidance("")

    assert result.status == "needs_context"
