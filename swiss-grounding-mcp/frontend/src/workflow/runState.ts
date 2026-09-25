import type { ExecutionEvent, ExecutionStatus } from "../lib/types";

export interface RunNode {
  id: string;
  label: string;
  summary: string;
  status: ExecutionStatus;
  tool?: string;
  details?: Record<string, string | number | boolean | null>;
  durationMs?: number;
}

export interface RunState {
  runId: string | null;
  status: ExecutionStatus | "idle";
  outcome?: ExecutionEvent["outcome"];
  nodes: Record<string, RunNode>;
  nodeOrder: string[];
  lastSequence: number;
  connectionStatus: "connected" | "interrupted";
  requestSummary?: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
}

export const emptyRunState: RunState = {
  runId: null,
  status: "idle",
  nodes: {},
  nodeOrder: [],
  lastSequence: 0,
  connectionStatus: "connected",
};

export type RunAction = ExecutionEvent | { type: "connection_interrupted" };

export function runReducer(state: RunState, event: RunAction): RunState {
  if (event.type === "connection_interrupted") return markRunDisconnected(state);
  if (event.type === "run_started") {
    if (state.runId === event.run_id && event.sequence <= state.lastSequence) return state;
    return {
      ...emptyRunState,
      runId: event.run_id,
      status: "running",
      lastSequence: event.sequence,
      requestSummary: typeof event.details?.request === "string" ? event.details.request : undefined,
      startedAt: event.timestamp,
      nodes: {},
      nodeOrder: [],
    };
  }
  if (!state.runId || event.run_id !== state.runId || event.sequence <= state.lastSequence) return state;
  if (event.type === "run_completed") {
    const started = state.startedAt ? Date.parse(state.startedAt) : Number.NaN;
    const completed = Date.parse(event.timestamp);
    return {
      ...state,
      status: event.status,
      outcome: event.outcome,
      lastSequence: event.sequence,
      completedAt: event.timestamp,
      durationMs: Number.isFinite(started) && Number.isFinite(completed) ? Math.max(0, completed - started) : undefined,
    };
  }
  if (event.type === "run_waiting") {
    return { ...state, status: "waiting_for_input", lastSequence: event.sequence };
  }

  const exists = Boolean(state.nodes[event.node_id]);
  return {
    ...state,
    lastSequence: event.sequence,
    nodes: {
      ...state.nodes,
      [event.node_id]: {
        ...state.nodes[event.node_id],
        id: event.node_id,
        label: event.label,
        summary: event.summary,
        status: event.status,
        tool: event.tool ?? state.nodes[event.node_id]?.tool,
        details: event.details ?? state.nodes[event.node_id]?.details,
        durationMs: event.duration_ms ?? state.nodes[event.node_id]?.durationMs,
      },
    },
    nodeOrder: exists ? state.nodeOrder : [...state.nodeOrder, event.node_id],
  };
}

export function markRunDisconnected(state: RunState): RunState {
  if (!state.runId) return state;
  return { ...state, connectionStatus: "interrupted" };
}
