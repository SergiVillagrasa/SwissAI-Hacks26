import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FlightCard } from "./FlightCard";

const sampleFlight = {
  flight_number: "LX14",
  flight_date: "2026-09-25",
  airline: { name: "SWISS", iata: "LX", icao: "SWR" },
  departure: { airport: { iata: "ZRH", icao: "LSZH", name: "Zurich Airport", timezone: null }, scheduled: "2026-09-25T10:20:00+02:00", estimated: null, actual: null, terminal: "1", gate: "A12", delay_minutes: 5 },
  arrival: { airport: { iata: "JFK", icao: "KJFK", name: "John F. Kennedy Intl", timezone: null }, scheduled: "2026-09-25T14:10:00-04:00", estimated: null, actual: null, terminal: "4", gate: null, delay_minutes: null },
  flight_status: "scheduled",
};

describe("FlightCard", () => {
  it("renders a single flight lookup result with explicit not-reported fields", () => {
    render(
      <FlightCard
        data={{ flight: sampleFlight, flights: [], fields_missing: ["arrival.gate"] }}
        onSelect={() => {}}
      />
    );

    expect(screen.getByText("LX14")).toBeInTheDocument();
    expect(screen.getByText("SWISS")).toBeInTheDocument();
    expect(screen.getAllByText(/not reported by source/i).length).toBeGreaterThan(0);
  });

  it("renders a selectable list for a flight search result", () => {
    const onSelect = vi.fn();
    render(<FlightCard data={{ flight: null, flights: [sampleFlight], fields_missing: [] }} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: /LX14/ }));

    expect(onSelect).toHaveBeenCalledWith(sampleFlight);
  });
});
