from swiss_grounding_mcp.config.settings import Settings


def test_defaults_when_env_empty():
    settings = Settings.from_env({})

    assert settings.ojp_api_token == ""
    assert settings.ojp_base_url == "https://api.opentransportdata.swiss/ojp20"
    assert settings.ojp_fare_url == "https://api.opentransportdata.swiss/ojpfare/"
    assert settings.ojp_requestor_ref == "swiss-grounding-mcp"
    assert settings.ojp_timeout_seconds == 10.0
    assert settings.respect_robots_txt is True
    assert settings.mcp_http_host == "127.0.0.1"
    assert settings.mcp_http_port == 8000


def test_env_overrides_defaults():
    env = {
        "OJP_API_TOKEN": "secret-token",
        "OJP_BASE_URL": "https://example.test/ojp20",
        "OJP_FARE_URL": "https://example.test/ojpfare/",
        "OJP_REQUESTOR_REF": "my-app",
        "OJP_TIMEOUT_SECONDS": "5",
        "RESPECT_ROBOTS_TXT": "false",
        "MCP_HTTP_HOST": "0.0.0.0",
        "MCP_HTTP_PORT": "9000",
    }

    settings = Settings.from_env(env)

    assert settings.ojp_api_token == "secret-token"
    assert settings.ojp_base_url == "https://example.test/ojp20"
    assert settings.ojp_fare_url == "https://example.test/ojpfare/"
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


def test_aerodatabox_defaults_when_env_empty():
    settings = Settings.from_env({})

    assert settings.aerodatabox_api_key == ""
    assert settings.aerodatabox_host == "aerodatabox.p.rapidapi.com"
    assert settings.aerodatabox_base_url == "https://aerodatabox.p.rapidapi.com"
    assert settings.aerodatabox_timeout_seconds == 10.0
    assert settings.aerodatabox_enable is True
    assert settings.aerodatabox_cache_seconds == 60.0


def test_aerodatabox_env_overrides_defaults():
    env = {
        "AERODATABOX_API_KEY": "test-key",
        "AERODATABOX_HOST": "example.rapidapi.com",
        "AERODATABOX_BASE_URL": "https://example.test",
        "AERODATABOX_TIMEOUT_SECONDS": "5",
        "AERODATABOX_ENABLE": "false",
        "AERODATABOX_CACHE_SECONDS": "30",
    }

    settings = Settings.from_env(env)

    assert settings.aerodatabox_api_key == "test-key"
    assert settings.aerodatabox_host == "example.rapidapi.com"
    assert settings.aerodatabox_base_url == "https://example.test"
    assert settings.aerodatabox_timeout_seconds == 5.0
    assert settings.aerodatabox_enable is False
    assert settings.aerodatabox_cache_seconds == 30.0


def test_serpapi_defaults_and_env_overrides():
    defaults = Settings.from_env({})
    configured = Settings.from_env(
        {
            "SERPAPI_API_KEY": "test-key",
            "SERPAPI_BASE_URL": "https://example.test/search.json",
            "SERPAPI_TIMEOUT_SECONDS": "4",
        }
    )

    assert defaults.serpapi_api_key == ""
    assert defaults.serpapi_base_url == "https://serpapi.com/search.json"
    assert defaults.serpapi_timeout_seconds == 10.0
    assert configured.serpapi_api_key == "test-key"
    assert configured.serpapi_base_url == "https://example.test/search.json"
    assert configured.serpapi_timeout_seconds == 4.0
