from __future__ import annotations

from datetime import datetime, timezone

from swiss_grounding_mcp.domain.models import AirportGuidanceResult
from swiss_grounding_mcp.sources.zrh.guidance import GUIDANCE_TOPICS


def get_airport_guidance(topic: str) -> AirportGuidanceResult:
    if not topic or not topic.strip():
        return AirportGuidanceResult(
            status="needs_context",
            topic=topic,
            message="Please specify a guidance topic.",
        )

    record = GUIDANCE_TOPICS.get(topic)
    if record is None:
        return AirportGuidanceResult(
            status="out_of_scope",
            topic=topic,
            message=(
                f"'{topic}' is not a supported guidance topic. Supported topics: "
                + ", ".join(sorted(GUIDANCE_TOPICS))
            ),
        )

    return AirportGuidanceResult(
        status="answered",
        topic=topic,
        guidance=record.text,
        source=record.source,
        source_url=record.source_url,
        retrieved_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        applicable_airport="ZRH / LSZH",
        limitations=record.limitations,
    )
