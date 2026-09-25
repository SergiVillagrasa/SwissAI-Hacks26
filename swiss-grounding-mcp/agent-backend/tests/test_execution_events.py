from datetime import datetime, timezone

import pytest

from agent_backend.execution_events import ExecutionEventEmitter, sanitize_details


def test_emitter_adds_monotonic_sequence_and_timestamp():
    fixed_now = datetime(2026, 9, 25, 10, 15, 30, tzinfo=timezone.utc)
    emitter = ExecutionEventEmitter("run-1", now=lambda: fixed_now)

    first = emitter.emit(
        "node_started",
        node_id="model-1",
        label="Understand request",
        status="running",
        summary="Interpreting your request",
    )
    second = emitter.emit(
        "node_completed",
        node_id="model-1",
        label="Understand request",
        status="completed",
        summary="Request understood",
        duration_ms=12,
    )

    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert first["timestamp"] == "2026-09-25T10:15:30+00:00"
    assert "duration_ms" not in first
    assert second["duration_ms"] == 12


def test_sanitize_details_keeps_only_named_scalar_values():
    assert sanitize_details({
        "origin": "Bern",
        "count": 3,
        "available": True,
        "nested": {"secret": "x"},
        "items": [1],
        "error": RuntimeError("secret"),
    }) == {"origin": "Bern", "count": 3, "available": True}


def test_emitter_omits_unsupported_optional_fields_and_exception_values():
    emitter = ExecutionEventEmitter("run-1")

    event = emitter.emit(
        "node_failed",
        node_id="model-1",
        label="Understand request",
        status="failed",
        summary="The assistant service is unavailable",
        error=RuntimeError("secret"),
        raw_payload="hidden",
    )

    assert "error" not in event
    assert "raw_payload" not in event


def test_emitter_rejects_unknown_event_type_without_advancing_sequence():
    emitter = ExecutionEventEmitter("run-1")

    with pytest.raises(ValueError, match="Unsupported execution event type"):
        emitter.emit(
            "debug_dump",
            node_id="model-1",
            label="Debug",
            status="running",
            summary="Debugging",
        )

    valid = emitter.emit(
        "run_started",
        node_id="run",
        label="Run started",
        status="running",
        summary="Starting your request",
    )
    assert valid["sequence"] == 1
