from datetime import datetime, timezone
from types import SimpleNamespace

from swiss_grounding_mcp.domain.models import ConnectionSearchResult

from agent_backend import agent_loop
from agent_backend.agent_loop import run_chat


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


def test_system_prompt_includes_the_real_current_date_for_relative_time_words():
    # Regression: without a real "today" anchor, the model has no way to
    # correctly resolve "tomorrow"/"this weekend" and silently computes the
    # wrong absolute date, which OJP/AeroDataBox then answer for as if it
    # were valid (empty results), not as an error the user could act on.
    fake_openai = _FakeOpenAI([_text_response("ok")])
    fixed_now = datetime(2026, 9, 24, 18, 0, tzinfo=timezone.utc)

    list(run_chat(
        [{"role": "user", "content": "hi"}],
        openai_client=fake_openai, ojp_client=None, aviation_client=None,
        settings=None, model="gpt-4o-mini", now=fixed_now,
    ))

    system_message = fake_openai.calls[0]["messages"][0]
    assert system_message["role"] == "system"
    assert "2026-09-24" in system_message["content"]


def test_plain_text_reply_emits_token_then_done():
    fake_openai = _FakeOpenAI([_text_response("Hello there.")])

    events = list(run_chat(
        [{"role": "user", "content": "hi"}],
        openai_client=fake_openai, ojp_client=None, aviation_client=None,
        settings=None, model="gpt-4o-mini",
    ))

    assert events == [
        {"type": "token", "text": "Hello there."},
        {"type": "done"},
    ]


def test_single_tool_call_emits_widget_before_final_text(monkeypatch):
    def fake_dispatch(tool_name, arguments, *, ojp_client, aviation_client, settings):
        assert tool_name == "find_connections"
        assert arguments == {"origin": "Bern", "destination": "Zürich HB"}
        return ConnectionSearchResult(status="ok", connections=[])

    monkeypatch.setattr(agent_loop, "dispatch", fake_dispatch)

    fake_openai = _FakeOpenAI([
        _tool_call_response([_tool_call("call_1", "find_connections", '{"origin": "Bern", "destination": "Zürich HB"}')]),
        _text_response("Here are your options."),
    ])

    events = list(run_chat(
        [{"role": "user", "content": "trains from Bern to Zürich"}],
        openai_client=fake_openai, ojp_client="ojp", aviation_client="aviation",
        settings="settings", model="gpt-4o-mini",
    ))

    assert events[0]["type"] == "widget"
    widget_events = [event for event in events if event["type"] == "widget"]
    assert len(widget_events) == 1
    assert widget_events[0]["tool"] == "find_connections"
    assert widget_events[0]["status"] == "ok"
    assert events[-2] == {"type": "token", "text": "Here are your options."}
    assert events[-1] == {"type": "done"}
    # the widget must appear before the follow-up text (ordering matters for the UI)
    assert events.index(widget_events[0]) < len(events) - 2


def test_openai_failure_emits_source_error_widget_and_done():
    def _raise(**kwargs):
        raise RuntimeError("boom")

    fake_openai = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_raise))
    )

    events = list(run_chat(
        [{"role": "user", "content": "hi"}],
        openai_client=fake_openai, ojp_client=None, aviation_client=None,
        settings=None, model="gpt-4o-mini",
    ))

    assert events[0]["type"] == "widget"
    assert events[0]["status"] == "source_error"
    assert events[-1] == {"type": "done"}
