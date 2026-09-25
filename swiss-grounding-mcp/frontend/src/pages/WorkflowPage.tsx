import { useMemo, useState } from "react";
import { Background, BackgroundVariant, Controls, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useRun } from "../workflow/runContext";
import { ExecutionNode } from "../workflow/ExecutionNode";
import { toFlowElements } from "../workflow/toFlowElements";
import { ArrowLeftIcon } from "../workflow/icons";
import "../styles/workflow.css";

const nodeTypes = { execution: ExecutionNode };

export function WorkflowPage({ onGoHome }: { onGoHome: () => void }) {
  const { state } = useRun();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const elements = useMemo(() => {
    const projected = toFlowElements(state);
    return { ...projected, nodes: projected.nodes.map((node) => ({ ...node, selected: node.id === selectedNodeId })) };
  }, [state, selectedNodeId]);
  const durationLabel = state.durationMs === undefined ? "Live" : state.durationMs < 1000 ? `${state.durationMs} ms` : `${(state.durationMs / 1000).toFixed(1)} s`;
  if (!state.runId) {
    return <section className="workflow-page workflow-empty">
      <h1>Your workflow will appear here</h1>
      <p>Start a travel request from Home to follow each grounded step as it happens.</p>
      <button type="button" onClick={onGoHome}>Go to Home</button>
    </section>;
  }
  const statusLabel = state.status === "waiting_for_input" ? "Needs input" : state.status;
  return <section className="workflow-page">
    <header className="workflow-header">
      <div className="workflow-header__top">
        <button type="button" className="back-home" onClick={onGoHome}>
          <ArrowLeftIcon className="back-home__icon" />Back to Home
        </button>
        <span className="workflow-status" data-status={state.status}>
          <i className="status-dot" aria-hidden />{statusLabel}
        </span>
      </div>
      <div className="workflow-header__titles">
        <h1>{state.requestSummary || "Current execution"}</h1>
        <p>Run {state.runId.slice(0, 8)} · {durationLabel}</p>
      </div>
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
        deleteKeyCode={null}
        onNodeClick={(_, node) => setSelectedNodeId(node.id)}
        defaultViewport={{ x: 36, y: 24, zoom: 1 }}
        minZoom={0.65}
        maxZoom={1.4}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#dfe7e1" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
    <div className="sr-only" aria-live="polite">Workflow status: {state.status}</div>
  </section>;
}
