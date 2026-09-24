from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from swiss_grounding_mcp.config.settings import Settings as MCPSettings

_SERVER_ENV_PATH = Path(__file__).resolve().parents[3] / "server" / ".env"
_LOCAL_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"

# Matches http(s)://localhost:<port> and http(s)://127.0.0.1:<port> for any
# port. Dev tools (Vite's own port fallback when 3000 is busy, browser
# preview proxies, etc.) routinely serve the frontend from a port nobody
# configured ahead of time; without this, every new port is a fresh CORS
# rejection that has to be whitelisted by hand (see CORS_ALLOWED_ORIGIN and
# the regression test in test_main.py). Explicit CORS_ALLOWED_ORIGIN entries
# still apply on top of this and are what a non-local deployment should rely
# on; this regex only ever matches loopback origins.
LOCAL_DEV_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def _parse_bool(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class AgentSettings:
    openai_api_key: str
    openai_model: str
    openai_transcribe_model: str
    openai_tts_model: str
    openai_tts_voice: str
    host: str
    port: int
    cors_allowed_origin: str
    cors_allowed_origins: list[str]
    cors_allow_any_local_port: bool
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
            openai_transcribe_model=os.environ.get("OPENAI_TRANSCRIBE_MODEL", "whisper-1"),
            openai_tts_model=os.environ.get("OPENAI_TTS_MODEL", "tts-1"),
            openai_tts_voice=os.environ.get("OPENAI_TTS_VOICE", "alloy"),
            host=os.environ.get("AGENT_BACKEND_HOST", "127.0.0.1"),
            port=int(os.environ.get("AGENT_BACKEND_PORT", "3001")),
            cors_allowed_origin=cors_origins[0],
            cors_allowed_origins=cors_origins,
            cors_allow_any_local_port=_parse_bool(os.environ.get("CORS_ALLOW_ANY_LOCAL_PORT", "true")),
            mcp_settings=MCPSettings.from_env(),
        )
