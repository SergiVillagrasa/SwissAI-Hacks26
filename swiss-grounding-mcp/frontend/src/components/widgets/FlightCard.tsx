import { GlassTile, glassRowInteractive } from "../GlassTile";

interface AirportInfo {
  iata: string | null;
  icao: string | null;
  name: string | null;
  timezone: string | null;
}

interface FlightEndpoint {
  airport: AirportInfo;
  scheduled: string | null;
  estimated: string | null;
  actual: string | null;
  terminal: string | null;
  gate: string | null;
  delay_minutes: number | null;
}

interface Flight {
  flight_number: string;
  flight_date: string;
  airline: { name: string | null; iata: string | null; icao: string | null };
  departure: FlightEndpoint;
  arrival: FlightEndpoint;
  flight_status: string | null;
}

export interface FlightSearchData {
  flight?: Flight | null;
  flights?: Flight[];
  fields_missing?: string[];
}

function fieldOrNotReported(value: string | null | undefined): string {
  return value ?? "not reported by source";
}

function FlightSummary({ flight, nested = false }: { flight: Flight; nested?: boolean }) {
  return (
    <div className={nested ? `p-3.5 ${glassRowInteractive}` : "space-y-1"}>
      <div className="flex items-center justify-between text-sm font-semibold text-neutral-800">
        <span>{flight.flight_number}</span>
        <span className="text-accent-ink">{fieldOrNotReported(flight.airline.name)}</span>
      </div>
      <div className="mt-1 text-xs font-medium tracking-wide text-neutral-600">
        {fieldOrNotReported(flight.departure.airport.iata)} → {fieldOrNotReported(flight.arrival.airport.iata)}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-600">
        <span>Gate: {fieldOrNotReported(flight.departure.gate)}</span>
        <span>Terminal: {fieldOrNotReported(flight.departure.terminal)}</span>
        <span>Arrival gate: {fieldOrNotReported(flight.arrival.gate)}</span>
      </div>
    </div>
  );
}

export function FlightCard({ data, onSelect }: { data: FlightSearchData; onSelect: (flight: Flight) => void }) {
  if (data.flight) {
    return (
      <GlassTile className="p-4">
        <FlightSummary flight={data.flight} />
      </GlassTile>
    );
  }

  return (
    <GlassTile className="space-y-2 p-4">
      {(data.flights ?? []).map((flight, index) => (
        <button key={index} type="button" onClick={() => onSelect(flight)} className="block w-full text-left">
          <FlightSummary flight={flight} nested />
        </button>
      ))}
    </GlassTile>
  );
}
