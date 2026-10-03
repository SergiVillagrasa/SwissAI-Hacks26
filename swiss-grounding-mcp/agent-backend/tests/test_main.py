import importlib
import io
import os
from dataclasses import replace
from types import SimpleNamespace

import pytest
from agent_backend import main as main_module
from fastapi.testclient import TestClient


def _fake_openai_client():
    return SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(text=" fake transcript ")
            ),
            speech=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(read=lambda: b"fake-mp3-bytes")
            ),
        )
    )


@pytest.fixture(autouse=True)
def reset_access_state(monkeypatch):
    main_module._rate_limiter.limit = main_module.settings.rate_limit_per_minute
    main_module._daily_limiter.limit = main_module.settings.daily_request_limit
    main_module._rate_limiter.reset()
    main_module._daily_limiter.reset()
    monkeypatch.setattr(main_module, "_openai_client", _fake_openai_client())
    yield
    main_module._rate_limiter.reset()
    main_module._daily_limiter.reset()


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


def test_cors_allows_any_unconfigured_localhost_port(monkeypatch):
    # Regression: browser preview proxies and Vite's own port fallback serve
    # the frontend from a port nobody configured ahead of time. Those must
    # not need CORS_ALLOWED_ORIGIN edited by hand every time.
    previous_value = os.environ.get("CORS_ALLOW_ANY_LOCAL_PORT")
    monkeypatch.setenv("CORS_ALLOW_ANY_LOCAL_PORT", "true")
    importlib.reload(main_module)

    try:
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
    finally:
        if previous_value is None:
            monkeypatch.delenv("CORS_ALLOW_ANY_LOCAL_PORT", raising=False)
        else:
            monkeypatch.setenv("CORS_ALLOW_ANY_LOCAL_PORT", previous_value)
        importlib.reload(main_module)


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


def test_transcribe_endpoint_returns_openai_transcript_text(monkeypatch):
    def fake_create(*, model, file):
        assert model == main_module.settings.openai_transcribe_model
        assert file.read() == b"fake-audio-bytes"
        return SimpleNamespace(text=" hello there ")

    monkeypatch.setattr(
        main_module._openai_client.audio.transcriptions, "create", fake_create
    )

    client = TestClient(main_module.app)
    response = client.post(
        "/api/voice/transcribe",
        files={"audio": ("utterance.webm", io.BytesIO(b"fake-audio-bytes"), "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "hello there"}


def test_transcribe_endpoint_rejects_empty_upload():
    client = TestClient(main_module.app)

    response = client.post(
        "/api/voice/transcribe",
        files={"audio": ("utterance.webm", io.BytesIO(b""), "audio/webm")},
    )

    assert response.status_code == 400


def test_transcribe_endpoint_rejects_oversized_upload(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "settings",
        replace(
            main_module.settings,
            max_audio_upload_bytes=4,
            agent_api_key="required-key",
        ),
    )
    client = TestClient(main_module.app)

    response = client.post(
        "/api/voice/transcribe",
        files={"audio": ("utterance.webm", io.BytesIO(b"12345"), "audio/webm")},
        headers={"Authorization": "Bearer required-key"},
    )

    assert response.status_code == 413


def test_unauthenticated_oversized_content_length_is_rejected_before_body_limit(
    monkeypatch,
):
    monkeypatch.setattr(
        main_module,
        "settings",
        replace(main_module.settings, agent_api_key="required-key"),
    )
    client = TestClient(main_module.app)
    content_length = main_module.settings.max_audio_upload_bytes + 65_537

    response = client.post(
        "/api/voice/transcribe",
        content=b"",
        headers={"Content-Length": str(content_length)},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_speak_endpoint_returns_mp3_audio_bytes(monkeypatch):
    def fake_create(*, model, voice, input, response_format):
        assert model == main_module.settings.openai_tts_model
        assert voice == main_module.settings.openai_tts_voice
        assert input == "hello there"
        assert response_format == "mp3"
        return SimpleNamespace(read=lambda: b"fake-mp3-bytes")

    monkeypatch.setattr(main_module._openai_client.audio.speech, "create", fake_create)

    client = TestClient(main_module.app)
    response = client.post("/api/voice/speak", json={"text": "hello there"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"fake-mp3-bytes"


def test_speak_endpoint_rejects_empty_text():
    client = TestClient(main_module.app)

    response = client.post("/api/voice/speak", json={"text": "   "})

    assert response.status_code == 400


@pytest.mark.parametrize("role", ["system", "tool"])
def test_chat_rejects_unsupported_roles(role):
    response = TestClient(main_module.app).post(
        "/api/chat", json={"messages": [{"role": role, "content": "invalid"}]}
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"messages": [{"role": "user", "content": "hi"}] * 41},
        {"messages": [{"role": "user", "content": "x" * 8001}]},
        {"messages": [{"role": "user", "content": "hi"}], "channel": "x"},
        {"messages": []},
    ],
)
def test_chat_rejects_oversized_or_invalid_requests(payload):
    response = TestClient(main_module.app).post("/api/chat", json=payload)

    assert response.status_code == 422


def test_speak_rejects_text_over_1500_characters():
    response = TestClient(main_module.app).post(
        "/api/voice/speak", json={"text": "x" * 1501}
    )

    assert response.status_code == 422


def test_api_key_protects_post_routes_but_not_health(monkeypatch):
    monkeypatch.setattr(
        main_module, "settings", replace(main_module.settings, agent_api_key="key")
    )
    client = TestClient(main_module.app)

    missing = client.post("/api/voice/speak", json={"text": "hello"})
    wrong = client.post(
        "/api/voice/speak",
        json={"text": "hello"},
        headers={"Authorization": "Bearer wrong"},
    )
    authorized = client.post(
        "/api/voice/speak",
        json={"text": "hello"},
        headers={"Authorization": "Bearer key"},
    )

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert wrong.status_code == 401
    assert authorized.status_code == 200
    assert client.get("/api/health").status_code == 200


def test_auth_rejection_has_cors_headers_and_preflight_needs_no_key(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "settings",
        replace(main_module.settings, agent_api_key="key"),
    )
    client = TestClient(main_module.app)
    origin = main_module.settings.cors_allowed_origins[0]

    unauthorized = client.post(
        "/api/voice/speak",
        json={"text": "hello"},
        headers={"Origin": origin},
    )
    preflight = client.options(
        "/api/chat",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert unauthorized.status_code == 401
    assert unauthorized.headers["access-control-allow-origin"] == origin
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin


def test_per_ip_rate_limit_returns_retry_after():
    main_module._rate_limiter.limit = 2
    client = TestClient(main_module.app)

    assert client.post("/api/voice/speak", json={"text": "hi"}).status_code == 200
    assert client.post("/api/voice/speak", json={"text": "hi"}).status_code == 200
    blocked = client.post("/api/voice/speak", json={"text": "hi"})

    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1


def test_trusted_client_ip_header_separates_rate_limit_buckets(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "settings",
        replace(main_module.settings, client_ip_header="X-Real-IP"),
    )
    main_module._rate_limiter.limit = 1
    client = TestClient(main_module.app)

    first_ip = client.post(
        "/api/voice/speak", json={"text": "hi"}, headers={"X-Real-IP": "192.0.2.1"}
    )
    second_ip = client.post(
        "/api/voice/speak", json={"text": "hi"}, headers={"X-Real-IP": "192.0.2.2"}
    )
    blocked = client.post(
        "/api/voice/speak", json={"text": "hi"}, headers={"X-Real-IP": "192.0.2.1"}
    )

    assert first_ip.status_code == 200
    assert second_ip.status_code == 200
    assert blocked.status_code == 429


def test_daily_request_limit_is_global():
    main_module._daily_limiter.limit = 2
    client = TestClient(main_module.app)

    assert client.post("/api/voice/speak", json={"text": "hi"}).status_code == 200
    assert client.post("/api/voice/speak", json={"text": "hi"}).status_code == 200
    assert client.post("/api/voice/speak", json={"text": "hi"}).status_code == 429


def test_speak_openai_error_is_sanitized(monkeypatch):
    def fail(*args, **kwargs):
        raise main_module.openai.OpenAIError("SECRET-EXCEPTION")

    monkeypatch.setattr(main_module._openai_client.audio.speech, "create", fail)
    response = TestClient(main_module.app).post(
        "/api/voice/speak", json={"text": "hello"}
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Voice provider request failed."
    assert "SECRET-EXCEPTION" not in response.text


def test_transcribe_openai_error_is_sanitized(monkeypatch):
    def fail(*args, **kwargs):
        raise main_module.openai.OpenAIError("SECRET-EXCEPTION")

    monkeypatch.setattr(main_module._openai_client.audio.transcriptions, "create", fail)
    response = TestClient(main_module.app).post(
        "/api/voice/transcribe",
        files={"audio": ("utterance.webm", io.BytesIO(b"audio"), "audio/webm")},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Voice provider request failed."
    assert "SECRET-EXCEPTION" not in response.text
