import { describe, expect, it } from "vitest";
import type { ExecutionEvent } from "../lib/types";
import { emptyRunState, markRunDisconnected, runReducer } from "./runState";

function event(overrides: Partial<ExecutionEvent>): ExecutionEvent {
  return {
    type: "node_started",
    run_id: "r1",
    sequence: 1,
    timestamp: "2026-09-25T10:00:00Z",
    node_id: "node-1",
    label: "Understand request",
    status: "running",
    summary: "Interpreting your request",
    ...overrides,
  } as ExecutionEvent;
}

describe("runReducer", () => {
  it("accepts ordered events and ignores stale sequence numbers", () => {
    const started = event({ type: "run_started", node_id: "run", sequence: 1 });
    const running = event({ node_id: "tool-1", sequence: 2 });
    const stale = event({ type: "node_completed", node_id: "tool-1", sequence: 1, status: "completed" });

    const state = runReducer(runReducer(runReducer(emptyRunState, started), running), stale);

    expect(state.nodes["tool-1"].status).toBe("running");
    expect(state.lastSequence).toBe(2);
  });

  it("replaces the previous run when a new run starts", () => {
    const first = runReducer(emptyRunState, event({ type: "run_started", run_id: "r1", node_id: "run" }));
    const withNode = runReducer(first, event({ run_id: "r1", sequence: 2, node_id: "old" }));
    const next = runReducer(withNode, event({ type: "run_started", run_id: "r2", node_id: "run", sequence: 1 }));

    expect(next.runId).toBe("r2");
    expect(next.nodes.old).toBeUndefined();
  });

  it("marks only the visualization connection interrupted", () => {
    const running = runReducer(emptyRunState, event({ type: "run_started", node_id: "run" }));
    const disconnected = markRunDisconnected(running);

    expect(disconnected.connectionStatus).toBe("interrupted");
    expect(disconnected.status).toBe("running");
  });
});
