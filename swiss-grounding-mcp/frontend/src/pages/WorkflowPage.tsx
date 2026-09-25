import { useMemo } from "react";
import { Background, BackgroundVariant, Controls, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useRun } from "../workflow/runContext";
import { ExecutionNode } from "../workflow/ExecutionNode";
import { toFlowElements } from "../workflow/toFlowElements";
import "../styles/workflow.css";

const nodeTypes = { execution: ExecutionNode };

export function WorkflowPage({ onGoHome }: { onGoHome: () => void }) {
  const { state } = useRun();
  const elements = useMemo(() => toFlowElements(state), [state]);
  if (!state.runId) {
    return <section className="workflow-page workflow-empty">
      <h1>Your workflow will appear here</h1>
      <p>Start a travel request from Home to follow each grounded step as it happens.</p>
      <button type="button" onClick={onGoHome}>Go to Home</button>
    </section>;
  }
  return <section className="workflow-page">
    <header className="workflow-header">
      <div><h1>Current execution</h1><p>Frontend-initiated run · {state.runId.slice(0, 8)}</p></div>
      <span className="workflow-status" data-status={state.status}>{state.status === "waiting_for_input" ? "Needs input" : state.status}</span>
    </header>
    {state.connectionStatus === "interrupted" && <p className="connection-alert">Connection interrupted. The workflow may still be running.</p>}
    <div className="workflow-canvas" aria-label="Current execution workflow">
      <ReactFlow
        nodes={elements.nodes}
        edges={elements.edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        fitView
        minZoom={0.45}
        maxZoom={1.4}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#dfe7e1" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
    <div className="sr-only" aria-live="polite">Workflow status: {state.status}</div>
  </section>;
}
