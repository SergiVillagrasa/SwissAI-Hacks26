from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _parse_bool(value: str, default: bool) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    return default


@dataclass(frozen=True)
class Settings:
    ojp_api_token: str = ""
    ojp_base_url: str = "https://api.opentransportdata.swiss/ojp20"
    ojp_requestor_ref: str = "swiss-grounding-mcp"
    ojp_timeout_seconds: float = 10.0
    respect_robots_txt: bool = True
    mcp_http_host: str = "127.0.0.1"
    mcp_http_port: int = 8000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        defaults = cls()
        return cls(
            ojp_api_token=source.get("OJP_API_TOKEN", defaults.ojp_api_token),
            ojp_base_url=source.get("OJP_BASE_URL", defaults.ojp_base_url),
            ojp_requestor_ref=source.get("OJP_REQUESTOR_REF", defaults.ojp_requestor_ref),
            ojp_timeout_seconds=float(
                source.get("OJP_TIMEOUT_SECONDS", defaults.ojp_timeout_seconds)
            ),
            respect_robots_txt=_parse_bool(
                source.get("RESPECT_ROBOTS_TXT", str(defaults.respect_robots_txt)),
                defaults.respect_robots_txt,
            ),
            mcp_http_host=source.get("MCP_HTTP_HOST", defaults.mcp_http_host),
            mcp_http_port=int(source.get("MCP_HTTP_PORT", defaults.mcp_http_port)),
        )
