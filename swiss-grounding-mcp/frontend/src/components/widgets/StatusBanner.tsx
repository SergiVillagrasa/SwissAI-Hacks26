import { GlassTile } from "../GlassTile";
import { MarkdownText } from "../MarkdownText";

interface StopCandidate {
  name: string;
  stop_ref: string;
  probability: number | null;
}

export function StatusBanner({
  status,
  message,
  candidates,
  onClarify,
}: {
  status: string;
  message: string | null;
  candidates: StopCandidate[];
  onClarify: (value: string) => void;
}) {
  return (
    <GlassTile className="p-4 text-sm text-neutral-700">
      <MarkdownText>{message ?? "This could not be answered."}</MarkdownText>
      {status === "needs_clarification" && candidates.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {candidates.map((candidate) => (
            <button
              key={candidate.stop_ref}
              type="button"
              onClick={() => onClarify(candidate.name)}
              className="rounded-full border border-white/60 bg-white/50 px-3.5 py-1.5 text-xs font-medium text-neutral-700 backdrop-blur-md transition duration-200 hover:-translate-y-0.5 hover:border-accent/60 hover:text-accent hover:shadow-glass-sm"
            >
              {candidate.name}
            </button>
          ))}
        </div>
      )}
    </GlassTile>
  );
}
