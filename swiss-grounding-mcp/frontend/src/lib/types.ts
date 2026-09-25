export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface TokenEvent {
  type: "token";
  text: string;
}

export interface WidgetEvent {
  type: "widget";
  tool: string | null;
  status: string;
  data: Record<string, unknown>;
}

export interface DoneEvent {
  type: "done";
}

export type ExecutionEventType =
  | "run_started"
  | "node_started"
  | "node_completed"
  | "node_skipped"
  | "node_failed"
  | "tool_started"
  | "tool_completed"
  | "tool_failed"
  | "run_waiting"
  | "run_completed";

export type ExecutionStatus = "pending" | "running" | "completed" | "waiting_for_input" | "failed" | "skipped";

export interface ExecutionEvent {
  type: ExecutionEventType;
  run_id: string;
  sequence: number;
  timestamp: string;
  node_id: string;
  label: string;
  status: ExecutionStatus;
  summary: string;
  tool?: string;
  source?: string;
  duration_ms?: number;
  details?: Record<string, string | number | boolean | null>;
  outcome?: "completed" | "waiting" | "failed" | "incomplete";
  error?: string;
}

export type AgentEvent = TokenEvent | WidgetEvent | DoneEvent | ExecutionEvent;

const EXECUTION_EVENT_TYPES: ExecutionEventType[] = ["run_started", "node_started", "node_completed", "node_skipped", "node_failed", "tool_started", "tool_completed", "tool_failed", "run_waiting", "run_completed"];
const EXECUTION_STATUSES: ExecutionStatus[] = ["pending", "running", "completed", "waiting_for_input", "failed", "skipped"];

export function isExecutionEvent(event: unknown): event is ExecutionEvent {
  if (!event || typeof event !== "object") return false;
  const candidate = event as Partial<ExecutionEvent>;
  return typeof candidate.type === "string"
    && EXECUTION_EVENT_TYPES.includes(candidate.type as ExecutionEventType)
    && typeof candidate.run_id === "string"
    && typeof candidate.sequence === "number"
    && typeof candidate.node_id === "string"
    && typeof candidate.label === "string"
    && typeof candidate.summary === "string"
    && typeof candidate.status === "string"
    && EXECUTION_STATUSES.includes(candidate.status as ExecutionStatus);
}
