"""Multi-turn tests for the sort-preference flow (wait time vs. price).

Turn 1: the user asks for ticket/connection options without stating an
order -- the system prompt must instruct the model to ask A (soonest
departure / shortest wait) or B (cheapest price) before calling a tool.
Turn 2: the user picks a criterion -- the matching tool is called with
sort_by and the widget payload is ordered accordingly.
"""

from types import SimpleNamespace

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import (
    Connection,
    FareProduct,
    StopCandidate,
)

from agent_backend.agent_loop import run_chat
from agent_backend.tools_registry import TOOL_SCHEMAS


def _tool_call(call_id, name, arguments_json):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments_json),
    )


class _FakeOpenAI:
    """Returns one canned response per call, in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        self.calls = []

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _text_response(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=[]))]
    )


def _tool_call_response(tool_calls):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=tool_calls))]
    )


def _settings():
    return Settings.from_env({"OJP_BASE_URL": "https://example.test/ojp20"})


class _StubOjpClient:
    def __init__(self, *, candidates_by_name=None, fares=None, connections=None):
        self.candidates_by_name = candidates_by_name or {}
        self.fares = fares if fares is not None else []
        self.connections = connections if connections is not None else []

    def location_information(self, name):
        return self.candidates_by_name.get(name, [])

    def fare_request(self, origin_ref, destination_ref, **kwargs):
        return self.fares

    def trip_request(self, origin_ref, destination_ref, **kwargs):
        return self.connections


def _swiss_candidates():
    return {
        "Bern": [StopCandidate(name="Bern", stop_ref="ch:1:sloid:7000", probability=1.0)],
        "Zürich HB": [StopCandidate(name="Zürich HB", stop_ref="ch:1:sloid:8503000", probability=1.0)],
    }


def _run(messages, fake_openai, ojp_client=None, **kwargs):
    return list(run_chat(
        messages,
        openai_client=fake_openai,
        ojp_client=ojp_client,
        aviation_client=None,
        settings=_settings(),
        model="gpt-4o-mini",
        **kwargs,
    ))


def test_system_prompt_instructs_preference_question_before_listing():
    fake_openai = _FakeOpenAI([_text_response("ok")])

    _run([{"role": "user", "content": "hi"}], fake_openai)

    system = fake_openai.calls[0]["messages"][0]["content"]
    assert "soonest departure" in system
    assert "cheapest" in system
    assert "MUST NOT call the tool" in system


def test_tool_schemas_expose_sort_by_parameters():
    schemas = {s["function"]["name"]: s["function"] for s in TOOL_SCHEMAS}
    assert schemas["find_connections"]["parameters"]["properties"]["sort_by"]["enum"] == ["departure"]
    assert schemas["check_public_transport_fares"]["parameters"]["properties"]["sort_by"]["enum"] == ["price"]


def test_first_turn_asks_preference_then_second_turn_sorts_fares_by_price():
    # Turn 1 -- the model asks the ordering question instead of calling a tool.
    question = "Do you prefer the soonest departure or the cheapest price?"
    fake_openai = _FakeOpenAI([_text_response(question)])
    turn1 = _run(
        [{"role": "user", "content": "what are my ticket options from Bern to Zürich tomorrow?"}],
        fake_openai,
    )
    assert {"type": "token", "text": question} in turn1
    assert not any(e["type"] == "widget" for e in turn1)

    # Turn 2 -- the model keeps the journey context and applies sort_by=price.
    ojp = _StubOjpClient(
        candidates_by_name=_swiss_candidates(),
        fares=[
            FareProduct(product="Single ticket 1st", price_chf=51.0, class_of_travel="1"),
            FareProduct(product="Single ticket 2nd", price_chf=31.0, class_of_travel="2"),
            FareProduct(product="Supersaver", price_chf=22.6, class_of_travel="2"),
        ],
    )
    history = [
        {"role": "user", "content": "what are my ticket options from Bern to Zürich tomorrow?"},
        {"role": "assistant", "content": question},
        {"role": "user", "content": "the cheapest"},
    ]
    fake_openai = _FakeOpenAI([
        _tool_call_response([_tool_call(
            "call_1",
            "check_public_transport_fares",
            '{"origin": "Bern", "destination": "Zürich HB", "sort_by": "price"}',
        )]),
        _text_response("Sorted by cheapest."),
    ])

    events = _run(history, fake_openai, ojp_client=ojp)

    # The model saw the full journey context, not just the preference answer.
    sent_messages = fake_openai.calls[0]["messages"]
    assert sent_messages[-3]["content"] == history[0]["content"]
    assert sent_messages[-2]["content"] == question

    widget = next(e for e in events if e["type"] == "widget" and e["tool"] == "check_public_transport_fares")
    fares = widget["data"]["fares"]
    assert [f["price_chf"] for f in fares] == [22.6, 31.0, 51.0]
    assert widget["data"]["sorted_by"] == "price"
    assert widget["data"]["booking_url"].startswith("https://sbb.ch/")
    assert "von=Bern" in widget["data"]["booking_url"]


def test_second_turn_sorts_connections_by_soonest_departure():
    ojp = _StubOjpClient(
        candidates_by_name=_swiss_candidates(),
        connections=[
            Connection(departure="2026-09-26T19:04:00Z", arrival="2026-09-26T19:57:00Z",
                       duration_minutes=53, changes=0),
            Connection(departure="2026-09-26T18:04:00Z", arrival="2026-09-26T18:57:00Z",
                       duration_minutes=53, changes=0),
        ],
    )
    history = [
        {"role": "user", "content": "connection options from Bern to Zürich tomorrow"},
        {"role": "assistant", "content": "Soonest departure or cheapest price?"},
        {"role": "user", "content": "the soonest departure"},
    ]
    fake_openai = _FakeOpenAI([
        _tool_call_response([_tool_call(
            "call_1",
            "find_connections",
            '{"origin": "Bern", "destination": "Zürich HB", "sort_by": "departure"}',
        )]),
        _text_response("Sorted by soonest departure."),
    ])

    events = _run(history, fake_openai, ojp_client=ojp)

    widget = next(e for e in events if e["type"] == "widget" and e["tool"] == "find_connections")
    departures = [c["departure"] for c in widget["data"]["connections"]]
    assert departures == ["2026-09-26T18:04:00Z", "2026-09-26T19:04:00Z"]
    assert widget["data"]["sorted_by"] == "departure"


def test_voice_channel_extends_system_prompt_with_link_instruction():
    fake_openai = _FakeOpenAI([_text_response("ok")])

    _run([{"role": "user", "content": "hi"}], fake_openai, channel="voice")

    system = fake_openai.calls[0]["messages"][0]["content"]
    assert "VOICE CHANNEL" in system
    assert "purchase link on their screen" in system
    assert "never read URLs aloud" in system


def test_text_channel_does_not_add_voice_prompt():
    fake_openai = _FakeOpenAI([_text_response("ok")])

    _run([{"role": "user", "content": "hi"}], fake_openai)

    system = fake_openai.calls[0]["messages"][0]["content"]
    assert "VOICE CHANNEL" not in system
    # The booking-link pointer exists for every channel.
    assert "Book on SBB" in system
