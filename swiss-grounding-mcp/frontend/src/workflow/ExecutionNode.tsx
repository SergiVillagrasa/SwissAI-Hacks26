import { useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { ExecutionNodeData } from "./toFlowElements";

const STATUS_LABELS = {
  pending: "Waiting",
  running: "Running",
  completed: "Completed",
  waiting_for_input: "Needs input",
  failed: "Failed",
  skipped: "Not needed",
};

export function ExecutionNode({ data }: NodeProps) {
  const node = data as ExecutionNodeData;
  const [expanded, setExpanded] = useState(false);
  const hasDetails = Boolean(node.tool || node.details || node.durationMs);
  return <article className="execution-node" data-status={node.status}>
    <Handle type="target" position={Position.Left} />
    <header>
      <div>
        <strong>{node.label}</strong>
        <p>{node.summary}</p>
      </div>
      <span className="node-status"><i aria-hidden />{STATUS_LABELS[node.status]}</span>
    </header>
    {hasDetails && <button type="button" className="node-operation" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
      <span>{node.tool?.replaceAll("_", " ") ?? "Operation details"}</span>
      <span>{node.durationMs ? `${node.durationMs} ms` : expanded ? "Hide" : "Details"}</span>
    </button>}
    {expanded && <dl className="node-details">
      {node.details && Object.entries(node.details).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value)}</dd></div>)}
    </dl>}
    <Handle type="source" position={Position.Right} />
  </article>;
}
