import type { Turn } from "../App";
import { AssistantTurn } from "./AssistantTurn";

interface ChatThreadProps {
  turns: Turn[];
  pendingTurnId: string | null;
  onClarify: (value: string) => void;
}

export function ChatThread({ turns, pendingTurnId, onClarify }: ChatThreadProps) {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-8">
      {turns.map((turn) =>
        turn.role === "user" ? (
          <p
            key={turn.id}
            className="ml-auto w-fit max-w-[80%] animate-rise rounded-full border border-white/40 bg-accent/90 px-5 py-2.5 text-white shadow-glass-sm backdrop-blur-md"
          >
            {turn.text}
          </p>
        ) : (
          <AssistantTurn
            key={turn.id}
            turn={turn}
            isPending={turn.id === pendingTurnId}
            onClarify={onClarify}
          />
        )
      )}
    </div>
  );
}
