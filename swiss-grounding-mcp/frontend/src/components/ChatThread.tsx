import type { Turn } from "../App";
import { AssistantTurn } from "./AssistantTurn";

interface ChatThreadProps {
  turns: Turn[];
  onClarify: (value: string) => void;
}

export function ChatThread({ turns, onClarify }: ChatThreadProps) {
  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 py-8">
      {turns.map((turn) =>
        turn.role === "user" ? (
          <p key={turn.id} className="ml-auto w-fit rounded-2xl bg-accent px-4 py-2 text-white">
            {turn.text}
          </p>
        ) : (
          <AssistantTurn key={turn.id} turn={turn} onClarify={onClarify} />
        )
      )}
    </div>
  );
}
