import { fireEvent, render, screen } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import { describe, expect, it } from "vitest";
import { ExecutionNode } from "./ExecutionNode";


describe("ExecutionNode", () => {
  it("shows status text and expands safe operation details", () => {
    const props = { data: {
      id: "tool-1",
      label: "Check connections",
      summary: "Searching Swiss data",
      status: "running",
      tool: "find_connections",
      details: { origin: "Bern" },
    }} as unknown as Parameters<typeof ExecutionNode>[0];
    render(<ReactFlowProvider><ExecutionNode {...props} /></ReactFlowProvider>);
    expect(screen.getByText("Running")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: /find connections/i });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Bern")).toBeInTheDocument();
  });
});
