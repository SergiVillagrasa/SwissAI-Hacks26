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
    ojp_fare_url: str = "https://api.opentransportdata.swiss/ojpfare/"
    ojp_requestor_ref: str = "swiss-grounding-mcp"
    ojp_timeout_seconds: float = 10.0
    respect_robots_txt: bool = True
    mcp_http_host: str = "127.0.0.1"
    mcp_http_port: int = 8000
    aerodatabox_api_key: str = ""
    aerodatabox_host: str = "aerodatabox.p.rapidapi.com"
    aerodatabox_base_url: str = "https://aerodatabox.p.rapidapi.com"
    aerodatabox_timeout_seconds: float = 10.0
    aerodatabox_enable: bool = True
    aerodatabox_cache_seconds: float = 60.0
    serpapi_api_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search.json"
    serpapi_timeout_seconds: float = 10.0
    trip_time_margin_minutes: float = 10.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        defaults = cls()
        return cls(
            ojp_api_token=source.get("OJP_API_TOKEN", defaults.ojp_api_token),
            ojp_base_url=source.get("OJP_BASE_URL", defaults.ojp_base_url),
            ojp_fare_url=source.get("OJP_FARE_URL", defaults.ojp_fare_url),
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
            aerodatabox_api_key=source.get(
                "AERODATABOX_API_KEY", defaults.aerodatabox_api_key
            ),
            aerodatabox_host=source.get("AERODATABOX_HOST", defaults.aerodatabox_host),
            aerodatabox_base_url=source.get(
                "AERODATABOX_BASE_URL", defaults.aerodatabox_base_url
            ),
            aerodatabox_timeout_seconds=float(
                source.get(
                    "AERODATABOX_TIMEOUT_SECONDS", defaults.aerodatabox_timeout_seconds
                )
            ),
            aerodatabox_enable=_parse_bool(
                source.get("AERODATABOX_ENABLE", str(defaults.aerodatabox_enable)),
                defaults.aerodatabox_enable,
            ),
            aerodatabox_cache_seconds=float(
                source.get(
                    "AERODATABOX_CACHE_SECONDS", defaults.aerodatabox_cache_seconds
                )
            ),
            serpapi_api_key=source.get("SERPAPI_API_KEY", defaults.serpapi_api_key),
            serpapi_base_url=source.get("SERPAPI_BASE_URL", defaults.serpapi_base_url),
            serpapi_timeout_seconds=float(
                source.get("SERPAPI_TIMEOUT_SECONDS", defaults.serpapi_timeout_seconds)
            ),
            trip_time_margin_minutes=float(
                source.get(
                    "TRIP_TIME_MARGIN_MINUTES", defaults.trip_time_margin_minutes
                )
            ),
        )
