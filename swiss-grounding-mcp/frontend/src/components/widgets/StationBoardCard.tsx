import { useState } from "react";
import { GlassTile, glassRow, glassRowSelected } from "../GlassTile";

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

function formatTime(iso: string): string {
  // An explicit locale (rather than [] -- the runtime's default) keeps the
  // output deterministic regardless of the browser/OS locale: some locales
  // render a 24-hour time differently (digits, separators) even with
  // hour12 forced to false.
  return new Date(iso).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Europe/Zurich",
  });
}

export function StationBoardCard({ data }: { data: StationBoardData }) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  return (
    <GlassTile className="space-y-3 p-4">
      <h3 className="px-1 text-sm font-semibold text-neutral-800">{data.station_name}</h3>
      <ul className="space-y-2">
        {data.events.map((event, index) => {
          const isSelected = selectedIndex === index;
          return (
            <li key={index}>
              <button
                type="button"
                onClick={() => setSelectedIndex((current) => (current === index ? null : index))}
                aria-expanded={isSelected}
                className={`flex w-full cursor-pointer items-center justify-between gap-3 p-3 text-left text-sm transition duration-200 hover:bg-blue-50/60 ${glassRow} ${isSelected ? glassRowSelected : ""}`}
              >
                <span className="font-semibold text-accent-ink">{event.line ?? "—"}</span>
                <span className="flex-1 truncate text-neutral-600">
                  to {event.direction_name ?? "not reported by source"}
                </span>
                <span className="tabular font-medium text-neutral-800">
                  {event.planned_time
                    ? formatTime(event.planned_time)
                    : "not reported by source"}
                </span>
                <span className="text-xs text-neutral-600">
                  {event.platform ? `Platform ${event.platform}` : "not reported by source"}
                </span>
              </button>
              {isSelected && (
                <div className="mt-1 space-y-1 rounded-2xl border border-blue-200/70 bg-blue-50/40 p-3 text-xs text-neutral-600">
                  <div>
                    <span className="font-semibold text-neutral-700">Mode:</span> {event.mode ?? "not reported by source"}
                  </div>
                  <div>
                    <span className="font-semibold text-neutral-700">Planned time:</span>{" "}
                    {event.planned_time ? formatTime(event.planned_time) : "not reported by source"}
                  </div>
                  <div>
                    <span className="font-semibold text-neutral-700">Estimated time:</span>{" "}
                    {event.estimated_time ? formatTime(event.estimated_time) : "not reported by source"}
                  </div>
                  <div>
                    <span className="font-semibold text-neutral-700">Delay:</span>{" "}
                    {event.delay_minutes != null ? `${event.delay_minutes} min` : "not reported by source"}
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </GlassTile>
  );
}
