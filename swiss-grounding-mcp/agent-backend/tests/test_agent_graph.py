from datetime import datetime, timezone
from types import SimpleNamespace

from agent_backend import agent_graph
from agent_backend.agent_loop import run_chat


def _response(content=None, tool_calls=None, finish_reason=None):
    choice = SimpleNamespace(message=SimpleNamespace(
        content=content,
        tool_calls=tool_calls or [],
    ))
    if finish_reason is not None:
        choice.finish_reason = finish_reason
    return SimpleNamespace(choices=[choice])


class _FakeOpenAI:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.responses)


def _run(client, **kwargs):
    return list(run_chat(
        [{"role": "user", "content": "hello"}],
        openai_client=client,
        ojp_client=None,
        aviation_client=None,
        settings=None,
        model="test-model",
        run_id="run-1",
        now=datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
        **kwargs,
    ))


def test_plain_reply_emits_graph_lifecycle_and_preserves_chat_events():
    client = _FakeOpenAI([_response(content="Hello")])
    events = _run(client)

    assert events[0]["type"] == "run_started"
    assert [event["type"] for event in events if event["type"] in {"token", "widget", "done"}] == ["token", "done"]
    assert next(event for event in events if event["type"] == "run_completed")["outcome"] == "completed"
    assert [event["label"] for event in events if event["type"] == "node_skipped"] == ["Invoke Swiss tool", "Verify result"]
    assert events[-1] == {"type": "done"}
    assert client.calls[0]["max_completion_tokens"] == 1024


def test_model_output_token_limit_can_be_disabled():
    client = _FakeOpenAI([_response(content="Hello")])

    _run(client, max_output_tokens=0)

    assert "max_completion_tokens" not in client.calls[0]


def test_truncated_tool_call_fails_without_executing_tool(monkeypatch):
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(
            name="find_connections",
            arguments='{"origin":"Zurich","destination":',
        ),
    )
    executed = []
    monkeypatch.setattr(
        agent_graph,
        "dispatch",
        lambda *args, **kwargs: executed.append((args, kwargs)),
    )

    events = _run(_FakeOpenAI([
        _response(tool_calls=[tool_call], finish_reason="length"),
    ]))

    assert executed == []
    assert any(event["type"] == "node_failed" for event in events)
    source_error = next(
        event for event in events
        if event["type"] == "widget" and event["status"] == "source_error"
    )
    assert source_error["data"]["message"] == (
        "The assistant's response hit the output limit before it could finish. "
        "Please ask a more specific question."
    )
    assert next(event for event in events if event["type"] == "run_completed")[
        "outcome"
    ] == "failed"


def test_truncated_text_reply_emits_cut_short_marker():
    events = _run(_FakeOpenAI([
        _response(content="Partial reply", finish_reason="length"),
    ]))

    assert [
        event["text"] for event in events if event["type"] == "token"
    ] == [
        "Partial reply",
        "\n\n(Response cut short: output limit reached.)",
    ]
    assert next(event for event in events if event["type"] == "run_completed")[
        "outcome"
    ] == "completed"


def test_final_reply_after_tool_call_uses_additional_round_labels(monkeypatch):
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="find_connections", arguments='{"origin":"Zurich HB","destination":"Lucerne"}'),
    )
    monkeypatch.setattr(agent_graph, "dispatch", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_graph, "map_result", lambda *args: {"status": "ok", "data": {}})

    events = _run(_FakeOpenAI([
        _response(tool_calls=[tool_call]),
        _response(content="Take the IR from Zurich HB to Lucerne."),
    ]))

    skipped = [event for event in events if event["type"] == "node_skipped"]
    assert [event["label"] for event in skipped] == ["Additional Swiss tool call", "Additional verification"]
    assert all(event["summary"] == "No further lookup needed" for event in skipped)


def test_clarification_marks_run_waiting(monkeypatch):
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="find_connections", arguments='{"origin":"Bern"}'),
    )
    monkeypatch.setattr(agent_graph, "dispatch", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_graph, "map_result", lambda *args: {
        "status": "needs_clarification",
        "data": {"message": "Which station?", "candidates": ["Bern"]},
    })

    events = _run(_FakeOpenAI([_response(tool_calls=[tool_call])]))

    assert any(event["type"] == "run_waiting" for event in events)
    assert next(event for event in events if event["type"] == "run_completed")["outcome"] == "waiting"


def test_model_failure_emits_failed_node_and_run_before_done():
    class _Broken:
        def create(self, **kwargs):
            raise RuntimeError("boom")

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Broken()))
    events = _run(client)

    assert any(event["type"] == "node_failed" for event in events)
    assert next(event for event in events if event["type"] == "run_completed")["outcome"] == "failed"
    assert events[-1] == {"type": "done"}
