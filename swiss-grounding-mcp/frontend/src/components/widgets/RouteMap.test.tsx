import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { RouteMap } from "./RouteMap";

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
  it("shows an unavailable message when coordinates are missing", () => {
    render(
      <RouteMap
        origin="Bern"
        destination="Nowhereville"
        originCoords={null}
        destinationCoords={null}
      />
    );

    expect(screen.getByText(/map unavailable/i)).toBeInTheDocument();
  });

  it("renders the map container when both endpoint coordinates are available", () => {
    render(
      <RouteMap
        origin="Bern"
        destination="Zürich"
        originCoords={{ lat: 46.9481, lng: 7.4474 }}
        destinationCoords={{ lat: 47.3769, lng: 8.5417 }}
      />
    );

    expect(screen.getByTestId("route-map")).toBeInTheDocument();
  });
});
