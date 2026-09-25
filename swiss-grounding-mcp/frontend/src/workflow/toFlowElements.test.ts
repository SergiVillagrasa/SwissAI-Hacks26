import { describe, expect, it } from "vitest";
import { emptyRunState, type RunState } from "./runState";
import { toFlowElements } from "./toFlowElements";


describe("toFlowElements", () => {
  it("projects ordered nodes into a horizontal non-overlapping flow", () => {
    const state: RunState = {
      ...emptyRunState,
      runId: "run-1",
      status: "running",
      nodeOrder: ["one", "two"],
      nodes: {
        one: { id: "one", label: "Understand request", summary: "Done", status: "completed" },
        two: { id: "two", label: "Check connections", summary: "Running", status: "running", tool: "find_connections" },
      },
    };

    const result = toFlowElements(state);

    expect(result.nodes.map((node) => node.id)).toEqual(["one", "two"]);
    expect(result.nodes[1].position.x).toBeGreaterThan(result.nodes[0].position.x);
    expect(result.edges).toHaveLength(1);
    expect(result.edges[0].type).toBe("smoothstep");
  });

  it("groups tool and skip nodes under their originating model round", () => {
    const state: RunState = {
      ...emptyRunState,
      runId: "run-1",
      status: "completed",
      nodeOrder: ["model-1", "tool-1-1", "tool-1-2", "model-2", "invoke-tool-2", "verify-result-2"],
      nodes: {
        "model-1": { id: "model-1", label: "Understand request", summary: "Interpreting", status: "completed" },
        "tool-1-1": { id: "tool-1-1", label: "Find Connections", summary: "", status: "completed", tool: "find_connections" },
        "tool-1-2": { id: "tool-1-2", label: "Find Connections", summary: "", status: "completed", tool: "find_connections" },
        "model-2": { id: "model-2", label: "Response prepared", summary: "Your answer is ready", status: "completed" },
        "invoke-tool-2": { id: "invoke-tool-2", label: "Invoke Swiss tool", summary: "Not needed", status: "skipped" },
        "verify-result-2": { id: "verify-result-2", label: "Verify result", summary: "Not needed", status: "skipped" },
      },
    };

    const result = toFlowElements(state);

    expect(result.nodes.map((node) => node.id)).toEqual(["model-1", "model-2"]);
    expect(result.nodes[0].data.children).toHaveLength(2);
    expect(result.nodes[1].data.children).toHaveLength(2);
    expect(result.edges).toEqual([
      expect.objectContaining({ source: "model-1", target: "model-2" }),
    ]);
  });
});
