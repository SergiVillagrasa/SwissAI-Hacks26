import type { Turn } from "../App";

interface AssistantTurnProps {
  turn: Turn;
  onClarify: (value: string) => void;
}

export function AssistantTurn({ turn }: AssistantTurnProps) {
  return (
    <div className="space-y-3">
      {turn.text && <p className="text-neutral-700">{turn.text}</p>}
      {turn.widgets.map((widget, index) => (
        <div
          key={index}
          data-testid={`widget-${widget.tool ?? "unknown"}`}
          className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm"
        >
          <pre className="whitespace-pre-wrap text-xs text-neutral-500">
            {JSON.stringify(widget, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}
