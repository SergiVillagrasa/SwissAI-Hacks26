import { useEffect, useRef, useState } from "react";
import { Composer } from "./components/Composer";
import { ChatThread } from "./components/ChatThread";
import { VoiceBorderGlow } from "./components/VoiceBorderGlow";
import { GlassTile } from "./components/GlassTile";
import { AppShell } from "./components/AppShell";
import { useVoiceAgent } from "./lib/useVoiceAgent";
import { streamChat } from "./lib/sse";
import { isExecutionEvent, type ChatMessage, type WidgetEvent } from "./lib/types";
import { usePage } from "./navigation/usePage";
import { RunProvider, useRun } from "./workflow/RunProvider";

export interface Turn {
  id: string;
  role: "user" | "assistant";
  text: string;
  widgets: WidgetEvent[];
}

const BACKEND_URL = import.meta.env.VITE_AGENT_BACKEND_URL ?? "http://127.0.0.1:3001";

function makeId(): string {
  return Math.random().toString(36).slice(2);
}

function AppContent() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const { page, navigate } = usePage();
  const { state: runState, acceptEvent, markDisconnected } = useRun();
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [pendingTurnId, setPendingTurnId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node || typeof node.scrollTo !== "function") return;
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [turns]);

  async function handleSubmit(text: string): Promise<string> {
    const userTurn: Turn = { id: makeId(), role: "user", text, widgets: [] };
    const assistantTurn: Turn = { id: makeId(), role: "assistant", text: "", widgets: [] };
    const nextHistory: ChatMessage[] = [...history, { role: "user", content: text }];

    setTurns((current) => [...current, userTurn, assistantTurn]);
    setHistory(nextHistory);
    setPending(true);
    setPendingTurnId(assistantTurn.id);

    let assistantText = "";
    try {
      for await (const event of streamChat(BACKEND_URL, nextHistory)) {
        if (isExecutionEvent(event)) {
          acceptEvent(event);
        } else if (event.type === "token") {
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
      return assistantText;
    } catch (error) {
      markDisconnected();
      const fallback = "Something went wrong reaching the assistant. Please try again.";
      setTurns((current) =>
        current.map((turn) => (turn.id === assistantTurn.id ? { ...turn, text: fallback } : turn))
      );
      return fallback;
    } finally {
      setPending(false);
      setPendingTurnId(null);
    }
  }

  const voice = useVoiceAgent(BACKEND_URL, handleSubmit);
  const voiceActive = voice.state !== "idle";

  function handleMicClick() {
    if (voice.state === "listening") {
      void voice.stopAndSend();
    } else {
      void voice.start();
    }
  }

  const closeVoiceButton = voiceActive ? (
    <button
      type="button"
      aria-label="Close voice mode"
      onClick={voice.cancel}
      className="quiet-focus relative z-50 flex h-11 w-11 items-center justify-center rounded-full bg-white/70 text-neutral-600 shadow-glass-sm backdrop-blur-xl transition hover:bg-white/90"
    >
      <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden>
        <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </button>
  ) : null;

  const voiceErrorBanner =
    voice.state === "error" && voice.errorMessage ? (
      <GlassTile className="max-w-2xl p-4 text-sm text-neutral-700">
        <span className="mr-2 font-medium text-rose-500">Voice error:</span>
        {voice.errorMessage}
      </GlassTile>
    ) : null;

  return (
    <AppShell page={page} onNavigate={navigate}>
      {page === "workflow" ? (
        <section className="workflow-placeholder">
          <h1>Workflow</h1>
          <p>{runState.runId ? "Current execution" : "Start a request from Home to see its workflow."}</p>
        </section>
      ) : <div className="flex h-full flex-col overflow-hidden">
      {voiceActive && <VoiceBorderGlow state={voice.state} level={voice.level} />}
      {turns.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6">
          <h1 className="animate-rise mb-6 text-center text-4xl font-medium tracking-tight text-neutral-800 sm:text-5xl">
            Where are you headed?
          </h1>
          {closeVoiceButton}
          {voiceErrorBanner}
          <Composer
            disabled={pending}
            onSubmit={handleSubmit}
            voiceState={voice.state}
            onMicClick={handleMicClick}
          />
        </div>
      ) : (
        <>
          <div ref={scrollRef} className="flex-1 overflow-y-auto">
            <ChatThread turns={turns} pendingTurnId={pendingTurnId} onClarify={handleSubmit} />
          </div>
          <div className="w-full shrink-0 bg-gradient-to-t from-[#cfe4ff] via-[#cfe4ff]/80 to-transparent px-4 py-6">
            <div className="flex flex-col items-center gap-3">
              {closeVoiceButton}
              {voiceErrorBanner}
              <Composer
                disabled={pending}
                onSubmit={handleSubmit}
                voiceState={voice.state}
                onMicClick={handleMicClick}
              />
            </div>
          </div>
        </>
      )}
      </div>}
    </AppShell>
  );
}

export default function App() {
  return <RunProvider><AppContent /></RunProvider>;
}
