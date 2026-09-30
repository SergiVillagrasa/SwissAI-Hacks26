export function ViaBadge({ viaStopName }: { viaStopName: string | null | undefined }) {
  if (!viaStopName) return null;

  return (
    <span
      data-testid="via-badge"
      className="inline-flex w-fit items-center rounded-full border border-white/60 bg-white/70 px-3 py-1 text-xs font-medium text-accent-ink shadow-glass-sm"
    >
      {`Via ${viaStopName}`}
    </span>
  );
}
