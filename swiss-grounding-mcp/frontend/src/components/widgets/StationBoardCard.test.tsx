import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StationBoardCard } from "./StationBoardCard";

describe("StationBoardCard", () => {
  it("renders the station name and each event's line, direction, and time", () => {
    render(
      <StationBoardCard
        data={{
          station_name: "Bern",
          event_type: "departure",
          events: [
            { line: "IC 8", mode: "rail", direction_name: "Zürich HB", planned_time: "2026-09-24T18:04:00Z", estimated_time: null, platform: "3", delay_minutes: null },
          ],
        }}
      />
    );

    expect(screen.getByText("Bern")).toBeInTheDocument();
    expect(screen.getByText("IC 8")).toBeInTheDocument();
    expect(screen.getByText(/Zürich HB/)).toBeInTheDocument();
    expect(screen.getByText(/Platform 3/)).toBeInTheDocument();
  });
});
