import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StationBoardCard } from "./StationBoardCard";

const sampleData = {
  station_name: "Bern",
  event_type: "departure",
  events: [
    { line: "IC 8", mode: "rail", direction_name: "Zürich HB", planned_time: "2026-09-24T18:04:00Z", estimated_time: null, platform: "3", delay_minutes: null },
  ],
};

describe("StationBoardCard", () => {
  it("renders the station name and each event's line, direction, and time", () => {
    render(<StationBoardCard data={sampleData} />);

    expect(screen.getByText("Bern")).toBeInTheDocument();
    expect(screen.getByText("IC 8")).toBeInTheDocument();
    expect(screen.getByText(/Zürich HB/)).toBeInTheDocument();
    expect(screen.getByText(/Platform 3/)).toBeInTheDocument();
  });

  it("highlights the selected departure and expands its mode and delay detail", () => {
    render(<StationBoardCard data={sampleData} />);

    const row = screen.getByRole("button", { name: /IC 8/ });
    expect(row).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(row);

    expect(row).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/Mode:/)).toBeInTheDocument();
    expect(screen.getByText(/Delay:/)).toBeInTheDocument();
  });

  it("collapses the departure detail when selected again", () => {
    render(<StationBoardCard data={sampleData} />);

    const row = screen.getByRole("button", { name: /IC 8/ });
    fireEvent.click(row);
    expect(screen.getByText(/Mode:/)).toBeInTheDocument();

    fireEvent.click(row);
    expect(screen.queryByText(/Mode:/)).not.toBeInTheDocument();
  });
});
