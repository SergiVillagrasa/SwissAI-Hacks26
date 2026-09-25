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
});
