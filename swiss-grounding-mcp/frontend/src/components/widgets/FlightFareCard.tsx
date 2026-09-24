import { GlassTile, glassRow } from "../GlassTile";

interface FlightFare {
  airline: string;
  flight_number: string;
  departure_time: string;
  arrival_time: string;
  price: number;
  currency: string;
  duration_minutes: number | null;
  carbon_emissions_grams: number | null;
}

export interface FlightFareSearchData {
  flights: FlightFare[];
}

function formatDuration(minutes: number | null): string | null {
  if (minutes == null) return null;
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return hours > 0 ? `${hours}h ${remaining}m` : `${remaining}m`;
}

export function FlightFareCard({ data }: { data: FlightFareSearchData }) {
  return (
    <GlassTile className="space-y-2 p-4">
      <ul className="space-y-2">
        {data.flights.map((flight, index) => {
          const duration = formatDuration(flight.duration_minutes);
          return (
            <li key={index} className={`flex items-center justify-between gap-3 p-3.5 text-sm ${glassRow}`}>
              <div className="min-w-0">
                <div className="flex items-center gap-2 font-semibold text-neutral-800">
                  <span>{flight.airline}</span>
                  <span className="text-xs font-normal text-neutral-500">{flight.flight_number}</span>
                </div>
                <div className="mt-1 text-xs text-neutral-500">
                  {flight.departure_time} → {flight.arrival_time}
                  {duration ? ` · ${duration}` : ""}
                </div>
              </div>
              <span className="shrink-0 tabular font-semibold text-accent">
                {flight.currency} {flight.price}
              </span>
            </li>
          );
        })}
      </ul>
    </GlassTile>
  );
}
