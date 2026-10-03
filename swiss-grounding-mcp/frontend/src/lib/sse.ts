import type { AgentEvent, ChatMessage } from "./types";
import { BackendError, backendHeaders } from "./backend";

export async function* streamChat(
  backendUrl: string,
  messages: ChatMessage[],
  channel?: "text" | "voice"
): AsyncGenerator<AgentEvent> {
  const response = await fetch(`${backendUrl}/api/chat`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(
      channel
        ? { messages: messages.slice(-20), channel }
        : { messages: messages.slice(-20) }
    ),
  });

  if (!response.ok) throw new BackendError(response.status);
  if (!response.body) throw new Error("Agent backend returned no response body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice("data:".length).trim();
      if (!payload) continue;
      try {
        yield JSON.parse(payload) as AgentEvent;
      } catch {
        continue;
      }
    }
  }
}
