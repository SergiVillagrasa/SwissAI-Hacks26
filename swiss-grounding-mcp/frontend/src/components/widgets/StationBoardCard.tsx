import { GlassTile, glassRow } from "../GlassTile";

interface StopEvent {
  line: string | null;
  mode: string | null;
  direction_name: string | null;
  planned_time: string | null;
  estimated_time: string | null;
  platform: string | null;
  delay_minutes: number | null;
}

export interface StationBoardData {
  station_name: string | null;
  event_type: string | null;
  events: StopEvent[];
}

export function StationBoardCard({ data }: { data: StationBoardData }) {
  return (
    <GlassTile className="space-y-3 p-4">
      <h3 className="px-1 text-sm font-semibold text-neutral-800">{data.station_name}</h3>
      <ul className="space-y-2">
        {data.events.map((event, index) => (
          <li
            key={index}
            className={`flex items-center justify-between gap-3 p-3 text-sm ${glassRow}`}
          >
            <span className="font-semibold text-accent-ink">{event.line ?? "—"}</span>
            <span className="flex-1 truncate text-neutral-600">
              to {event.direction_name ?? "not reported by source"}
            </span>
            <span className="tabular font-medium text-neutral-800">
              {event.planned_time
                ? new Date(event.planned_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                : "not reported by source"}
            </span>
            <span className="text-xs text-neutral-600">
              {event.platform ? `Platform ${event.platform}` : "not reported by source"}
            </span>
          </li>
        ))}
      </ul>
    </GlassTile>
  );
}
