from swiss_grounding_mcp.config.settings import Settings


def test_defaults_when_env_empty():
    settings = Settings.from_env({})

    assert settings.ojp_api_token == ""
    assert settings.ojp_base_url == "https://api.opentransportdata.swiss/ojp20"
    assert settings.ojp_requestor_ref == "swiss-grounding-mcp"
    assert settings.ojp_timeout_seconds == 10.0
    assert settings.respect_robots_txt is True
    assert settings.mcp_http_host == "127.0.0.1"
    assert settings.mcp_http_port == 8000


def test_env_overrides_defaults():
    env = {
        "OJP_API_TOKEN": "secret-token",
        "OJP_BASE_URL": "https://example.test/ojp20",
        "OJP_REQUESTOR_REF": "my-app",
        "OJP_TIMEOUT_SECONDS": "5",
        "RESPECT_ROBOTS_TXT": "false",
        "MCP_HTTP_HOST": "0.0.0.0",
        "MCP_HTTP_PORT": "9000",
    }

    settings = Settings.from_env(env)

    assert settings.ojp_api_token == "secret-token"
    assert settings.ojp_base_url == "https://example.test/ojp20"
    assert settings.ojp_requestor_ref == "my-app"
    assert settings.ojp_timeout_seconds == 5.0
    assert settings.respect_robots_txt is False
    assert settings.mcp_http_host == "0.0.0.0"
    assert settings.mcp_http_port == 9000


def test_respect_robots_txt_accepts_common_truthy_strings():
    assert Settings.from_env({"RESPECT_ROBOTS_TXT": "true"}).respect_robots_txt is True
    assert Settings.from_env({"RESPECT_ROBOTS_TXT": "1"}).respect_robots_txt is True
    assert Settings.from_env({"RESPECT_ROBOTS_TXT": "false"}).respect_robots_txt is False
    assert Settings.from_env({"RESPECT_ROBOTS_TXT": "0"}).respect_robots_txt is False


def test_aviationstack_defaults_when_env_empty():
    settings = Settings.from_env({})

    assert settings.aviationstack_api_key == ""
    assert settings.aviationstack_base_url == "https://api.aviationstack.com/v1"
    assert settings.aviationstack_timeout_seconds == 10.0
    assert settings.aviationstack_enable is True
    assert settings.aviationstack_cache_seconds == 60.0


def test_aviationstack_env_overrides_defaults():
    env = {
        "AVIATIONSTACK_API_KEY": "test-key",
        "AVIATIONSTACK_BASE_URL": "https://example.test/v1",
        "AVIATIONSTACK_TIMEOUT_SECONDS": "5",
        "AVIATIONSTACK_ENABLE": "false",
        "AVIATIONSTACK_CACHE_SECONDS": "30",
    }

    settings = Settings.from_env(env)

    assert settings.aviationstack_api_key == "test-key"
    assert settings.aviationstack_base_url == "https://example.test/v1"
    assert settings.aviationstack_timeout_seconds == 5.0
    assert settings.aviationstack_enable is False
    assert settings.aviationstack_cache_seconds == 30.0
