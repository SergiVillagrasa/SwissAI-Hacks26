import { useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { ExecutionNodeData } from "./toFlowElements";
import type { RunNode } from "./runState";
import { AgentIcon, CheckCircleIcon, ChevronDownIcon, DotCircleIcon, MinusCircleIcon, XCircleIcon } from "./icons";

const STATUS_LABELS: Record<RunNode["status"], string> = {
  pending: "Waiting",
  running: "Running",
  completed: "Completed",
  waiting_for_input: "Needs input",
  failed: "Failed",
  skipped: "Not needed",
};

function StatusGlyph({ status }: { status: RunNode["status"] }) {
  if (status === "completed") return <CheckCircleIcon className="status-icon status-icon--ok" />;
  if (status === "failed") return <XCircleIcon className="status-icon status-icon--bad" />;
  if (status === "skipped") return <MinusCircleIcon className="status-icon status-icon--muted" />;
  return (
    <DotCircleIcon className={`status-icon status-icon--pending${status === "running" ? " status-icon--live" : ""}`} />
  );
}

function ChildRow({ child }: { child: RunNode }) {
  const [open, setOpen] = useState(false);
  const hasDetails = Boolean(child.details && Object.keys(child.details).length > 0);
  const kind = child.status === "failed" ? "error" : child.status === "skipped" ? "skipped" : child.tool ? "tool" : "step";
  const meta = child.durationMs ? `${kind} · ${child.durationMs} ms` : kind;

  return (
    <div className="child-row">
      <button
        type="button"
        className="child-row__trigger"
        aria-expanded={hasDetails ? open : undefined}
        disabled={!hasDetails}
        onClick={hasDetails ? () => setOpen((value) => !value) : undefined}
      >
        <StatusGlyph status={child.status} />
        <span className="child-row__label">{child.tool ? child.tool.replaceAll("_", " ") : child.label}</span>
        <span className="child-row__tag">{meta}</span>
        <span className="child-row__pill" data-status={child.status}>{STATUS_LABELS[child.status]}</span>
        {hasDetails && <ChevronDownIcon className={`child-row__chevron${open ? " child-row__chevron--open" : ""}`} />}
      </button>
      {open && hasDetails && (
        <dl className="child-details">
          {Object.entries(child.details!).map(([key, value]) => (
            <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value)}</dd></div>
          ))}
        </dl>
      )}
    </div>
  );
}

export function ExecutionNode({ data }: NodeProps) {
  const node = data as ExecutionNodeData;
  const children = node.children ?? [];

  return (
    <div className="execution-node-wrap">
      <Handle type="target" position={Position.Left} />
      <article className="execution-card" data-status={node.status}>
        <span className="execution-card__glyph"><AgentIcon /></span>
        <div className="execution-card__body">
          <strong>{node.label}</strong>
          <p>{node.summary}</p>
        </div>
        <span className="node-status"><i aria-hidden />{STATUS_LABELS[node.status]}</span>
      </article>
      {children.length > 0 && (
        <div className="execution-children">
          {children.map((child) => <ChildRow key={child.id} child={child} />)}
        </div>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
