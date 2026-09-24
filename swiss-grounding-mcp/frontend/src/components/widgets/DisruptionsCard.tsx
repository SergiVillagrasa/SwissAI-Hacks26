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

export function DisruptionsCard({ data }: { data: DisruptionSearchData }) {
  return (
    <GlassTile className="p-4">
      <ul className="space-y-2">
        {data.disruptions.map((disruption) => (
          <li
            key={disruption.id}
            className="rounded-2xl border border-amber-200/70 bg-amber-50/70 p-3.5 backdrop-blur-md"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-amber-900">{disruption.title ?? "Disruption"}</span>
              <span className="shrink-0 rounded-full bg-amber-200/70 px-2 py-0.5 text-xs font-medium uppercase text-amber-800">
                {disruption.severity ?? "not reported by source"}
              </span>
            </div>
            {disruption.description && (
              <p className="mt-1 text-sm text-amber-900/80">{disruption.description}</p>
            )}
            {disruption.affected_lines.length > 0 && (
              <p className="mt-1 text-xs text-amber-700">{disruption.affected_lines.join(", ")}</p>
            )}
          </li>
        ))}
      </ul>
    </GlassTile>
  );
}
