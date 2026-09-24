from fastapi.testclient import TestClient

from agent_backend import main as main_module


def test_health_endpoint_returns_ok():
    client = TestClient(main_module.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_every_configured_origin_not_just_the_first():
    # Regression: a single hardcoded allow_origins=[settings.cors_allowed_origin]
    # rejected any origin other than exactly the first configured one (e.g. a
    # dev tool that serves the frontend through a proxy on a different port).
    client = TestClient(main_module.app)

    for origin in main_module.settings.cors_allowed_origins:
        response = client.options(
            "/api/chat",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200, f"origin {origin} was rejected"
        assert response.headers["access-control-allow-origin"] == origin


def test_cors_allows_any_unconfigured_localhost_port():
    # Regression: browser preview proxies and Vite's own port fallback serve
    # the frontend from a port nobody configured ahead of time. Those must
    # not need CORS_ALLOWED_ORIGIN edited by hand every time.
    client = TestClient(main_module.app)

    for origin in ["http://localhost:54321", "http://127.0.0.1:54321"]:
        response = client.options(
            "/api/chat",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200, f"origin {origin} was rejected"
        assert response.headers["access-control-allow-origin"] == origin


def test_cors_rejects_non_local_origin_not_in_allowlist():
    client = TestClient(main_module.app)

    response = client.options(
        "/api/chat",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers


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
