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
      origin_latitude: 46.948,
      origin_longitude: 7.4474,
      destination_latitude: 47.3779,
      destination_longitude: 8.5403,
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

  it("shows the applied ordering badge when sorted by soonest departure", () => {
    render(<TrainConnectionsCard data={{ ...sampleData, sorted_by: "departure" }} onSelect={() => {}} />);

    expect(screen.getByTestId("sort-badge")).toHaveTextContent("Sorted by: Soonest departure");
  });

  it("renders no ordering badge when no sorting was applied", () => {
    render(<TrainConnectionsCard data={sampleData} onSelect={() => {}} />);

    expect(screen.queryByTestId("sort-badge")).not.toBeInTheDocument();
  });

  it("shows the via badge when the trip passes through an intermediate station", () => {
    render(<TrainConnectionsCard data={{ ...sampleData, via_stop_name: "Bern" }} onSelect={() => {}} />);

    expect(screen.getByTestId("via-badge")).toHaveTextContent("Via Bern");
  });

  it("renders no via badge when no intermediate station was requested", () => {
    render(<TrainConnectionsCard data={sampleData} onSelect={() => {}} />);

    expect(screen.queryByTestId("via-badge")).not.toBeInTheDocument();
  });

  it("uses a real space between 'Via' and the station name", () => {
    render(<TrainConnectionsCard data={{ ...sampleData, via_stop_name: "Bern" }} onSelect={() => {}} />);

    expect(screen.getByTestId("via-badge").textContent).toBe("Via Bern");
  });

  it("expands the leg detail, transfer stations, and SBB booking link on selection", () => {
    render(<TrainConnectionsCard data={sampleData} onSelect={() => {}} />);

    const row = screen.getByRole("button", { name: /103 min/ });
    expect(row).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(row);

    expect(row).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/IC 8/)).toBeInTheDocument();
    const bookLink = screen.getByRole("link", { name: /book on sbb/i });
    expect(bookLink).toHaveAttribute("href", expect.stringContaining("von=Bern"));
    expect(bookLink).toHaveAttribute("href", expect.stringContaining("nach=Z%C3%BCrich+HB"));
  });

  it("renders departure and arrival times in Swiss local time, not the browser/runtime timezone", () => {
    // The connection's departure is 2026-09-24T18:04:00Z (UTC). In
    // Europe/Zurich (CEST, UTC+2) that is 20:04 -- the card must show the
    // Swiss time regardless of what timezone the test runner itself uses.
    render(<TrainConnectionsCard data={sampleData} onSelect={() => {}} />);

    expect(screen.getByText(/20:04 → 21:47/)).toBeInTheDocument();
  });

  it("builds the SBB deep link date from Swiss local time, not the raw UTC date", () => {
    const lateNightData = {
      ...sampleData,
      connections: [
        {
          ...sampleData.connections[0],
          departure: "2026-09-24T23:10:00Z",
          arrival: "2026-09-25T00:03:00Z",
          legs: [
            {
              mode: "rail",
              line: "IC 8",
              from_name: "Bern",
              to_name: "Zürich HB",
              departure: "2026-09-24T23:10:00Z",
              arrival: "2026-09-25T00:03:00Z",
            },
          ],
        },
      ],
    };
    render(<TrainConnectionsCard data={lateNightData} onSelect={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: /103 min/ }));

    const bookLink = screen.getByRole("link", { name: /book on sbb/i });
    // 23:10 UTC is already 2026-09-25 in Europe/Zurich (CEST, UTC+2).
    expect(bookLink).toHaveAttribute("href", expect.stringContaining("date=2026-09-25"));
  });

  it("collapses the detail when the same connection is selected again", () => {
    render(<TrainConnectionsCard data={sampleData} onSelect={() => {}} />);

    const row = screen.getByRole("button", { name: /103 min/ });
    fireEvent.click(row);
    expect(row).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(row);
    expect(row).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: /book on sbb/i })).not.toBeInTheDocument();
  });
});
