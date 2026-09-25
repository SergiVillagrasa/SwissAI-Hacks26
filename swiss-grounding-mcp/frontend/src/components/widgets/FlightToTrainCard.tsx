import { FlightCard, type FlightSearchData } from "./FlightCard";
import { BookOnSbbButton } from "./FaresCard";
import { TrainConnectionsCard, type ConnectionSearchData } from "./TrainConnectionsCard";

interface FlightToTrainData {
  message?: string | null;
  flight?: FlightSearchData["flight"];
  train_connections: ConnectionSearchData["connections"];
  train_booking_url?: string | null;
  train_price_chf?: number | null;
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
      {data.message && <p className="px-1 text-sm text-neutral-600">{data.message}</p>}
      {data.flight && <FlightCard data={{ flight: data.flight, flights: [] }} onSelect={() => {}} />}
      <TrainConnectionsCard data={{ connections: data.train_connections }} onSelect={onSelectConnection} />
      {(data.train_booking_url || data.train_price_chf != null) && (
        <div className="flex items-center justify-between gap-3 px-1">
          {data.train_price_chf != null && (
            <span className="text-sm text-neutral-600">
              Train fare from{" "}
              <span className="tabular font-semibold text-accent-ink">
                CHF {data.train_price_chf.toFixed(2)}
              </span>
            </span>
          )}
          <BookOnSbbButton bookingUrl={data.train_booking_url} />
        </div>
      )}
    </div>
  );
}
