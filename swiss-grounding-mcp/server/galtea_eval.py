"""Galtea evaluation runner for the Swiss Grounding MCP agent.

Wraps the in-process tool surface (ToolBox + intent router + answer renderer
from voice_assistant.py) as a Galtea `agent` callable, then runs the
specification-driven evaluations linked to the configured product version
and polls every evaluation to a terminal status.

Usage (from server/):
    ./.venv/Scripts/python galtea_eval.py

Requires GALTEA_API_KEY in .env or .env.local.
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)

from galtea import Galtea

from swiss_grounding_mcp.config.settings import Settings
from voice_assistant import ToolBox, route_intent

VERSION_ID = "version_defum1qn271mzz4gggjbw6ug"
PRODUCT_ID = "product_wcky92rnoaxozh51twl2jja5"

_tools = ToolBox(Settings.from_env())


def agent(user_message: str) -> str:
    """Galtea agent entry point.

    First parameter annotated `str` -> the SDK passes the latest user
    message. Returns a plain-text, source-cited answer.
    NOTE: do not enable `from __future__ import annotations` here — the
    SDK inspects the raw annotation object, and PEP 563 would turn `str`
    into the string 'str', silently reverting to list[dict] input.
    """
    name, result = route_intent(user_message, _tools)
    if name == "clarify":
        return json.dumps({"status": "needs_clarification", "message": result})
    return result.model_dump_json()


def main() -> int:
    key = os.environ.get("GALTEA_API_KEY", "").strip()
    if not key:
        print("GALTEA_API_KEY missing in .env / .env.local")
        return 1

    galtea = Galtea(api_key=key)

    print(f"Running evaluations for version {VERSION_ID} ...", flush=True)
    run = galtea.evaluations.run(version_id=VERSION_ID, agent=agent)
    print(f"run returned: {run}", flush=True)
    run_id = (run.get("id") or run.get("run_id")) if isinstance(run, dict) else None

    # Poll until every evaluation reaches a terminal state.
    terminal = {"SUCCESS", "FAILED", "SKIPPED"}
    deadline = time.time() + 15 * 60
    items = []
    while time.time() < deadline:
        try:
            evals = galtea.evaluations.list(version_id=VERSION_ID)
            items = getattr(evals, "items", None) or getattr(evals, "data", None) or list(evals)
        except Exception as exc:  # noqa: BLE001 - transient API errors must not kill the poll
            print(f"[poll] list failed: {exc}", flush=True)
            time.sleep(20)
            continue
        states = {getattr(e, "status", "?") for e in items}
        print(f"[poll] {len(items)} evaluations, statuses: {states}", flush=True)
        if items and states <= terminal:
            break
        time.sleep(20)

    print("\nResults:")
    worst = 0
    for e in items:
        status = getattr(e, "status", "?")
        score = getattr(e, "score", None)
        metric = getattr(getattr(e, "metric", None), "name", None) or getattr(e, "metric_id", "?")
        print(f"  {status:10} score={score}  metric={metric}  id={getattr(e, 'id', '?')}")
        if status != "SUCCESS":
            worst = 1
    print("\nView on the Galtea platform: https://platform.galtea.ai "
          f"(product {PRODUCT_ID}, version {VERSION_ID}, run {run_id})")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
