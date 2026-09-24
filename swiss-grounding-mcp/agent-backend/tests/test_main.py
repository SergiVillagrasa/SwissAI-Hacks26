from fastapi.testclient import TestClient

from agent_backend import main as main_module


def test_health_endpoint_returns_ok():
    client = TestClient(main_module.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_streams_events_from_run_chat(monkeypatch):
    def fake_run_chat(messages, **kwargs):
        assert messages == [{"role": "user", "content": "hi"}]
        yield {"type": "token", "text": "hello"}
        yield {"type": "done"}

    monkeypatch.setattr(main_module, "run_chat", fake_run_chat)

    client = TestClient(main_module.app)
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"type": "token", "text": "hello"}' in response.text
    assert 'data: {"type": "done"}' in response.text
