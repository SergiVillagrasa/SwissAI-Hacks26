import { fireEvent, render, screen } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import { describe, expect, it } from "vitest";
import { ExecutionNode } from "./ExecutionNode";

function renderNode(data: unknown) {
  const props = { data } as unknown as Parameters<typeof ExecutionNode>[0];
  return render(<ReactFlowProvider><ExecutionNode {...props} /></ReactFlowProvider>);
}

describe("ExecutionNode", () => {
  it("shows the round label and an operation row per tool call, expandable to safe details", () => {
    renderNode({
      id: "model-1",
      label: "Understand request",
      summary: "Interpreting your request",
      status: "completed",
      children: [
        {
          id: "tool-1-1",
          label: "Find Connections",
          summary: "",
          status: "completed",
          tool: "find_connections",
          details: { origin: "Bern" },
          durationMs: 420,
        },
      ],
    });

    expect(screen.getByText("Understand request")).toBeInTheDocument();
    const trigger = screen.getByRole("button", { name: /find connections/i });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Bern")).toBeInTheDocument();
  });

  it("renders only the round card when there are no operations", () => {
    renderNode({
      id: "model-2",
      label: "Response prepared",
      summary: "Your answer is ready",
      status: "completed",
      children: [],
    });

    expect(screen.getByText("Response prepared")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
