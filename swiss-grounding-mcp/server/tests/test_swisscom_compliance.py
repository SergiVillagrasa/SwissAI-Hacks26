"""Live compliance stress-test against the Swisscom evaluation criteria.

Runs the `find_connections` tool against the real OJP 2.0 API and prints a
structured diagnostic report covering grounding quality, scope enforcement,
agent efficiency, operability, and missing-context handling.

Usage (always runs live):
    .venv/Scripts/python tests/test_swisscom_compliance.py

Under pytest these tests are skipped unless SWISSCOM_LIVE_EVAL=1 is set, so
the standard offline suite stays hermetic:
    SWISSCOM_LIVE_EVAL=1 pytest tests/test_swisscom_compliance.py
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import ConnectionSearchResult
from swiss_grounding_mcp.sources.ojp.client import OjpClient
from swiss_grounding_mcp.tools.find_connections import find_train_connections

LIVE = os.getenv("SWISSCOM_LIVE_EVAL") == "1"
pytestmark = pytest.mark.skipif(
    not LIVE, reason="live OJP eval; set SWISSCOM_LIVE_EVAL=1 to run under pytest"
)

LATENCY_WARN_MS = 10_000  # 3 sequential HTTP calls; >10s is sluggish
SIZE_WARN_CHARS = 8_000  # ~2k tokens; larger responses bloat agent context


@dataclass
class ScenarioResult:
    name: str
    query: str
    expected: str
    actual: str
    verdict: str  # PASS / WARN / FAIL
    notes: str


def _call(origin: str, destination: str, results: int = 3) -> ConnectionSearchResult:
    settings = Settings.from_env()
    return find_train_connections(
        origin,
        destination,
        None,
        None,
        results,
        client=OjpClient(settings),
        settings=settings,
    )


def _timed_call(origin: str, destination: str, results: int) -> tuple[ConnectionSearchResult, float]:
    start = time.perf_counter()
    result = _call(origin, destination, results)
    return result, (time.perf_counter() - start) * 1000


def scenario_a() -> ScenarioResult:
    """Valid domestic trip: Bern -> Zürich HB, results=2."""
    result, ms = _timed_call("Bern", "Zürich HB", 2)
    problems = []
    if result.status != "ok":
        problems.append(f"status={result.status}")
    if len(result.connections) > 2:
        problems.append(f"{len(result.connections)} connections > requested 2 (no truncation)")
    for c in result.connections:
        if not c.duration_minutes or not c.legs:
            problems.append("connection missing duration/legs")
            break
    if not (result.provenance and "opentransportdata.swiss" in result.provenance.source_url):
        problems.append("provenance missing authoritative source URL")
    notes = "; ".join(problems) if problems else f"authoritative citation present, {ms:.0f} ms"
    return ScenarioResult(
        "A: Valid domestic trip",
        "Bern -> Zürich HB (results=2)",
        "ok, <=2 connections, cited",
        f"{result.status}, {len(result.connections)} conn",
        "PASS" if not problems else "FAIL",
        notes,
    )


def scenario_b() -> ScenarioResult:
    """Missing context: empty origin and empty destination."""
    r1 = _call("", "Zürich HB")
    r2 = _call("Bern", "")
    ok = r1.status == "needs_clarification" and r2.status == "needs_clarification"
    return ScenarioResult(
        "B: Missing context",
        "'' -> Zürich HB / Bern -> ''",
        "needs_clarification",
        f"{r1.status} / {r2.status}",
        "PASS" if ok else "FAIL",
        "both empty-field cases ask for input without guessing" if ok else "did not ask for clarification",
    )


def scenario_c() -> ScenarioResult:
    """Ambiguous station: 'Bellevue'."""
    result = _call("Bellevue", "Bern")
    if result.status == "needs_clarification" and result.candidates:
        verdict, notes = "PASS", f"{len(result.candidates)} candidates offered"
    elif result.status == "ok":
        verdict, notes = "WARN", "auto-resolved via dominant match; no clarification asked"
    else:
        verdict, notes = "FAIL", f"unexpected status; message: {result.message}"
    return ScenarioResult(
        "C: Ambiguous station",
        "Bellevue -> Bern",
        "needs_clarification + candidates",
        result.status,
        verdict,
        notes,
    )


def scenario_d() -> ScenarioResult:
    """Out-of-scope foreign trips: expect honest non-ok handling."""
    r1 = _call("Paris Gare de Lyon", "Marseille")
    r2 = _call("Berlin Hbf", "Hamburg Hbf")
    honest = {"out_of_scope", "not_found", "needs_clarification"}
    ok = r1.status in honest and r2.status in honest
    notes = []
    if r1.status == "ok":
        notes.append(f"Paris->Marseille answered with {len(r1.connections)} conn (scope leak)")
    if r2.status == "ok":
        notes.append(f"Berlin->Hamburg answered with {len(r2.connections)} conn (scope leak)")
    if not notes:
        notes.append("foreign trips refused honestly")
    return ScenarioResult(
        "D: Purely foreign trips",
        "Paris->Marseille / Berlin->Hamburg",
        "out_of_scope / not_found / clarify",
        f"{r1.status} / {r2.status}",
        "PASS" if ok else "FAIL",
        "; ".join(notes),
    )


def scenario_f() -> ScenarioResult:
    """Cross-border trips touching Switzerland must be allowed."""
    r1 = _call("Paris Gare de Lyon", "Genève")
    r2 = _call("Basel SBB", "Frankfurt(Main)Hbf")
    ok = r1.status == "ok" and r2.status == "ok"
    notes = (
        f"inbound {len(r1.connections)} conn, outbound {len(r2.connections)} conn"
        if ok
        else f"inbound msg: {r1.message} | outbound msg: {r2.message}"
    )
    return ScenarioResult(
        "F: Cross-border trips",
        "Paris->Genève / Basel->Frankfurt",
        "ok / ok (one Swiss end)",
        f"{r1.status} / {r2.status}",
        "PASS" if ok else "FAIL",
        notes,
    )


def scenario_e() -> ScenarioResult:
    """Latency & response size for a standard 2-connection request."""
    result, ms = _timed_call("Bern", "Zürich HB", 2)
    size = len(result.model_dump_json())
    verdict = "PASS" if ms < LATENCY_WARN_MS and size < SIZE_WARN_CHARS else "WARN"
    return ScenarioResult(
        "E: Latency & size",
        "Bern -> Zürich HB (results=2)",
        f"<{LATENCY_WARN_MS} ms, <{SIZE_WARN_CHARS} chars",
        f"{ms:.0f} ms, {size} chars (~{size // 4} tokens)",
        verdict,
        "3 sequential OJP calls per tool invocation" + ("; oversized payload" if size >= SIZE_WARN_CHARS else ""),
    )


SCENARIOS = [
    scenario_a,
    scenario_b,
    scenario_c,
    scenario_d,
    scenario_e,
    scenario_f,
]


def run_report() -> list[ScenarioResult]:
    rows = []
    for fn in SCENARIOS:
        try:
            rows.append(fn())
        except Exception as exc:  # noqa: BLE001 - diagnostic must survive crashes
            rows.append(
                ScenarioResult(fn.__name__, "-", "no crash", type(exc).__name__, "FAIL", str(exc))
            )
    return rows


def _print_table(rows: list[ScenarioResult]) -> None:
    headers = ["Scenario", "Query", "Expected", "Actual", "Verdict", "Notes / Gaps"]
    data = [[r.name, r.query, r.expected, r.actual, r.verdict, r.notes] for r in rows]
    widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], min(len(str(cell)), 60))
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in widths) + " |"
    sep = "|-" + "-|-".join("-" * w for w in widths) + "-|"
    print(fmt.format(*headers))
    print(sep)
    for row in data:
        print(fmt.format(*[str(c)[:60] for c in row]))


def main() -> int:
    if not os.getenv("OJP_API_TOKEN"):
        print("OJP_API_TOKEN not set - cannot run live evaluation.")
        return 2
    rows = run_report()
    print("\n=== Swisscom Compliance Report (live OJP) ===\n")
    _print_table(rows)
    fails = [r for r in rows if r.verdict == "FAIL"]
    warns = [r for r in rows if r.verdict == "WARN"]
    print(f"\n{sum(1 for r in rows if r.verdict == 'PASS')}/{len(rows)} PASS "
          f"| {len(warns)} WARN | {len(fails)} FAIL")
    return 0 if not fails else 1


# --- pytest entry points (gated by SWISSCOM_LIVE_EVAL=1) ---


def test_scenario_a_valid_domestic_trip():
    r = scenario_a()
    assert r.verdict == "PASS", r.notes


def test_scenario_b_missing_context():
    r = scenario_b()
    assert r.verdict == "PASS", r.notes


def test_scenario_c_ambiguous_station():
    r = scenario_c()
    assert r.verdict in ("PASS", "WARN"), r.notes


def test_scenario_d_foreign_trips_refused():
    r = scenario_d()
    assert r.verdict == "PASS", r.notes


def test_scenario_e_latency_and_size():
    r = scenario_e()
    assert r.verdict in ("PASS", "WARN"), r.notes


def test_scenario_f_cross_border_allowed():
    r = scenario_f()
    assert r.verdict == "PASS", r.notes


if __name__ == "__main__":
    sys.exit(main())
