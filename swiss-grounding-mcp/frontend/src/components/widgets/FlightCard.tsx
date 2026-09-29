import { useState } from "react";
import { GlassTile, glassRowInteractive, glassRowSelected } from "../GlassTile";
import { ExpandChevron } from "./ExpandChevron";

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

// booking_url is a Google Flights search link for any flight with distinct
// origin/destination airports; it only lands on the airline's own portal
// when the route is unknown. Label and announce it accordingly instead of
// always claiming it's the airline's official booking page.
function isGoogleFlightsUrl(url: string): boolean {
  return url.startsWith("https://www.google.com/travel/flights");
}

function BookFlightButton({ flight, compact = false }: { flight: Flight; compact?: boolean }) {
  if (!flight.booking_url) return null;
  const airline = airlineLabel(flight);
  const onGoogleFlights = isGoogleFlightsUrl(flight.booking_url);
  const fullLabel = onGoogleFlights ? "Search on Google Flights" : `Book on ${airline}`;
  const ariaSite = onGoogleFlights ? "Google Flights" : `the ${airline} website`;
  return (
    <a
      href={flight.booking_url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Book flight ${flight.flight_number}, opens ${ariaSite} in a new tab`}
      className={
        compact
          ? "inline-block shrink-0 cursor-pointer rounded-full bg-accent px-3 py-1.5 text-xs font-medium text-white shadow-glass-sm transition duration-200 hover:bg-accent-dim"
          : "mt-3 inline-block cursor-pointer rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white shadow-glass-sm transition duration-200 hover:bg-accent-dim"
      }
    >
      {compact ? "Book" : fullLabel}
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

function statusLabel(flight: Flight): string {
  return flight.flight_status ? flight.flight_status.replace(/_/g, " ") : "not reported by source";
}

function FlightDetail({ flight }: { flight: Flight }) {
  return (
    <div className="space-y-2 border-t border-blue-200/70 bg-blue-50/40 p-3.5 text-xs text-neutral-700">
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span><span className="font-semibold text-neutral-600">Airline:</span> {fieldOrNotReported(flight.airline.name)}</span>
        <span><span className="font-semibold text-neutral-600">Status:</span> {statusLabel(flight)}</span>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span><span className="font-semibold text-neutral-600">Departure terminal:</span> {fieldOrNotReported(flight.departure.terminal)}</span>
        <span><span className="font-semibold text-neutral-600">Departure gate:</span> {fieldOrNotReported(flight.departure.gate)}</span>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span><span className="font-semibold text-neutral-600">Arrival terminal:</span> {fieldOrNotReported(flight.arrival.terminal)}</span>
        <span><span className="font-semibold text-neutral-600">Arrival gate:</span> {fieldOrNotReported(flight.arrival.gate)}</span>
      </div>
      <BookFlightButton flight={flight} />
    </div>
  );
}

export function FlightCard({ data, onSelect }: { data: FlightSearchData; onSelect: (flight: Flight) => void }) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  if (data.flight) {
    return (
      <GlassTile className="p-4">
        <FlightSummary flight={data.flight} />
        <BookFlightButton flight={data.flight} />
      </GlassTile>
    );
  }

  function handleSelect(index: number, flight: Flight) {
    setSelectedIndex((current) => (current === index ? null : index));
    onSelect(flight);
  }

  return (
    <GlassTile className="space-y-2 p-4">
      {(data.flights ?? []).map((flight, index) => {
        const isSelected = selectedIndex === index;
        return (
          <div
            key={index}
            className={`overflow-hidden ${glassRowInteractive} ${isSelected ? glassRowSelected : ""}`}
          >
            <div className="flex items-center gap-3 p-3.5">
              <button
                type="button"
                onClick={() => handleSelect(index, flight)}
                aria-expanded={isSelected}
                className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 text-left hover:bg-blue-50/60"
              >
                <div className="min-w-0 flex-1">
                  <FlightSummary flight={flight} />
                </div>
                <ExpandChevron expanded={isSelected} />
              </button>
              <BookFlightButton flight={flight} compact />
            </div>
            {isSelected && <FlightDetail flight={flight} />}
          </div>
        );
      })}
    </GlassTile>
  );
}
