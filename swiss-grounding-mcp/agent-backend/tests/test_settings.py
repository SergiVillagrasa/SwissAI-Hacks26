from agent_backend.settings import AgentSettings


def test_from_env_reads_agent_specific_vars(monkeypatch, tmp_path):
    # Point at an empty server .env so the test never depends on real
    # OJP/AeroDataBox credentials being present on the machine.
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)

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


def test_from_env_defaults_model_when_unset(monkeypatch, tmp_path):
    empty_env = tmp_path / "server.env"
    empty_env.write_text("")
    monkeypatch.setattr("agent_backend.settings._SERVER_ENV_PATH", empty_env)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    settings = AgentSettings.from_env()

    assert settings.openai_model == "gpt-4o-mini"
