import { FlightCard, type FlightSearchData } from "./FlightCard";
import { TrainConnectionsCard, type ConnectionSearchData } from "./TrainConnectionsCard";

interface FlightToTrainData {
  message?: string | null;
  flight?: FlightSearchData["flight"];
  train_connections: ConnectionSearchData["connections"];
}

export function FlightToTrainCard({
  data,
  onSelectConnection,
}: {
  data: FlightToTrainData;
  onSelectConnection: (connection: ConnectionSearchData["connections"][number]) => void;
}) {
  return (
    <div className="space-y-3">
      {data.message && <p className="text-sm text-neutral-600">{data.message}</p>}
      {data.flight && <FlightCard data={{ flight: data.flight, flights: [] }} onSelect={() => {}} />}
      <TrainConnectionsCard data={{ connections: data.train_connections }} onSelect={onSelectConnection} />
    </div>
  );
}
