import json

from agent_backend.sse import format_sse


def test_format_sse_wraps_json_payload_in_data_frame():
    frame = format_sse({"type": "token", "text": "hi"})

    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    payload = json.loads(frame[len("data: "):].strip())
    assert payload == {"type": "token", "text": "hi"}
