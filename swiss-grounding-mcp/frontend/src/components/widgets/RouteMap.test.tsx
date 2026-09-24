import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { RouteMap } from "./RouteMap";
import * as geocodeModule from "../../lib/geocode";

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

afterEach(() => vi.restoreAllMocks());

describe("RouteMap", () => {
  it("shows an unavailable message when a location cannot be geocoded", async () => {
    vi.spyOn(geocodeModule, "geocode").mockResolvedValue(null);

    render(<RouteMap origin="Bern" destination="Nowhereville" />);

    await waitFor(() => expect(screen.getByText(/map unavailable/i)).toBeInTheDocument());
  });

  it("renders the map container once both endpoints resolve", async () => {
    vi.spyOn(geocodeModule, "geocode")
      .mockResolvedValueOnce({ lat: 46.9481, lng: 7.4474 })
      .mockResolvedValueOnce({ lat: 47.3769, lng: 8.5417 });

    render(<RouteMap origin="Bern" destination="Zürich" />);

    await waitFor(() => expect(screen.getByTestId("route-map")).toBeInTheDocument());
  });
});
