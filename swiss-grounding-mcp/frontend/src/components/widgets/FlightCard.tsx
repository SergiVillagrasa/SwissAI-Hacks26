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

function FlightSummary({ flight }: { flight: Flight }) {
  return (
    <div className="rounded-xl border border-neutral-200 p-3">
      <div className="flex items-center justify-between text-sm font-medium">
        <span>{flight.flight_number}</span>
        <span>{fieldOrNotReported(flight.airline.name)}</span>
      </div>
      <div className="text-xs text-neutral-500">
        {fieldOrNotReported(flight.departure.airport.iata)} → {fieldOrNotReported(flight.arrival.airport.iata)}
      </div>
      <div className="text-xs text-neutral-500">
        Gate: {fieldOrNotReported(flight.departure.gate)} · Terminal: {fieldOrNotReported(flight.departure.terminal)}
      </div>
      <div className="text-xs text-neutral-500">
        Arrival gate: {fieldOrNotReported(flight.arrival.gate)}
      </div>
    </div>
  );
}

export function FlightCard({ data, onSelect }: { data: FlightSearchData; onSelect: (flight: Flight) => void }) {
  if (data.flight) {
    return <FlightSummary flight={data.flight} />;
  }

  return (
    <div className="space-y-2">
      {(data.flights ?? []).map((flight, index) => (
        <button key={index} type="button" onClick={() => onSelect(flight)} className="block w-full text-left">
          <FlightSummary flight={flight} />
        </button>
      ))}
    </div>
  );
}
