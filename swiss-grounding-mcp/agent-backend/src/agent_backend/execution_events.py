from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

_EVENT_TYPES = {
    "run_started",
    "node_started",
    "node_completed",
    "node_skipped",
    "node_failed",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "run_waiting",
    "run_completed",
}
_OPTIONAL_FIELDS = {"tool", "source", "duration_ms", "details", "outcome", "error"}
_SCALAR_TYPES = (str, int, float, bool, type(None))


def sanitize_details(value: object) -> dict[str, str | int | float | bool | None]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, _SCALAR_TYPES)
    }


class ExecutionEventEmitter:
    def __init__(self, run_id: str, now: Callable[[], datetime] | None = None):
        self.run_id = run_id
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._sequence = 0

    def emit(
        self,
        event_type: str,
        *,
        node_id: str,
        label: str,
        status: str,
        summary: str,
        **optional: Any,
    ) -> dict:
        if event_type not in _EVENT_TYPES:
            raise ValueError(f"Unsupported execution event type: {event_type}")

        self._sequence += 1
        event = {
            "type": event_type,
            "run_id": self.run_id,
            "sequence": self._sequence,
            "timestamp": self._now().astimezone(timezone.utc).isoformat(),
            "node_id": node_id,
            "label": label,
            "status": status,
            "summary": summary,
        }
        for key, value in optional.items():
            if key not in _OPTIONAL_FIELDS:
                continue
            if key == "details":
                details = sanitize_details(value)
                if details:
                    event[key] = details
            elif isinstance(value, _SCALAR_TYPES):
                event[key] = value
        return event
