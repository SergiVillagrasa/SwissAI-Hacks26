import { useState } from "react";
import { Composer } from "./components/Composer";
import { ChatThread } from "./components/ChatThread";
import { streamChat } from "./lib/sse";
import type { ChatMessage, WidgetEvent } from "./lib/types";

export interface Turn {
  id: string;
  role: "user" | "assistant";
  text: string;
  widgets: WidgetEvent[];
}

const BACKEND_URL = import.meta.env.VITE_AGENT_BACKEND_URL ?? "http://127.0.0.1:8080";

function makeId(): string {
  return Math.random().toString(36).slice(2);
}

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);

  async function handleSubmit(text: string) {
    const userTurn: Turn = { id: makeId(), role: "user", text, widgets: [] };
    const assistantTurn: Turn = { id: makeId(), role: "assistant", text: "", widgets: [] };
    const nextHistory: ChatMessage[] = [...history, { role: "user", content: text }];

    setTurns((current) => [...current, userTurn, assistantTurn]);
    setHistory(nextHistory);
    setPending(true);

    let assistantText = "";
    try {
      for await (const event of streamChat(BACKEND_URL, nextHistory)) {
        if (event.type === "token") {
          assistantText += event.text;
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantTurn.id ? { ...turn, text: assistantText } : turn
            )
          );
        } else if (event.type === "widget") {
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantTurn.id
                ? { ...turn, widgets: [...turn.widgets, event] }
                : turn
            )
          );
        }
      }
      setHistory((current) => [...current, { role: "assistant", content: assistantText }]);
    } catch (error) {
      setTurns((current) =>
        current.map((turn) =>
          turn.id === assistantTurn.id
            ? { ...turn, text: "Something went wrong reaching the assistant. Please try again." }
            : turn
        )
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center">
      {turns.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-8">
          <h1 className="text-3xl font-medium text-neutral-800">Where are you headed?</h1>
          <Composer disabled={pending} onSubmit={handleSubmit} />
        </div>
      ) : (
        <>
          <ChatThread turns={turns} onClarify={handleSubmit} />
          <div className="sticky bottom-0 w-full bg-gradient-to-t from-neutral-50 py-6">
            <div className="flex justify-center">
              <Composer disabled={pending} onSubmit={handleSubmit} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
