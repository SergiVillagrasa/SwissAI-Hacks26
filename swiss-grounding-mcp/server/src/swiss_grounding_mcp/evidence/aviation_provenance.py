from __future__ import annotations

from datetime import datetime, timezone

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import AviationProvenance


def build_aviation_provenance(
    settings: Settings, *, applicable_date: str, retrieved_at: datetime | None = None
) -> AviationProvenance:
    timestamp = retrieved_at or datetime.now(timezone.utc)
    return AviationProvenance(
        source="AeroDataBox (aerodatabox.com)",
        source_url="https://aerodatabox.com",
        retrieved_at=timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        applicable_date=applicable_date,
        # All flight times returned by this server come from AeroDataBox's
        # `.utc` time fields (see sources/aerodatabox/parser.py), never the
        # `.local` fields, so the correct label is UTC, not the airport's
        # local zone. This keeps the timezone consistent with the train
        # tools, which also always report UTC (`Provenance.timezone`).
        timezone="UTC",
    )
