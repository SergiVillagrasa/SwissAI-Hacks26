import io
from types import SimpleNamespace

from fastapi.testclient import TestClient

from agent_backend import main as main_module


def test_health_endpoint_returns_ok():
    client = TestClient(main_module.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["openai_configured"], bool)


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
    # The /api/chat handler short-circuits to the "missing key" fallback
    # whenever _openai_client is None, so this must mock _openai_client
    # itself (not just run_chat) -- otherwise the test only exercises the
    # real code path when a real OPENAI_API_KEY happens to be set in the
    # environment, and silently takes the fallback branch (hiding this
    # test's own assertions) in a clean CI environment without one.
    monkeypatch.setattr(main_module, "_openai_client", SimpleNamespace())

    def fake_run_chat(messages, **kwargs):
        assert messages == [{"role": "user", "content": "hi"}]
        assert kwargs["run_id"]
        yield {"type": "run_started", "run_id": kwargs["run_id"], "sequence": 1}
        yield {"type": "token", "text": "hello"}
        yield {"type": "run_completed", "run_id": kwargs["run_id"], "sequence": 2}
        yield {"type": "done"}

    monkeypatch.setattr(main_module, "run_chat", fake_run_chat)

    client = TestClient(main_module.app)
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"type": "token", "text": "hello"}' in response.text
    assert 'data: {"type": "done"}' in response.text


def test_chat_endpoint_reports_missing_openai_key(monkeypatch):
    # Without a usable OpenAI key the app still serves a clean error
    # event instead of crashing at import or mid-request.
    monkeypatch.setattr(main_module, "_openai_client", None)

    client = TestClient(main_module.app)
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert response.status_code == 200
    assert '"type": "run_started"' in response.text
    assert '"status": "source_error"' in response.text
    assert "OPENAI_API_KEY" in response.text
    assert '"type": "run_completed"' in response.text
    assert 'data: {"type": "done"}' in response.text


def test_build_openai_client_returns_none_without_key():
    assert main_module._build_openai_client("") is None


def _fake_openai_client() -> SimpleNamespace:
    """A minimal stand-in for the OpenAI SDK client, structured so tests can
    still monkeypatch individual `.audio.transcriptions.create` /
    `.audio.speech.create` methods on it."""
    return SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(create=lambda **kwargs: None),
            speech=SimpleNamespace(create=lambda **kwargs: None),
        )
    )


def test_transcribe_endpoint_returns_openai_transcript_text(monkeypatch):
    fake_client = _fake_openai_client()
    monkeypatch.setattr(main_module, "_openai_client", fake_client)

    def fake_create(*, model, file):
        assert model == main_module.settings.openai_transcribe_model
        assert file.read() == b"fake-audio-bytes"
        return SimpleNamespace(text=" hello there ")

    monkeypatch.setattr(fake_client.audio.transcriptions, "create", fake_create)

    client = TestClient(main_module.app)
    response = client.post(
        "/api/voice/transcribe",
        files={"audio": ("utterance.webm", io.BytesIO(b"fake-audio-bytes"), "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "hello there"}


def test_transcribe_endpoint_rejects_empty_upload(monkeypatch):
    # Must still mock _openai_client: the handler checks for a configured
    # client before it checks for an empty upload, so without this mock the
    # test would get a 503 (missing key) instead of exercising the 400
    # (empty upload) path it's meant to check -- hermetic only by accident
    # of a real OPENAI_API_KEY being set locally.
    monkeypatch.setattr(main_module, "_openai_client", _fake_openai_client())

    client = TestClient(main_module.app)

    response = client.post(
        "/api/voice/transcribe",
        files={"audio": ("utterance.webm", io.BytesIO(b""), "audio/webm")},
    )

    assert response.status_code == 400


def test_speak_endpoint_returns_mp3_audio_bytes(monkeypatch):
    fake_client = _fake_openai_client()
    monkeypatch.setattr(main_module, "_openai_client", fake_client)

    def fake_create(*, model, voice, input, response_format):
        assert model == main_module.settings.openai_tts_model
        assert voice == main_module.settings.openai_tts_voice
        assert input == "hello there"
        assert response_format == "mp3"
        return SimpleNamespace(read=lambda: b"fake-mp3-bytes")

    monkeypatch.setattr(fake_client.audio.speech, "create", fake_create)

    client = TestClient(main_module.app)
    response = client.post("/api/voice/speak", json={"text": "hello there"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"fake-mp3-bytes"


def test_speak_endpoint_rejects_empty_text(monkeypatch):
    # See test_transcribe_endpoint_rejects_empty_upload: the missing-key
    # check runs before the empty-text check.
    monkeypatch.setattr(main_module, "_openai_client", _fake_openai_client())

    client = TestClient(main_module.app)

    response = client.post("/api/voice/speak", json={"text": "   "})

    assert response.status_code == 400
