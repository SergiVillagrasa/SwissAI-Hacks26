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
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{data.station_name}</h3>
      <ul className="space-y-1">
        {data.events.map((event, index) => (
          <li key={index} className="flex items-center justify-between text-sm">
            <span className="font-medium">{event.line ?? "—"}</span>
            <span className="text-neutral-500">to {event.direction_name ?? "not reported by source"}</span>
            <span>{event.planned_time ? new Date(event.planned_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "not reported by source"}</span>
            <span className="text-xs text-neutral-400">{event.platform ? `Platform ${event.platform}` : "not reported by source"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
