import { lazy, Suspense, useState } from "react";
import { GlassTile, glassRowInteractive, glassRowSelected } from "../GlassTile";
import { SortBadge } from "./SortBadge";
import { ViaBadge } from "./ViaBadge";
import { ExpandChevron } from "./ExpandChevron";
import { useRouteWaypoints } from "../../lib/useRouteWaypoints";

const RouteMap = lazy(() => import("./RouteMap").then((m) => ({ default: m.RouteMap })));

interface Leg {
  mode: string;
  line: string | null;
  from_name: string;
  to_name: string;
  departure: string | null;
  arrival: string | null;
}

interface Connection {
  departure: string;
  arrival: string;
  duration_minutes: number;
  changes: number;
  origin_latitude: number | null;
  origin_longitude: number | null;
  destination_latitude: number | null;
  destination_longitude: number | null;
  legs: Leg[];
}

interface Provenance {
  source: string;
  source_url: string;
  retrieved_at: string;
}

export interface ConnectionSearchData {
  connections: Connection[];
  provenance?: Provenance | null;
  sorted_by?: string | null;
  via_stop_name?: string | null;
}

interface TrainConnectionsCardProps {
  data: ConnectionSearchData;
  onSelect: (connection: Connection) => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Europe/Zurich",
  });
}

/** YYYY-MM-DD in Swiss local time -- the UTC date alone can be off by one
 * day for departures close to midnight (e.g. 23:10 UTC is already past
 * midnight in Zurich), which would build a deep link for the wrong date. */
function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Zurich" }).format(new Date(iso));
}

/** Client-built SBB timetable deep link for the selected connection, matching
 * the server's `build_sbb_deep_link` URL shape (https://sbb.ch/en?von=..&nach=..&date=..). */
function sbbDeepLink(connection: Connection): string | null {
  const legs = connection.legs ?? [];
  if (legs.length === 0) return null;
  const origin = legs[0].from_name;
  const destination = legs[legs.length - 1].to_name;
  const params = new URLSearchParams({ von: origin, nach: destination, date: formatDate(connection.departure) });
  return `https://sbb.ch/en?${params.toString()}`;
}

/** The stations where the traveller changes trains, derived from consecutive rail legs. */
function transferStations(connection: Connection): string[] {
  const railLegs = (connection.legs ?? []).filter((leg) => leg.mode !== "walk" && leg.mode !== "foot");
  return railLegs.slice(0, -1).map((leg) => leg.to_name);
}

function ConnectionDetail({
  connection,
  viaStopName,
}: {
  connection: Connection;
  viaStopName?: string | null;
}) {
  const legs = connection.legs ?? [];
  const transfers = transferStations(connection);
  const bookingUrl = sbbDeepLink(connection);
  const { waypoints, isResolving } = useRouteWaypoints(connection, viaStopName);

  return (
    <div className="space-y-3 border-t border-blue-200/70 bg-blue-50/40 p-3.5">
      {transfers.length > 0 && (
        <div className="text-xs text-neutral-600">
          <span className="font-semibold text-neutral-700">Change at:</span> {transfers.join(", ")}
        </div>
      )}
      <ol className="space-y-2">
        {legs.map((leg, index) => (
          <li key={index} className="flex items-start gap-2 text-xs text-neutral-700">
            <span className="mt-0.5 shrink-0 rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-700">
              {leg.mode === "walk" || leg.mode === "foot" ? "Walk" : leg.line ?? leg.mode}
            </span>
            <span className="flex-1">
              {leg.from_name} → {leg.to_name}
              {leg.departure && leg.arrival && (
                <span className="tabular text-neutral-500"> ({formatTime(leg.departure)} – {formatTime(leg.arrival)})</span>
              )}
            </span>
          </li>
        ))}
      </ol>
      {legs.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-white/50">
          <Suspense fallback={null}>
            <RouteMap waypoints={waypoints} isResolving={isResolving} />
          </Suspense>
        </div>
      )}
      {bookingUrl && (
        <a
          href={bookingUrl}
          target="_blank"
          rel="noreferrer"
          aria-label="Book on SBB, opens the official SBB website in a new tab"
          className="inline-block rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white shadow-glass-sm transition duration-200 hover:bg-accent-dim"
        >
          Book on SBB
        </a>
      )}
    </div>
  );
}

export function TrainConnectionsCard({ data, onSelect }: TrainConnectionsCardProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  function handleSelect(index: number, connection: Connection) {
    setSelectedIndex((current) => (current === index ? null : index));
    onSelect(connection);
  }

  return (
    <GlassTile className="space-y-2 p-4">
      <div className="flex flex-wrap gap-2">
        <SortBadge sortedBy={data.sorted_by} />
        <ViaBadge viaStopName={data.via_stop_name} />
      </div>
      {(data.connections ?? []).map((connection, index) => {
        const isSelected = selectedIndex === index;
        return (
          <div
            key={index}
            className={`overflow-hidden ${glassRowInteractive} ${isSelected ? glassRowSelected : ""}`}
          >
            <button
              type="button"
              onClick={() => handleSelect(index, connection)}
              aria-expanded={isSelected}
              className="flex w-full items-center gap-3 p-3.5 text-left cursor-pointer"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between text-sm font-semibold text-neutral-800">
                  <span className="tabular">
                    {formatTime(connection.departure)} → {formatTime(connection.arrival)}
                  </span>
                  <span className="tabular text-accent-ink">{connection.duration_minutes} min</span>
                </div>
                <div className="text-xs text-neutral-600">
                  {connection.changes === 0 ? "Direct" : `${connection.changes} change${connection.changes > 1 ? "s" : ""}`}
                </div>
              </div>
              <ExpandChevron expanded={isSelected} />
            </button>
            {isSelected && <ConnectionDetail connection={connection} viaStopName={data.via_stop_name} />}
          </div>
        );
      })}
      {data.provenance && (
        <a
          href={data.provenance.source_url}
          target="_blank"
          rel="noreferrer"
          className="block px-1 text-xs text-neutral-600 hover:text-accent-ink hover:underline"
        >
          Source: {data.provenance.source}
        </a>
      )}
    </GlassTile>
  );
}
