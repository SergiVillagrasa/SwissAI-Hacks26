import { GlassTile } from "../GlassTile";

export interface AirportGuidanceData {
  topic: string;
  guidance: string | null;
  source: string | null;
  source_url: string | null;
}

export function AirportGuidanceCard({ data }: { data: AirportGuidanceData }) {
  return (
    <GlassTile className="space-y-2 p-4">
      <p className="text-sm leading-relaxed text-neutral-700">{data.guidance}</p>
      {data.source_url && (
        <a
          href={data.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-neutral-600 hover:text-accent-ink hover:underline"
        >
          Source: {data.source}
        </a>
      )}
    </GlassTile>
  );
}
