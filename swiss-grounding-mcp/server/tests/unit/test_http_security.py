import pytest
from starlette.testclient import TestClient
from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.http_security import (
    SlidingWindowRateLimiter,
    bearer_token_matches,
    client_ip,
    redact,
)
from swiss_grounding_mcp.server import (
    build_http_app,
    ensure_http_exposure_is_safe,
)


def test_sliding_window_rate_limiter_allows_limit_then_blocks_and_expires():
    now = [0.0]
    limiter = SlidingWindowRateLimiter(2, 60, clock=lambda: now[0])

    assert limiter.check("client") is None
    assert limiter.check("client") is None
    retry_after = limiter.check("client")
    assert retry_after == 60

    now[0] = 60
    assert limiter.check("client") is None


def test_sliding_window_rate_limiter_can_be_disabled_and_keys_are_independent():
    disabled = SlidingWindowRateLimiter(0, 60, clock=lambda: 0)
    assert all(disabled.check("client") is None for _ in range(5))

    limiter = SlidingWindowRateLimiter(1, 60, clock=lambda: 0)
    assert limiter.check("first") is None
    assert limiter.check("second") is None
    assert limiter.check("first") is not None


def test_sliding_window_rate_limiter_reset_clears_state():
    limiter = SlidingWindowRateLimiter(1, 60, clock=lambda: 0)
    assert limiter.check("client") is None
    assert limiter.check("client") is not None

    limiter.reset()

    assert limiter.check("client") is None


def test_client_ip_uses_trusted_header_case_insensitively_and_first_value():
    assert client_ip({"X-REAL-IP": " 192.0.2.1 "}, "127.0.0.1", "x-real-ip") == (
        "192.0.2.1"
    )
    assert client_ip({"x-real-ip": "192.0.2.1, 10.0.0.1"}, None, "X-Real-IP") == (
        "192.0.2.1"
    )
    assert client_ip({}, "127.0.0.1", "X-Real-IP") == "127.0.0.1"
    assert client_ip({}, None, "") == "unknown"


@pytest.mark.parametrize(
    ("authorization", "expected", "matches"),
    [
        ("Bearer secret", "secret", True),
        ("bearer secret", "secret", True),
        ("Basic secret", "secret", False),
        ("Bearer wrong", "secret", False),
        (None, "secret", False),
        ("Bearer secret", "", False),
    ],
)
def test_bearer_token_matches(authorization, expected, matches):
    assert bearer_token_matches(authorization, expected) is matches


def test_redact_replaces_all_nonempty_secrets():
    assert redact("key=secret and token=abc", "secret", "", "abc") == (
        "key=*** and token=***"
    )


@pytest.mark.parametrize(
    ("host", "settings", "raises"),
    [
        ("0.0.0.0", Settings(), True),
        ("0.0.0.0", Settings(mcp_auth_token="token"), False),
        ("0.0.0.0", Settings(mcp_allow_unauthenticated=True), False),
        ("127.0.0.1", Settings(), False),
        ("localhost", Settings(), False),
        ("::1", Settings(), False),
    ],
)
def test_ensure_http_exposure_is_safe(host, settings, raises):
    if raises:
        with pytest.raises(SystemExit, match="MCP_AUTH_TOKEN.*MCP_ALLOW_UNAUTHENTICATED"):
            ensure_http_exposure_is_safe(host, settings)
    else:
        ensure_http_exposure_is_safe(host, settings)


def _initialize(client, token=None, extra_headers=None):
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "host": "127.0.0.1:8000",
    }
    if token is not None:
        headers["authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    return client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        },
    )


def test_build_http_app_requires_correct_bearer_token_and_initializes():
    settings = Settings(mcp_auth_token="expected-token")
    with TestClient(build_http_app(settings, "127.0.0.1")) as client:
        missing = _initialize(client)
        wrong = _initialize(client, "wrong-token")
        authorized = _initialize(client, "expected-token")

    assert missing.status_code == 401
    assert missing.json() == {"error": "unauthorized"}
    assert missing.headers["www-authenticate"] == "Bearer"
    assert wrong.status_code == 401
    assert authorized.status_code == 200


def test_build_http_app_rate_limits_after_two_requests():
    settings = Settings(mcp_auth_token="expected-token", mcp_rate_limit_per_minute=2)
    with TestClient(build_http_app(settings, "127.0.0.1")) as client:
        assert _initialize(client, "expected-token").status_code == 200
        assert _initialize(client, "expected-token").status_code == 200
        blocked = _initialize(client, "expected-token")

    assert blocked.status_code == 429
    assert blocked.json() == {"error": "rate_limited"}
    assert int(blocked.headers["retry-after"]) >= 1


def test_build_http_app_allows_configured_browser_origins_only():
    settings = Settings(
        mcp_allowed_hosts=("example.com",),
        mcp_allowed_origins=("https://example.com",),
    )
    with TestClient(build_http_app(settings, "127.0.0.1")) as client:
        allowed = _initialize(
            client,
            extra_headers={
                "host": "example.com",
                "origin": "https://example.com",
            },
        )
        unlisted = _initialize(
            client,
            extra_headers={
                "host": "example.com",
                "origin": "https://unlisted.example",
            },
        )

    assert allowed.status_code == 200
    assert unlisted.status_code == 403
