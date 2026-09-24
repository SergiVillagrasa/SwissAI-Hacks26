import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FlightFareCard } from "./FlightFareCard";

describe("FlightFareCard", () => {
  it("renders each fare's airline, flight number, times, and price", () => {
    render(
      <FlightFareCard
        data={{
          flights: [
            {
              airline: "Swiss International Air Lines",
              flight_number: "LX1234",
              departure_time: "2026-09-25 08:00",
              arrival_time: "2026-09-25 08:50",
              price: 129,
              currency: "CHF",
              duration_minutes: 50,
              carbon_emissions_grams: 45000,
            },
          ],
        }}
      />
    );

    expect(screen.getByText("Swiss International Air Lines")).toBeInTheDocument();
    expect(screen.getByText("LX1234")).toBeInTheDocument();
    expect(screen.getByText(/2026-09-25 08:00.*2026-09-25 08:50/)).toBeInTheDocument();
    expect(screen.getByText("CHF 129")).toBeInTheDocument();
  });

  it("renders multiple fares", () => {
    render(
      <FlightFareCard
        data={{
          flights: [
            {
              airline: "Swiss",
              flight_number: "LX1234",
              departure_time: "2026-09-25 08:00",
              arrival_time: "2026-09-25 08:50",
              price: 129,
              currency: "CHF",
              duration_minutes: 50,
              carbon_emissions_grams: null,
            },
            {
              airline: "Helvetic Airways",
              flight_number: "2L123",
              departure_time: "2026-09-25 10:00",
              arrival_time: "2026-09-25 10:45",
              price: 99,
              currency: "CHF",
              duration_minutes: null,
              carbon_emissions_grams: null,
            },
          ],
        }}
      />
    );

    expect(screen.getByText("Swiss")).toBeInTheDocument();
    expect(screen.getByText("Helvetic Airways")).toBeInTheDocument();
    expect(screen.getByText("CHF 99")).toBeInTheDocument();
  });
});
