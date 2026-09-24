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
    <ul className="space-y-2">
      {data.disruptions.map((disruption) => (
        <li key={disruption.id} className="rounded-xl border border-amber-200 bg-amber-50 p-3">
          <div className="flex items-center justify-between">
            <span className="font-medium">{disruption.title ?? "Disruption"}</span>
            <span className="text-xs uppercase text-amber-700">{disruption.severity ?? "not reported by source"}</span>
          </div>
          {disruption.description && <p className="text-sm text-neutral-600">{disruption.description}</p>}
          {disruption.affected_lines.length > 0 && (
            <p className="text-xs text-neutral-500">{disruption.affected_lines.join(", ")}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
