from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from swiss_grounding_mcp.config.settings import Settings as MCPSettings

_SERVER_ENV_PATH = Path(__file__).resolve().parents[3] / "server" / ".env"


@dataclass(frozen=True)
class AgentSettings:
    openai_api_key: str
    openai_model: str
    host: str
    port: int
    cors_allowed_origin: str
    mcp_settings: MCPSettings

    @classmethod
    def from_env(cls) -> "AgentSettings":
        # Load the MCP server's own .env first so OJP_API_TOKEN and
        # AERODATABOX_API_KEY are available without duplicating them here.
        load_dotenv(_SERVER_ENV_PATH)
        load_dotenv()  # this package's own .env, if present
        return cls(
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            host=os.environ.get("AGENT_BACKEND_HOST", "127.0.0.1"),
            port=int(os.environ.get("AGENT_BACKEND_PORT", "8080")),
            cors_allowed_origin=os.environ.get(
                "CORS_ALLOWED_ORIGIN", "http://localhost:5173"
            ),
            mcp_settings=MCPSettings.from_env(),
        )
