from __future__ import annotations

from datetime import datetime, timezone

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Provenance


def build_provenance(
    settings: Settings,
    *,
    retrieved_at: datetime | None = None,
    source: str = "opentransportdata.swiss OJP 2.0",
    source_url: str | None = None,
) -> Provenance:
    timestamp = retrieved_at or datetime.now(timezone.utc)
    return Provenance(
        source=source,
        source_url=source_url or settings.ojp_base_url,
        retrieved_at=timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
