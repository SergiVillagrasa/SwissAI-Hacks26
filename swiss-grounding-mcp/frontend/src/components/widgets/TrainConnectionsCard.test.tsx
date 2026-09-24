import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TrainConnectionsCard } from "./TrainConnectionsCard";

vi.mock("mapbox-gl", () => {
  class FakeMap {
    on = vi.fn();
    remove = vi.fn();
    addControl = vi.fn();
  }
  class FakeMarker {
    setLngLat = vi.fn().mockReturnThis();
    addTo = vi.fn().mockReturnThis();
  }
  return { default: { accessToken: "", Map: FakeMap, Marker: FakeMarker } };
});

const sampleData = {
  connections: [
    {
      departure: "2026-09-24T18:04:00Z",
      arrival: "2026-09-24T19:47:00Z",
      duration_minutes: 103,
      changes: 1,
      legs: [
        { mode: "rail", line: "IC 8", from_name: "Bern", to_name: "Zürich HB", departure: "2026-09-24T18:04:00Z", arrival: "2026-09-24T18:57:00Z" },
      ],
    },
  ],
  provenance: { source: "opentransportdata.swiss OJP 2.0", source_url: "https://opentransportdata.swiss", retrieved_at: "2026-09-24T18:03:12Z" },
};

describe("TrainConnectionsCard", () => {
  it("renders one selectable option per connection with its citation", () => {
    render(<TrainConnectionsCard data={sampleData} onSelect={() => {}} />);

    expect(screen.getByText(/103 min/)).toBeInTheDocument();
    expect(screen.getByText(/1 change/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /opentransportdata.swiss/i })).toHaveAttribute(
      "href",
      "https://opentransportdata.swiss"
    );
  });

  it("calls onSelect with the chosen connection", () => {
    const onSelect = vi.fn();
    render(<TrainConnectionsCard data={sampleData} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: /103 min/ }));

    expect(onSelect).toHaveBeenCalledWith(sampleData.connections[0]);
  });
});
