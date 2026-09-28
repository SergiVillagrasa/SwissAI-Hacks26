const SORT_LABELS: Record<string, string> = {
  price: "Cheapest",
  departure: "Soonest departure",
};

export function SortBadge({ sortedBy }: { sortedBy: string | null | undefined }) {
  const label = sortedBy ? SORT_LABELS[sortedBy] : undefined;
  if (!label) return null;

  return (
    <span
      data-testid="sort-badge"
      className="inline-flex w-fit items-center rounded-full border border-white/60 bg-white/70 px-3 py-1 text-xs font-medium text-accent-ink shadow-glass-sm"
    >
      Sorted by: {label}
    </span>
  );
}
