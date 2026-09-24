import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DisruptionsCard } from "./DisruptionsCard";

describe("DisruptionsCard", () => {
  it("renders each disruption's title, severity, and affected lines", () => {
    render(
      <DisruptionsCard
        data={{
          disruptions: [
            {
              id: "1",
              title: "Track work",
              description: "Reduced service between Bern and Thun.",
              severity: "moderate",
              start_time: "2026-09-24T06:00:00Z",
              end_time: "2026-09-24T20:00:00Z",
              status: "active",
              affected_lines: ["S1"],
              affected_stops: ["Bern"],
            },
          ],
        }}
      />
    );

    expect(screen.getByText("Track work")).toBeInTheDocument();
    expect(screen.getByText(/moderate/i)).toBeInTheDocument();
    expect(screen.getByText("S1")).toBeInTheDocument();
  });
});
