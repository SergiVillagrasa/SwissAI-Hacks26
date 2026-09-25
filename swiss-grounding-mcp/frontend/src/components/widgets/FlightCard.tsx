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
  booking_url?: string | null;
  price_chf?: number | null;
}

export interface FlightSearchData {
  flight?: Flight | null;
  flights?: Flight[];
  fields_missing?: string[];
}

function fieldOrNotReported(value: string | null | undefined): string {
  return value ?? "not reported by source";
}

function airlineLabel(flight: Flight): string {
  return flight.airline.name ?? flight.airline.iata ?? "the airline";
}

function airportCode(airport: AirportInfo): string {
  return airport.iata ?? airport.icao ?? "not reported by source";
}

function BookFlightButton({ flight, compact = false }: { flight: Flight; compact?: boolean }) {
  if (!flight.booking_url) return null;
  const airline = airlineLabel(flight);
  return (
    <a
      href={flight.booking_url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Book flight ${flight.flight_number} on ${airline}, opens the official booking site in a new tab`}
      className={
        compact
          ? "inline-block shrink-0 cursor-pointer rounded-full bg-accent px-3 py-1.5 text-xs font-medium text-white shadow-glass-sm transition duration-200 hover:bg-accent-dim"
          : "mt-3 inline-block cursor-pointer rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white shadow-glass-sm transition duration-200 hover:bg-accent-dim"
      }
    >
      {compact ? "Book" : `Book on ${airline}`}
    </a>
  );
}

function FlightSummary({ flight }: { flight: Flight }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm font-semibold text-neutral-800">
        <span>{flight.flight_number}</span>
        <span className="text-accent-ink">{fieldOrNotReported(flight.airline.name)}</span>
      </div>
      <div className="mt-1 text-xs font-medium tracking-wide text-neutral-600">
        {airportCode(flight.departure.airport)} → {airportCode(flight.arrival.airport)}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-600">
        <span>Gate: {fieldOrNotReported(flight.departure.gate)}</span>
        <span>Terminal: {fieldOrNotReported(flight.departure.terminal)}</span>
        <span>Arrival gate: {fieldOrNotReported(flight.arrival.gate)}</span>
      </div>
      <div className="mt-1 text-xs">
        {flight.price_chf != null ? (
          <span className="tabular font-semibold text-accent-ink">
            From CHF {flight.price_chf.toFixed(2)}
          </span>
        ) : (
          <span className="text-neutral-500">Check live fares on booking</span>
        )}
      </div>
    </div>
  );
}

export function FlightCard({ data, onSelect }: { data: FlightSearchData; onSelect: (flight: Flight) => void }) {
  if (data.flight) {
    return (
      <GlassTile className="p-4">
        <FlightSummary flight={data.flight} />
        <BookFlightButton flight={data.flight} />
      </GlassTile>
    );
  }

  return (
    <GlassTile className="space-y-2 p-4">
      {(data.flights ?? []).map((flight, index) => (
        <div key={index} className={`flex items-center gap-3 p-3.5 ${glassRowInteractive}`}>
          <button
            type="button"
            onClick={() => onSelect(flight)}
            className="min-w-0 flex-1 cursor-pointer text-left"
          >
            <FlightSummary flight={flight} />
          </button>
          <BookFlightButton flight={flight} compact />
        </div>
      ))}
    </GlassTile>
  );
}
