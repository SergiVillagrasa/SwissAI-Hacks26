from __future__ import annotations

from swiss_grounding_mcp.sources.aerodatabox.client import AerodataboxClient
from swiss_grounding_mcp.sources.ojp.client import OjpClient
from swiss_grounding_mcp.sources.serpapi.flight_client import SerpApiFlightClient

from agent_backend.settings import AgentSettings


def build_ojp_client(settings: AgentSettings) -> OjpClient:
    return OjpClient(settings.mcp_settings)


def build_aviation_client(settings: AgentSettings) -> AerodataboxClient:
    return AerodataboxClient(settings.mcp_settings)


def build_flight_fares_client(settings: AgentSettings) -> SerpApiFlightClient:
    return SerpApiFlightClient(settings.mcp_settings)
