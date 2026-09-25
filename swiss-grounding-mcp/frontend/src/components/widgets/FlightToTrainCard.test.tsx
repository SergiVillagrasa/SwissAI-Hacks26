import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FlightToTrainCard } from "./FlightToTrainCard";

describe("FlightToTrainCard", () => {
  it("renders the flight summary and onward train connections together", () => {
    render(
      <FlightToTrainCard
        data={{
          message: "Considering onward trains departing no earlier than 15:10 (60-minute transfer buffer).",
          flight: {
            flight_number: "LX14",
            flight_date: "2026-09-25",
            airline: { name: "SWISS", iata: "LX", icao: "SWR" },
            departure: { airport: { iata: "JFK", icao: "KJFK", name: "JFK", timezone: null }, scheduled: null, estimated: null, actual: null, terminal: null, gate: null, delay_minutes: null },
            arrival: { airport: { iata: "ZRH", icao: "LSZH", name: "Zurich Airport", timezone: null }, scheduled: "2026-09-25T14:10:00+02:00", estimated: null, actual: null, terminal: "2", gate: null, delay_minutes: null },
            flight_status: "scheduled",
            booking_url: "https://www.swiss.com/us/en/Book/JFK-ZRH/from-2026-09-25",
          },
          train_connections: [
            { departure: "2026-09-25T15:10:00+02:00", arrival: "2026-09-25T16:00:00+02:00", duration_minutes: 50, changes: 0, legs: [] },
          ],
        }}
        onSelectConnection={() => {}}
      />
    );

    expect(screen.getByText("LX14")).toBeInTheDocument();
    expect(screen.getByText(/60-minute transfer buffer/)).toBeInTheDocument();
    expect(screen.getByText(/50 min/)).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /book flight lx14/i });
    expect(link).toHaveAttribute("href", "https://www.swiss.com/us/en/Book/JFK-ZRH/from-2026-09-25");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });
});
