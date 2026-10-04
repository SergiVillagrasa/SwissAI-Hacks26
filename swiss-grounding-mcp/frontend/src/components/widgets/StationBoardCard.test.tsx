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

  it("renders the planned time in Swiss local time, not the browser/runtime timezone", () => {
    // planned_time is 2026-09-24T18:04:00Z (UTC); in Europe/Zurich (CEST,
    // UTC+2) that is 20:04, regardless of the test runner's own timezone.
    render(<StationBoardCard data={sampleData} />);

    expect(screen.getByText("20:04")).toBeInTheDocument();
  });

  it("highlights the selected departure and expands its mode and delay detail", () => {
    render(<StationBoardCard data={sampleData} />);

    const row = screen.getByRole("button", { name: /IC 8/ });
    expect(row).toHaveAttribute("aria-expanded", "false");
    expect(row.className).not.toContain("ring-blue-400");

    fireEvent.click(row);

    expect(row).toHaveAttribute("aria-expanded", "true");
    // "Highlights" the row visually (glassRowSelected), not just marking
    // it expanded for assistive tech.
    expect(row.className).toContain("ring-blue-400");
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
