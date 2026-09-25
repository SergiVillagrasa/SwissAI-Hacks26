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


def _is_station_ref(stop_ref: str) -> bool:
    """Whether a ref identifies an actual stop/station, not a locality.

    OJP LIR also returns coarse locality entries (e.g. 'Basel' -> '22',
    'Lyon' -> '47') that share the place name but cannot be used for trip,
    board, or disruption requests. Real stops use namespaced refs
    ('ch:1:sloid:*', 'de:1:sloid:*') or UIC-style numeric refs of 6+
    digits (Swiss 85xxxxx, foreign stations like Lyon Part Dieu
    '8772319'); bare short numerics are locality ids.
    """
    ref = stop_ref.strip().lower()
    if ":" in ref:
        return True
    return ref.isdigit() and len(ref) >= 6


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

    # Prefer actual station refs over coarse locality entries: a locality
    # named exactly like the query (e.g. 'Basel' -> '22') would otherwise
    # win the exact match and resolve to a ref no downstream request can
    # use, or worse, make a Swiss city look foreign to the scope check.
    station_like = [c for c in candidates if _is_station_ref(c.stop_ref)]
    pool = station_like or candidates

    if len(pool) == 1:
        return pool[0], None

    normalized_query = normalize(query)
    for candidate in pool:
        if normalize(candidate.name) == normalized_query:
            return candidate, None

    ranked = sorted(pool, key=lambda c: c.probability or 0.0, reverse=True)
    best, second = ranked[0], ranked[1]
    if (best.probability or 0.0) - (second.probability or 0.0) >= DOMINANT_MATCH_MARGIN:
        return best, None

    return None, ConnectionSearchResult(
        status="needs_clarification",
        message=f"Multiple stations match {field_name} '{query}'. Please pick one.",
        candidates=ranked,
    )
