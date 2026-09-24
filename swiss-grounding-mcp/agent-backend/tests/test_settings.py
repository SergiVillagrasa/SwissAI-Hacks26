from agent_backend.settings import AgentSettings


def test_from_env_reads_agent_specific_vars(monkeypatch, tmp_path):
    # Point at an empty server .env so the test never depends on real
    # OJP/AeroDataBox credentials being present on the machine. Also
    # explicitly delenv them: another test module (e.g. test_main.py)
    # may have already loaded the real server/.env into os.environ
    # earlier in this pytest session, and an empty dotenv file does not
    # clear an already-set process environment variable.
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)
    monkeypatch.setattr("agent_backend.settings._SERVER_LOCAL_ENV_PATH", empty_env)
    monkeypatch.delenv("OJP_API_TOKEN", raising=False)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("AGENT_BACKEND_HOST", "0.0.0.0")
    monkeypatch.setenv("AGENT_BACKEND_PORT", "9090")
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN", "http://localhost:5173")

    settings = AgentSettings.from_env()

    assert settings.openai_api_key == "sk-test"
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.host == "0.0.0.0"
    assert settings.port == 9090
    assert settings.cors_allowed_origin == "http://localhost:5173"
    assert settings.mcp_settings.ojp_api_token == ""


def test_from_env_splits_comma_separated_cors_origins(monkeypatch, tmp_path):
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)
    monkeypatch.setattr("agent_backend.settings._SERVER_LOCAL_ENV_PATH", empty_env)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGIN",
        "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:45321",
    )

    settings = AgentSettings.from_env()

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:45321",
    ]


def test_from_env_defaults_cors_origins_to_common_local_dev_hosts(monkeypatch, tmp_path):
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)
    monkeypatch.setattr("agent_backend.settings._SERVER_LOCAL_ENV_PATH", empty_env)
    empty_local_env = tmp_path / "local.env"
    empty_local_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._LOCAL_ENV_PATH", empty_local_env)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("CORS_ALLOWED_ORIGIN", raising=False)

    settings = AgentSettings.from_env()

    assert settings.cors_allowed_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_from_env_defaults_cors_allow_any_local_port_to_true(monkeypatch, tmp_path):
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)
    monkeypatch.setattr("agent_backend.settings._SERVER_LOCAL_ENV_PATH", empty_env)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("CORS_ALLOW_ANY_LOCAL_PORT", raising=False)

    settings = AgentSettings.from_env()

    assert settings.cors_allow_any_local_port is True


def test_from_env_can_disable_cors_allow_any_local_port(monkeypatch, tmp_path):
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)
    monkeypatch.setattr("agent_backend.settings._SERVER_LOCAL_ENV_PATH", empty_env)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("CORS_ALLOW_ANY_LOCAL_PORT", "false")

    settings = AgentSettings.from_env()

    assert settings.cors_allow_any_local_port is False


def test_from_env_defaults_model_when_unset(monkeypatch, tmp_path):
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)
    monkeypatch.setattr("agent_backend.settings._SERVER_LOCAL_ENV_PATH", empty_env)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    settings = AgentSettings.from_env()

    assert settings.openai_model == "gpt-4o-mini"
