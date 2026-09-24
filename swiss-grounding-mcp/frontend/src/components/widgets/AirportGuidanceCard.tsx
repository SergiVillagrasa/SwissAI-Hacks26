export interface AirportGuidanceData {
  topic: string;
  guidance: string | null;
  source: string | null;
  source_url: string | null;
}

export function AirportGuidanceCard({ data }: { data: AirportGuidanceData }) {
  return (
    <div className="space-y-2 rounded-xl border border-neutral-200 p-4">
      <p className="text-sm text-neutral-700">{data.guidance}</p>
      {data.source_url && (
        <a href={data.source_url} target="_blank" rel="noreferrer" className="text-xs text-neutral-400 hover:underline">
          Source: {data.source}
        </a>
      )}
    </div>
  );
}
