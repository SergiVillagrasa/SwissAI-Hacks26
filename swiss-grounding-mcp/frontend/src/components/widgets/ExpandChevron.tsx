/** Small chevron that rotates to indicate expanded/collapsed state for a selectable row. */
export function ExpandChevron({ expanded }: { expanded: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={`h-4 w-4 shrink-0 text-blue-500 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
    >
      <path d="M5.5 8l4.5 4.5L14.5 8" />
    </svg>
  );
}
