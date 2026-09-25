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
  booking_url: "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+JFK+on+2026-09-25",
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

  it("renders the booking link as an accessible new-tab anchor for a single flight", () => {
    render(<FlightCard data={{ flight: sampleFlight, flights: [] }} onSelect={() => {}} />);

    const link = screen.getByRole("link", { name: /book flight lx14/i });
    expect(link).toHaveAttribute("href", "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+JFK+on+2026-09-25");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
    expect(link).toHaveTextContent("Book on SWISS");
  });

  it("renders no booking link when booking_url is absent", () => {
    const { booking_url: _omit, ...flightWithoutUrl } = sampleFlight;
    render(<FlightCard data={{ flight: flightWithoutUrl, flights: [] }} onSelect={() => {}} />);

    expect(screen.queryByRole("link", { name: /book/i })).not.toBeInTheDocument();
  });

  it("renders a selectable list for a flight search result", () => {
    const onSelect = vi.fn();
    render(<FlightCard data={{ flight: null, flights: [sampleFlight], fields_missing: [] }} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: /LX14/ }));

    expect(onSelect).toHaveBeenCalledWith(sampleFlight);
  });

  it("renders a per-flight booking link in the search list without hijacking selection", () => {
    const onSelect = vi.fn();
    render(<FlightCard data={{ flight: null, flights: [sampleFlight] }} onSelect={onSelect} />);

    const link = screen.getByRole("link", { name: /book flight lx14/i });
    expect(link).toHaveAttribute("href", "https://www.google.com/travel/flights?q=Flights+from+ZRH+to+JFK+on+2026-09-25");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");

    fireEvent.click(screen.getByRole("button", { name: /LX14/ }));
    expect(onSelect).toHaveBeenCalledWith(sampleFlight);
  });
});
