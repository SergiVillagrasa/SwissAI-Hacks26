import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RouteMap, type RouteWaypoint } from "./RouteMap";
import mapboxgl from "mapbox-gl";

const addedMarkers: Array<{ color: string; popupHtml: string | null; lngLat: [number, number] | null }> = [];

vi.mock("mapbox-gl", () => {
  class FakePopup {
    private html: string | null = null;
    setHTML(html: string) {
      this.html = html;
      return this;
    }
    getHTML() {
      return this.html;
    }
  }
  class FakeMarker {
    private color: string;
    private lngLat: [number, number] | null = null;
    private popup: FakePopup | null = null;
    constructor(options: { color: string }) {
      this.color = options.color;
    }
    setLngLat(lngLat: [number, number]) {
      this.lngLat = lngLat;
      return this;
    }
    setPopup(popup: FakePopup) {
      this.popup = popup;
      return this;
    }
    addTo() {
      addedMarkers.push({ color: this.color, popupHtml: this.popup?.getHTML() ?? null, lngLat: this.lngLat });
      return this;
    }
    remove() {}
  }
  class FakeSource {
    setData = vi.fn();
  }
  class FakeMap {
    private handlers: Record<string, () => void> = {};
    private source = new FakeSource();
    on(event: string, handler: () => void) {
      this.handlers[event] = handler;
      if (event === "load") handler();
    }
    addControl() {}
    addSource() {}
    addLayer() {}
    getSource() {
      return this.source;
    }
    fitBounds = vi.fn();
    flyTo = vi.fn();
    remove = vi.fn();
  }
  class FakeLngLatBounds {
    extend() {
      return this;
    }
  }
  return {
    default: {
      accessToken: "test-token",
      Map: FakeMap,
      Marker: FakeMarker,
      Popup: FakePopup,
      NavigationControl: class {},
      LngLatBounds: FakeLngLatBounds,
    },
  };
});

// RouteMap.tsx sets mapboxgl.accessToken from VITE_MAPBOX_TOKEN once at
// import time, which is empty in this test environment; reset it before
// each test so cases can opt into the "no token" scenario explicitly.
beforeEach(() => {
  mapboxgl.accessToken = "test-token";
  addedMarkers.length = 0;
});

afterEach(() => vi.restoreAllMocks());

const originWaypoint: RouteWaypoint = {
  id: "origin:Bern",
  name: "Bern",
  kind: "origin",
  coords: { lat: 46.9481, lng: 7.4474 },
  time: "2026-09-25T08:00:00Z",
  detail: "IC 1",
};

const viaWaypoint: RouteWaypoint = {
  id: "via:Olten:0",
  name: "Olten",
  kind: "via",
  coords: { lat: 47.3499, lng: 7.9036 },
  time: "2026-09-25T08:30:00Z",
  detail: "Change from IC 1 to IC 8",
};

const destinationWaypoint: RouteWaypoint = {
  id: "destination:Zürich HB",
  name: "Zürich HB",
  kind: "destination",
  coords: { lat: 47.3779, lng: 8.5403 },
  time: "2026-09-25T09:00:00Z",
  detail: "IC 8",
};

// A cross-border itinerary: origin in Spain, destination in Switzerland.
// At least one point (Zürich HB) is Swiss, so this must render normally.
const barcelonaOriginWaypoint: RouteWaypoint = {
  id: "origin:Barcelona Sants",
  name: "Barcelona Sants",
  kind: "origin",
  coords: { lat: 41.3789, lng: 2.1404 },
  time: "2026-09-25T08:00:00Z",
  detail: "TGV",
};

// A purely foreign hop: both ends outside Switzerland.
const madridOriginWaypoint: RouteWaypoint = {
  id: "origin:Madrid",
  name: "Madrid",
  kind: "origin",
  coords: { lat: 40.4168, lng: -3.7038 },
  time: "2026-09-25T08:00:00Z",
  detail: "AVE",
};
const barcelonaDestinationWaypoint: RouteWaypoint = {
  id: "destination:Barcelona Sants",
  name: "Barcelona Sants",
  kind: "destination",
  coords: { lat: 41.3789, lng: 2.1404 },
  time: "2026-09-25T09:00:00Z",
  detail: "AVE",
};

describe("RouteMap", () => {
  it("shows a no-data message without unmounting the map container when no waypoint has coordinates", async () => {
    render(<RouteMap waypoints={[{ ...originWaypoint, coords: null }]} />);

    expect(screen.getByTestId("route-map")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("route-map-no-data")).toBeInTheDocument());
  });

  it("shows the resolving indicator instead of the no-data message while geocoding is in flight", () => {
    render(<RouteMap waypoints={[{ ...originWaypoint, coords: null }]} isResolving />);

    expect(screen.getByTestId("route-map-resolving")).toBeInTheDocument();
    expect(screen.queryByTestId("route-map-no-data")).not.toBeInTheDocument();
  });

  it("renders a color-coded marker with a popup for each located waypoint", async () => {
    render(<RouteMap waypoints={[originWaypoint, viaWaypoint, destinationWaypoint]} />);

    await waitFor(() => expect(addedMarkers).toHaveLength(3));
    expect(addedMarkers.map((m) => m.color)).toEqual(["#16a34a", "#f59e0b", "#dc2626"]);
    expect(addedMarkers[0].popupHtml).toContain("Bern");
    expect(addedMarkers[0].popupHtml).toContain("Departure");
    expect(addedMarkers[1].popupHtml).toContain("Olten");
    expect(addedMarkers[1].popupHtml).toContain("Change from IC 1 to IC 8");
    expect(addedMarkers[2].popupHtml).toContain("Zürich HB");
    expect(addedMarkers[2].popupHtml).toContain("Arrival");
  });

  it("exposes a Fit route button once at least one waypoint is located", async () => {
    render(<RouteMap waypoints={[originWaypoint, destinationWaypoint]} />);

    const fitButton = await screen.findByTestId("route-map-fit");
    expect(fitButton).toBeInTheDocument();
    fireEvent.click(fitButton);
  });

  it("shows an unavailable message instead of crashing when no access token is configured", () => {
    mapboxgl.accessToken = "";

    render(<RouteMap waypoints={[originWaypoint, destinationWaypoint]} />);

    expect(screen.getByTestId("route-map-unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("route-map")).toBeInTheDocument();
  });

  it("renders a cross-border itinerary normally when at least one point is in Switzerland", async () => {
    render(<RouteMap waypoints={[barcelonaOriginWaypoint, destinationWaypoint]} />);

    await waitFor(() => expect(addedMarkers).toHaveLength(2));
    expect(screen.queryByTestId("route-map-out-of-scope")).not.toBeInTheDocument();
    expect(await screen.findByTestId("route-map-fit")).toBeInTheDocument();
  });

  it("shows an out-of-scope message and skips drawing markers when no point is in Switzerland", async () => {
    render(<RouteMap waypoints={[madridOriginWaypoint, barcelonaDestinationWaypoint]} />);

    await waitFor(() => expect(screen.getByTestId("route-map-out-of-scope")).toBeInTheDocument());
    expect(addedMarkers).toHaveLength(0);
    expect(screen.queryByTestId("route-map-fit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("route-map-no-data")).not.toBeInTheDocument();
  });

  it("does not flash the out-of-scope message while a via-stop is still resolving", () => {
    render(<RouteMap waypoints={[madridOriginWaypoint, { ...viaWaypoint, coords: null }]} isResolving />);

    expect(screen.queryByTestId("route-map-out-of-scope")).not.toBeInTheDocument();
    expect(screen.getByTestId("route-map-resolving")).toBeInTheDocument();
  });
});
