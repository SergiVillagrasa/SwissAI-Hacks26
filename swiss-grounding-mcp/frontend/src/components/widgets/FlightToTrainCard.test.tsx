import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FlightToTrainCard } from "./FlightToTrainCard";

const baseData = {
  message: "Considering onward trains departing no earlier than 15:10 (60-minute transfer buffer).",
  flight: {
    flight_number: "LX14",
    flight_date: "2026-09-25",
    airline: { name: "SWISS", iata: "LX", icao: "SWR" },
    departure: { airport: { iata: "JFK", icao: "KJFK", name: "JFK", timezone: null }, scheduled: null, estimated: null, actual: null, terminal: null, gate: null, delay_minutes: null },
    arrival: { airport: { iata: "ZRH", icao: "LSZH", name: "Zurich Airport", timezone: null }, scheduled: "2026-09-25T14:10:00+02:00", estimated: null, actual: null, terminal: "2", gate: null, delay_minutes: null },
    flight_status: "scheduled",
    booking_url: "https://www.google.com/travel/flights?q=Flights+from+JFK+to+ZRH+on+2026-09-25",
  },
  train_connections: [
    { departure: "2026-09-25T15:10:00+02:00", arrival: "2026-09-25T16:00:00+02:00", duration_minutes: 50, changes: 0, legs: [] },
  ],
};

describe("FlightToTrainCard", () => {
  it("renders the flight summary and onward train connections together", () => {
    render(<FlightToTrainCard data={baseData} onSelectConnection={() => {}} />);

    expect(screen.getByText("LX14")).toBeInTheDocument();
    expect(screen.getByText(/60-minute transfer buffer/)).toBeInTheDocument();
    expect(screen.getByText(/50 min/)).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /book flight lx14/i });
    expect(link).toHaveAttribute("href", "https://www.google.com/travel/flights?q=Flights+from+JFK+to+ZRH+on+2026-09-25");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("renders the SBB booking link and the cheapest train fare", () => {
    render(
      <FlightToTrainCard
        data={{
          ...baseData,
          train_booking_url: "https://sbb.ch/en?von=Z%C3%BCrich%20Flughafen&nach=Bern&date=2026-09-25",
          train_price_chf: 19.8,
        }}
        onSelectConnection={() => {}}
      />
    );

    expect(screen.getByText(/CHF 19\.80/)).toBeInTheDocument();
    const sbbLink = screen.getByRole("link", { name: /book on sbb/i });
    expect(sbbLink).toHaveAttribute("href", "https://sbb.ch/en?von=Z%C3%BCrich%20Flughafen&nach=Bern&date=2026-09-25");
    expect(sbbLink).toHaveAttribute("target", "_blank");
    expect(sbbLink).toHaveAttribute("rel", "noreferrer");
  });

  it("shows the SBB booking link without a price when fares are unavailable", () => {
    render(
      <FlightToTrainCard
        data={{ ...baseData, train_booking_url: "https://sbb.ch/en?von=Z%C3%BCrich%20Flughafen&nach=Bern" }}
        onSelectConnection={() => {}}
      />
    );

    expect(screen.queryByText(/CHF/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /book on sbb/i })).toBeInTheDocument();
  });

  it("renders no train purchase section when no booking data is returned", () => {
    render(<FlightToTrainCard data={baseData} onSelectConnection={() => {}} />);

    expect(screen.queryByRole("link", { name: /book on sbb/i })).not.toBeInTheDocument();
  });
});
