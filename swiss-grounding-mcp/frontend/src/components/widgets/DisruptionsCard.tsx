import { GlassTile } from "../GlassTile";

interface Disruption {
  id: string;
  title: string | null;
  description: string | null;
  severity: string | null;
  start_time: string | null;
  end_time: string | null;
  status: string | null;
  affected_lines: string[];
  affected_stops: string[];
}

export interface DisruptionSearchData {
  disruptions: Disruption[];
}

interface SeverityStyle {
  container: string;
  title: string;
  badge: string;
  description: string;
  lines: string;
}

const SEVERITY_STYLES: Record<string, SeverityStyle> = {
  critical: {
    container: "border-rose-200/70 bg-rose-50/70",
    title: "text-rose-900",
    badge: "bg-rose-200/70 text-rose-800",
    description: "text-rose-900/80",
    lines: "text-rose-700",
  },
  high: {
    container: "border-rose-200/70 bg-rose-50/70",
    title: "text-rose-900",
    badge: "bg-rose-200/70 text-rose-800",
    description: "text-rose-900/80",
    lines: "text-rose-700",
  },
  major: {
    container: "border-amber-200/70 bg-amber-50/70",
    title: "text-amber-900",
    badge: "bg-amber-200/70 text-amber-800",
    description: "text-amber-900/80",
    lines: "text-amber-700",
  },
  medium: {
    container: "border-amber-200/70 bg-amber-50/70",
    title: "text-amber-900",
    badge: "bg-amber-200/70 text-amber-800",
    description: "text-amber-900/80",
    lines: "text-amber-700",
  },
  minor: {
    container: "border-slate-200/70 bg-slate-50/70",
    title: "text-slate-800",
    badge: "bg-slate-200/70 text-slate-700",
    description: "text-slate-800/80",
    lines: "text-slate-600",
  },
  low: {
    container: "border-slate-200/70 bg-slate-50/70",
    title: "text-slate-800",
    badge: "bg-slate-200/70 text-slate-700",
    description: "text-slate-800/80",
    lines: "text-slate-600",
  },
};

const DEFAULT_SEVERITY_STYLE: SeverityStyle = SEVERITY_STYLES.major;

function severityStyleFor(severity: string | null): SeverityStyle {
  const key = severity?.toLowerCase().trim();
  if (!key) return DEFAULT_SEVERITY_STYLE;
  return SEVERITY_STYLES[key] ?? DEFAULT_SEVERITY_STYLE;
}

export function DisruptionsCard({ data }: { data: DisruptionSearchData }) {
  return (
    <GlassTile className="p-4">
      <ul className="space-y-2">
        {data.disruptions.map((disruption) => {
          const style = severityStyleFor(disruption.severity);
          return (
            <li
              key={disruption.id}
              className={`rounded-2xl border p-3.5 backdrop-blur-md ${style.container}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`font-semibold ${style.title}`}>{disruption.title ?? "Disruption"}</span>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium uppercase ${style.badge}`}
                >
                  {disruption.severity ?? "not reported by source"}
                </span>
              </div>
              {disruption.description && (
                <p className={`mt-1 text-sm ${style.description}`}>{disruption.description}</p>
              )}
              {disruption.affected_lines.length > 0 && (
                <p className={`mt-1 text-xs ${style.lines}`}>{disruption.affected_lines.join(", ")}</p>
              )}
            </li>
          );
        })}
      </ul>
    </GlassTile>
  );
}
