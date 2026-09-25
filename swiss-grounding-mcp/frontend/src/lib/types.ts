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

export function isExecutionEvent(event: AgentEvent): event is ExecutionEvent {
  return ["run_started", "node_started", "node_completed", "node_skipped", "node_failed", "tool_started", "tool_completed", "tool_failed", "run_waiting", "run_completed"].includes(event.type);
}
