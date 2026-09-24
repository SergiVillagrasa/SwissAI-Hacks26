import { useState } from "react";
import { RouteMap } from "./RouteMap";

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
    <div className="space-y-2">
      {data.connections.map((connection, index) => (
        <button
          key={index}
          type="button"
          onClick={() => handleSelect(connection)}
          className="w-full rounded-xl border border-neutral-200 p-3 text-left hover:border-accent"
        >
          <div className="flex items-center justify-between text-sm font-medium">
            <span>{formatTime(connection.departure)} → {formatTime(connection.arrival)}</span>
            <span>{connection.duration_minutes} min</span>
          </div>
          <div className="text-xs text-neutral-500">
            {connection.changes === 0 ? "Direct" : `${connection.changes} change${connection.changes > 1 ? "s" : ""}`}
          </div>
        </button>
      ))}
      {selected && selected.legs.length > 0 && (
        <RouteMap origin={selected.legs[0].from_name} destination={selected.legs[selected.legs.length - 1].to_name} />
      )}
      {data.provenance && (
        <a
          href={data.provenance.source_url}
          target="_blank"
          rel="noreferrer"
          className="block text-xs text-neutral-400 hover:underline"
        >
          Source: {data.provenance.source}
        </a>
      )}
    </div>
  );
}
