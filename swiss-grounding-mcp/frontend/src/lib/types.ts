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

export type AgentEvent = TokenEvent | WidgetEvent | DoneEvent;
