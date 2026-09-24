from agent_backend import clients
from agent_backend.settings import AgentSettings
from swiss_grounding_mcp.config.settings import Settings as MCPSettings


def _agent_settings() -> AgentSettings:
    return AgentSettings(
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
        host="127.0.0.1",
        port=8080,
        cors_allowed_origin="http://localhost:5173",
        cors_allowed_origins=["http://localhost:5173"],
        mcp_settings=MCPSettings(),
    )


def test_build_ojp_client_passes_mcp_settings(monkeypatch):
    captured = {}

    class FakeOjpClient:
        def __init__(self, settings):
            captured["settings"] = settings

    monkeypatch.setattr(clients, "OjpClient", FakeOjpClient)

    settings = _agent_settings()
    client = clients.build_ojp_client(settings)

    assert isinstance(client, FakeOjpClient)
    assert captured["settings"] is settings.mcp_settings


def test_build_aviation_client_passes_mcp_settings(monkeypatch):
    captured = {}

    class FakeAerodataboxClient:
        def __init__(self, settings):
            captured["settings"] = settings

    monkeypatch.setattr(clients, "AerodataboxClient", FakeAerodataboxClient)

    settings = _agent_settings()
    client = clients.build_aviation_client(settings)

    assert isinstance(client, FakeAerodataboxClient)
    assert captured["settings"] is settings.mcp_settings
