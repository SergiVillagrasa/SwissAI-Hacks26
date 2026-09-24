from __future__ import annotations

import unicodedata

from swiss_grounding_mcp.domain.models import ConnectionSearchResult, StopCandidate

DOMINANT_MATCH_MARGIN = 0.3


def is_swiss_stop(stop_ref: str) -> bool:
    ref = stop_ref.strip().lower()
    if ref.startswith("ch:"):
        return True
    if ":" not in ref and ref.isdigit():
        return ref.startswith("85")
    return False


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.strip().lower()


def resolve_station(
    query: str, candidates: list[StopCandidate], field_name: str
) -> tuple[StopCandidate | None, ConnectionSearchResult | None]:
    if not candidates:
        return None, ConnectionSearchResult(
            status="not_found",
            message=f"No station matches {field_name} '{query}'.",
        )

    if len(candidates) == 1:
        return candidates[0], None

    normalized_query = normalize(query)
    for candidate in candidates:
        if normalize(candidate.name) == normalized_query:
            return candidate, None

    ranked = sorted(candidates, key=lambda c: c.probability or 0.0, reverse=True)
    best, second = ranked[0], ranked[1]
    if (best.probability or 0.0) - (second.probability or 0.0) >= DOMINANT_MATCH_MARGIN:
        return best, None

    return None, ConnectionSearchResult(
        status="needs_clarification",
        message=f"Multiple stations match {field_name} '{query}'. Please pick one.",
        candidates=ranked,
    )
