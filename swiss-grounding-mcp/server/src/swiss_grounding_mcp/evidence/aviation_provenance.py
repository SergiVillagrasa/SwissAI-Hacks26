from __future__ import annotations

from datetime import datetime, timezone

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import AviationProvenance


def build_aviation_provenance(
    settings: Settings, *, applicable_date: str, retrieved_at: datetime | None = None
) -> AviationProvenance:
    timestamp = retrieved_at or datetime.now(timezone.utc)
    return AviationProvenance(
        source="aviationstack.com",
        source_url=f"{settings.aviationstack_base_url}/flights",
        retrieved_at=timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        applicable_date=applicable_date,
        timezone="Europe/Zurich",
    )
