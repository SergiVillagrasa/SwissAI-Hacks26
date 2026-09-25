import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RunProvider, useRun } from "./RunProvider";

function Probe() {
  const { state, acceptEvent, markDisconnected } = useRun();
  return <>
    <span>{state.runId ?? "none"}</span>
    <span>{state.connectionStatus}</span>
    <button onClick={() => acceptEvent({
      type: "run_started",
      run_id: "run-1",
      sequence: 1,
      timestamp: "2026-09-25T10:00:00Z",
      node_id: "run",
      label: "Workflow started",
      status: "running",
      summary: "Starting",
    })}>start</button>
    <button onClick={markDisconnected}>disconnect</button>
  </>;
}

describe("RunProvider", () => {
  it("shares accepted events and connection state", () => {
    render(<RunProvider><Probe /></RunProvider>);
    fireEvent.click(screen.getByText("start"));
    fireEvent.click(screen.getByText("disconnect"));
    expect(screen.getByText("run-1")).toBeInTheDocument();
    expect(screen.getByText("interrupted")).toBeInTheDocument();
  });
});
