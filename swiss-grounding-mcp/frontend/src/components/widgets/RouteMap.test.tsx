import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { RouteMap } from "./RouteMap";
import mapboxgl from "mapbox-gl";

const createdMaps: Array<{ handlers: Record<string, (event?: unknown) => void>; remove: ReturnType<typeof vi.fn> }> = [];

vi.mock("mapbox-gl", () => {
  class FakeMap {
    handlers: Record<string, (event?: unknown) => void> = {};
    remove = vi.fn();
    addControl = vi.fn();
    constructor() {
      createdMaps.push(this as unknown as { handlers: Record<string, (event?: unknown) => void>; remove: ReturnType<typeof vi.fn> });
    }
    on(event: string, handler: (event?: unknown) => void) {
      this.handlers[event] = handler;
    }
  }
  class FakeMarker {
    setLngLat = vi.fn().mockReturnThis();
    addTo = vi.fn().mockReturnThis();
  }
  return { default: { accessToken: "", Map: FakeMap, Marker: FakeMarker, LngLatBounds: class { extend() {} } } };
});

// RouteMap.tsx sets mapboxgl.accessToken from VITE_MAPBOX_TOKEN once at
// import time, which is empty in this test environment; reset it to a
// truthy value before each test so tests can opt into the "no token"
// case explicitly instead of inheriting whatever ran before them.
beforeEach(() => {
  mapboxgl.accessToken = "test-token";
  createdMaps.length = 0;
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

  it("shows an unavailable message instead of crashing when no access token is configured", () => {
    mapboxgl.accessToken = "";

    render(
      <RouteMap
        origin="Bern"
        destination="Zürich"
        originCoords={{ lat: 46.9481, lng: 7.4474 }}
        destinationCoords={{ lat: 47.3769, lng: 8.5417 }}
      />
    );

    expect(screen.getByText(/map unavailable/i)).toBeInTheDocument();
  });

  it("tears down the mapbox-gl instance when the map reports a runtime error, instead of leaking it", () => {
    render(
      <RouteMap
        origin="Bern"
        destination="Zürich"
        originCoords={{ lat: 46.9481, lng: 7.4474 }}
        destinationCoords={{ lat: 47.3769, lng: 8.5417 }}
      />
    );

    expect(createdMaps).toHaveLength(1);
    const map = createdMaps[0];
    expect(map.remove).not.toHaveBeenCalled();

    // Simulate mapbox-gl reporting a runtime error (e.g. an invalid token,
    // a failed style/tile fetch) after the map was already created.
    act(() => {
      map.handlers.error?.({ error: new Error("boom") });
    });

    expect(map.remove).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/map unavailable/i)).toBeInTheDocument();
  });
});
