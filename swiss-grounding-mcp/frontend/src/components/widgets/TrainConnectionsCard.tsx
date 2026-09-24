import { lazy, Suspense, useState } from "react";
import { GlassTile, glassRowInteractive } from "../GlassTile";

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
}

interface TrainConnectionsCardProps {
  data: ConnectionSearchData;
  onSelect: (connection: Connection) => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function TrainConnectionsCard({ data, onSelect }: TrainConnectionsCardProps) {
  const [selected, setSelected] = useState<Connection | null>(null);

  function handleSelect(connection: Connection) {
    setSelected(connection);
    onSelect(connection);
  }

  return (
    <GlassTile className="space-y-2 p-4">
      {data.connections.map((connection, index) => (
        <button
          key={index}
          type="button"
          onClick={() => handleSelect(connection)}
          className={`w-full p-3.5 text-left ${glassRowInteractive} ${selected === connection ? "ring-2 ring-accent/60" : ""}`}
        >
          <div className="flex items-center justify-between text-sm font-semibold text-neutral-800">
            <span className="tabular">
              {formatTime(connection.departure)} → {formatTime(connection.arrival)}
            </span>
            <span className="tabular text-accent-ink">{connection.duration_minutes} min</span>
          </div>
          <div className="text-xs text-neutral-600">
            {connection.changes === 0 ? "Direct" : `${connection.changes} change${connection.changes > 1 ? "s" : ""}`}
          </div>
        </button>
      ))}
      {selected && selected.legs.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-white/50">
          <Suspense fallback={null}>
            <RouteMap origin={selected.legs[0].from_name} destination={selected.legs[selected.legs.length - 1].to_name} />
          </Suspense>
        </div>
      )}
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
