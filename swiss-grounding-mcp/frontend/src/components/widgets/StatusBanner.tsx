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
    <div className="rounded-xl border border-neutral-200 bg-neutral-100 p-4 text-sm text-neutral-600">
      <p>{message ?? "This could not be answered."}</p>
      {status === "needs_clarification" && candidates.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {candidates.map((candidate) => (
            <button
              key={candidate.stop_ref}
              type="button"
              onClick={() => onClarify(candidate.name)}
              className="rounded-full border border-neutral-300 px-3 py-1 text-xs hover:border-accent"
            >
              {candidate.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
