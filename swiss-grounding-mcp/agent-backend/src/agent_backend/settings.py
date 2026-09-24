from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from swiss_grounding_mcp.config.settings import Settings as MCPSettings

_SERVER_ENV_PATH = Path(__file__).resolve().parents[3] / "server" / ".env"
_LOCAL_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


@dataclass(frozen=True)
class AgentSettings:
    openai_api_key: str
    openai_model: str
    host: str
    port: int
    cors_allowed_origin: str
    cors_allowed_origins: list[str]
    mcp_settings: MCPSettings

    @classmethod
    def from_env(cls) -> "AgentSettings":
        # Load the MCP server's own .env first so OJP_API_TOKEN and
        # AERODATABOX_API_KEY are available without duplicating them here.
        load_dotenv(_SERVER_ENV_PATH)
        load_dotenv(_LOCAL_ENV_PATH)  # this package's own .env, if present
        raw_cors_origins = os.environ.get("CORS_ALLOWED_ORIGIN", _DEFAULT_CORS_ORIGINS)
        cors_origins = [origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()]
        return cls(
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            host=os.environ.get("AGENT_BACKEND_HOST", "127.0.0.1"),
            port=int(os.environ.get("AGENT_BACKEND_PORT", "8080")),
            cors_allowed_origin=cors_origins[0],
            cors_allowed_origins=cors_origins,
            mcp_settings=MCPSettings.from_env(),
        )
