"""Galtea evaluation runner for the Swiss Grounding MCP agent.

Two execution modes, selected with GALTEA_EVAL_MODE (default: "backend"):

- "backend" (default): the Galtea agent callable forwards the full chat
  history to the running agent-backend (`POST /api/chat`, SSE) on
  GALTEA_AGENT_BACKEND_URL (default http://127.0.0.1:3001). This exercises
  the real production path -- OpenAI tool-calling, the 9-tool dispatcher,
  widget mapping -- including multi-turn disambiguation. Start the backend
  first (`npm run dev:api` from the repo root).
- "local": in-process ToolBox + deterministic intent router from
  voice_assistant.py. Useful when the backend/OpenAI is unavailable, but it
  is single-turn only and does not reflect the shipped pipeline.

Usage (from server/):
    ./.venv/Scripts/python galtea_eval.py

Requires GALTEA_API_KEY in .env or .env.local; backend mode also needs
OPENAI_API_KEY configured for the agent-backend.
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)

from galtea import Galtea

PRODUCT_ID = "product_wcky92rnoaxozh51twl2jja5"
# Iteration versions keep results comparable across improvement loops;
# override with GALTEA_VERSION_ID to evaluate a different one.
VERSION_ID = os.environ.get(
    "GALTEA_VERSION_ID", "version_defum1qn271mzz4gggjbw6ug"
).strip()

BACKEND_URL = os.environ.get("GALTEA_AGENT_BACKEND_URL", "http://127.0.0.1:3001").rstrip("/")
EVAL_MODE = os.environ.get("GALTEA_EVAL_MODE", "backend").strip().lower()
# Optional: restrict a run to specific specifications (comma-separated ids),
# e.g. to iterate quickly on a single spec instead of the whole version.
SPEC_IDS = [s.strip() for s in os.environ.get("GALTEA_SPEC_IDS", "").split(",") if s.strip()] or None

_LOCAL_TOOLS = None


def _local_toolbox():
    """Lazy in-process ToolBox so backend mode never pays the import cost."""
    global _LOCAL_TOOLS
    if _LOCAL_TOOLS is None:
        from swiss_grounding_mcp.config.settings import Settings
        from voice_assistant import ToolBox

        _LOCAL_TOOLS = ToolBox(Settings.from_env())
    return _LOCAL_TOOLS


def _agent_backend(messages: list[dict]) -> str:
    """Drive the real agent-backend SSE pipeline; return the tool contract.

    The returned JSON is the last tool result's payload verbatim (status,
    message, connections/candidates, provenance{source, retrieved_at,...})
    -- exactly the structured contract the product documents and the
    frontend renders. Prose-only turns emit {status: answered, message}.
    """
    reply_parts: list[str] = []
    tool_results: list[dict] = []
    with httpx.stream(
        "POST",
        f"{BACKEND_URL}/api/chat",
        json={"messages": messages},
        timeout=httpx.Timeout(180.0, connect=10.0),
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: "):])
            if event.get("type") == "token":
                reply_parts.append(event.get("text") or "")
            elif event.get("type") == "widget":
                tool_results.append(
                    {
                        "tool": event.get("tool"),
                        "status": event.get("status"),
                        "data": event.get("data"),
                    }
                )
    reply = "".join(reply_parts)
    if tool_results:
        last_data = tool_results[-1].get("data")
        if isinstance(last_data, dict):
            # Emit exactly the tool-result contract (status, message,
            # connections/candidates, provenance{source, retrieved_at,...})
            # the product documents -- the same payload the frontend renders.
            payload = dict(last_data)
            if not payload.get("message") and reply:
                payload["message"] = reply
            if len(tool_results) > 1:
                payload["additional_results"] = [
                    t.get("data") for t in tool_results[:-1]
                ]
            return json.dumps(payload)
    # Prose-only turn (no tool call): keep the {status, message} contract.
    return json.dumps({"status": "answered", "message": reply})


def _agent_local(user_message: str) -> str:
    """Legacy path: regex router + ToolBox in-process (single-turn)."""
    from voice_assistant import route_intent

    name, result = route_intent(user_message, _local_toolbox())
    if name == "clarify":
        return json.dumps({"status": "needs_clarification", "message": result})
    return result.model_dump_json()


def agent(messages: list[dict]) -> str:
    """Galtea agent entry point.

    First parameter annotated `list[dict]` -> the SDK passes the whole chat
    history each turn, which is what the multi-turn scenario datasets need
    for disambiguation follow-ups. NOTE: do not enable
    `from __future__ import annotations` here -- the SDK inspects the raw
    annotation object, and PEP 563 would turn it into a string, silently
    reverting the input shape detection.
    """
    if EVAL_MODE == "local":
        latest = next((m for m in reversed(messages) if m.get("role") == "user"), {})
        return _agent_local(str(latest.get("content", "")))
    return _agent_backend(messages)


def _preflight_backend() -> str | None:
    """Return an error string when the backend cannot serve evaluations."""
    try:
        health = httpx.get(f"{BACKEND_URL}/api/health", timeout=5.0).json()
    except Exception as exc:  # noqa: BLE001 - report any connectivity failure
        return (
            f"agent-backend unreachable at {BACKEND_URL} ({exc}). "
            "Start it with `npm run dev:api` from the repo root, or run with "
            "GALTEA_EVAL_MODE=local for the in-process pipeline."
        )
    if not health.get("openai_configured"):
        return (
            f"agent-backend at {BACKEND_URL} reports openai_configured=false. "
            "Set OPENAI_API_KEY in server/.env and restart the backend."
        )
    return None


def main() -> int:
    key = os.environ.get("GALTEA_API_KEY", "").strip()
    if not key:
        print("GALTEA_API_KEY missing in .env / .env.local")
        return 1

    if EVAL_MODE == "backend":
        problem = _preflight_backend()
        if problem:
            print(problem)
            return 2
        print(f"agent-backend healthy at {BACKEND_URL} (openai_configured=true)")

    galtea = Galtea(api_key=key)

    print(
        f"Running evaluations for version {VERSION_ID} (mode={EVAL_MODE}"
        f"{', specs=' + ','.join(SPEC_IDS) if SPEC_IDS else ''}) ...",
        flush=True,
    )
    run = galtea.evaluations.run(version_id=VERSION_ID, agent=agent, specification_ids=SPEC_IDS)
    run_evals = run.get("evaluations") if isinstance(run, dict) else None
    print(f"run returned {len(run_evals or [])} evaluations", flush=True)
    run_id = None
    if isinstance(run, dict):
        run_id = run.get("id") or run.get("run_id")
        if not run_id and run_evals:
            run_id = getattr(run_evals[0], "run_id", None)

    # Poll until every evaluation of THIS run reaches a terminal state.
    # The SDK returns EvaluationStatus enums whose str() is
    # "EvaluationStatus.SUCCESS" -- normalize via .value before comparing.
    def _status(e) -> str:
        s = getattr(e, "status", "?")
        return str(getattr(s, "value", s))

    terminal = {"SUCCESS", "FAILED", "SKIPPED", "CANCELLED", "OUTDATED", "PENDING_HUMAN"}
    deadline = time.time() + 30 * 60
    items = []
    while time.time() < deadline:
        try:
            evals = galtea.evaluations.list(version_id=VERSION_ID)
            all_items = getattr(evals, "items", None) or getattr(evals, "data", None) or list(evals)
            items = [e for e in all_items if not run_id or getattr(e, "run_id", None) == run_id]
        except Exception as exc:  # noqa: BLE001 - transient API errors must not kill the poll
            print(f"[poll] list failed: {exc}", flush=True)
            time.sleep(20)
            continue
        states = {_status(e) for e in items}
        print(f"[poll] {len(items)} evaluations in run, statuses: {states}", flush=True)
        if items and states <= terminal:
            break
        time.sleep(20)

    print("\nResults:")
    passed = failed = skipped = 0
    failures: list[str] = []
    for e in items:
        status = _status(e)
        score = getattr(e, "score", None)
        metric = getattr(getattr(e, "metric", None), "name", None) or getattr(e, "metric_id", "?")
        reason = getattr(e, "reason", None) or getattr(e, "error", None) or ""
        print(f"  {status:10} score={score}  metric={metric}  id={getattr(e, 'id', '?')}")
        if status == "SUCCESS":
            passed += 1
        elif status == "SKIPPED":
            skipped += 1
        else:
            failed += 1
            failures.append(f"    - {metric}: {reason}")

    total = len(items)
    print(f"\nSummary: {passed}/{total} SUCCESS, {failed} failed, {skipped} skipped")
    if failures:
        print("Failures:")
        print("\n".join(failures))
    print("\nView on the Galtea platform: https://platform.galtea.ai "
          f"(product {PRODUCT_ID}, version {VERSION_ID}, run {run_id})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
