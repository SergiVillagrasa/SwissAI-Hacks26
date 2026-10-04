import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { buildRouteWaypointDrafts, useRouteWaypoints } from "./useRouteWaypoints";
import { clearGeocodeCache } from "./geocode";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  clearGeocodeCache();
});

const directConnection = {
  legs: [
    { mode: "rail", line: "IC 8", from_name: "Bern", to_name: "Zürich HB", departure: "2026-09-25T08:00:00Z", arrival: "2026-09-25T09:00:00Z" },
  ],
  origin_latitude: 46.9481,
  origin_longitude: 7.4474,
  destination_latitude: 47.3779,
  destination_longitude: 8.5403,
};

const connectionWithTransfer = {
  legs: [
    { mode: "rail", line: "IC 1", from_name: "Genève", to_name: "Bern", departure: "2026-09-25T07:00:00Z", arrival: "2026-09-25T08:30:00Z" },
    { mode: "rail", line: "IC 8", from_name: "Bern", to_name: "Zürich HB", departure: "2026-09-25T08:40:00Z", arrival: "2026-09-25T09:34:00Z" },
  ],
  origin_latitude: 46.2044,
  origin_longitude: 6.1432,
  destination_latitude: 47.3779,
  destination_longitude: 8.5403,
};

describe("buildRouteWaypointDrafts", () => {
  it("returns just origin and destination for a direct connection", () => {
    const drafts = buildRouteWaypointDrafts(directConnection);

    expect(drafts).toHaveLength(2);
    expect(drafts[0]).toMatchObject({ name: "Bern", kind: "origin", lat: 46.9481, lng: 7.4474 });
    expect(drafts[1]).toMatchObject({ name: "Zürich HB", kind: "destination", lat: 47.3779, lng: 8.5403 });
  });

  it("inserts a via waypoint at the transfer station, without coordinates from the API", () => {
    const drafts = buildRouteWaypointDrafts(connectionWithTransfer);

    expect(drafts).toHaveLength(3);
    expect(drafts[0].kind).toBe("origin");
    expect(drafts[1]).toMatchObject({ name: "Bern", kind: "via", lat: null, lng: null });
    expect(drafts[1].detail).toBe("Change from IC 1 to IC 8");
    expect(drafts[2].kind).toBe("destination");
  });

  it("returns no waypoints when the connection has no legs", () => {
    expect(buildRouteWaypointDrafts({ legs: [], origin_latitude: null, origin_longitude: null, destination_latitude: null, destination_longitude: null })).toEqual([]);
  });
});

describe("useRouteWaypoints", () => {
  it("marks origin/destination waypoints as already located, without geocoding", () => {
    const { result } = renderHook(() => useRouteWaypoints(directConnection));

    expect(result.current.isResolving).toBe(false);
    expect(result.current.waypoints).toEqual([
      expect.objectContaining({ name: "Bern", kind: "origin", coords: { lat: 46.9481, lng: 7.4474 } }),
      expect.objectContaining({ name: "Zürich HB", kind: "destination", coords: { lat: 47.3779, lng: 8.5403 } }),
    ]);
  });

  it("geocodes the via waypoint's coordinates and reports isResolving until it resolves", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ features: [{ center: [7.4474, 46.9481] }] }),
      })
    );

    const { result } = renderHook(() => useRouteWaypoints(connectionWithTransfer));

    expect(result.current.isResolving).toBe(true);
    const viaBeforeResolve = result.current.waypoints.find((w) => w.kind === "via");
    expect(viaBeforeResolve?.coords).toBeNull();

    await waitFor(() => expect(result.current.isResolving).toBe(false));

    const viaAfterResolve = result.current.waypoints.find((w) => w.kind === "via");
    expect(viaAfterResolve?.coords).toEqual({ lat: 46.9481, lng: 7.4474 });
  });

  it("discards a via-stop geocode that falls far outside the origin-destination corridor", async () => {
    // Barcelona -> Zürich via a free-text "Valence" stop that Mapbox
    // mis-resolves to a homonym on another continent: the corridor check
    // must drop it instead of plotting (and distorting the map with) a
    // wildly wrong point.
    const barcelonaToZurichViaValence = {
      legs: [
        { mode: "rail", line: "TGV", from_name: "Barcelona Sants", to_name: "Valence TGV Rhône-Alpes Sud", departure: "2026-09-25T07:00:00Z", arrival: "2026-09-25T10:00:00Z" },
        { mode: "rail", line: "IC", from_name: "Valence TGV Rhône-Alpes Sud", to_name: "Zürich HB", departure: "2026-09-25T10:30:00Z", arrival: "2026-09-25T14:00:00Z" },
      ],
      origin_latitude: 41.3789,
      origin_longitude: 2.1404,
      destination_latitude: 47.3779,
      destination_longitude: 8.5403,
    };

    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        // A homonym city far away (Valencia, Venezuela) rather than Valence, France.
        ok: true,
        json: async () => ({ features: [{ center: [-68.0077, 10.162] }] }),
      })
    );

    const { result } = renderHook(() => useRouteWaypoints(barcelonaToZurichViaValence));

    await waitFor(() => expect(result.current.isResolving).toBe(false));

    const via = result.current.waypoints.find((w) => w.kind === "via");
    expect(via?.coords).toBeNull();
  });

  it("uses the previous confirmed stop as the next lookup's proximity hint (chained geocoding)", async () => {
    const threeLegConnection = {
      legs: [
        { mode: "rail", line: "IC1", from_name: "Genève", to_name: "Bern", departure: "2026-09-25T07:00:00Z", arrival: "2026-09-25T08:30:00Z" },
        { mode: "rail", line: "IC8", from_name: "Bern", to_name: "Olten", departure: "2026-09-25T08:40:00Z", arrival: "2026-09-25T09:10:00Z" },
        { mode: "rail", line: "IR", from_name: "Olten", to_name: "Zürich HB", departure: "2026-09-25T09:20:00Z", arrival: "2026-09-25T09:50:00Z" },
      ],
      origin_latitude: 46.2044,
      origin_longitude: 6.1432,
      destination_latitude: 47.3779,
      destination_longitude: 8.5403,
    };

    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    const seenProximities: Array<string | null> = [];
    const responsesByQuery: Record<string, [number, number]> = {
      Bern: [7.4474, 46.9481],
      Olten: [7.9036, 47.3499],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) => {
        const parsed = new URL(url);
        seenProximities.push(parsed.searchParams.get("proximity"));
        const query = decodeURIComponent(parsed.pathname.split("/").pop()!.replace(".json", ""));
        const center = responsesByQuery[query];
        return { ok: true, json: async () => ({ features: center ? [{ center }] : [] }) };
      })
    );

    const { result } = renderHook(() => useRouteWaypoints(threeLegConnection));

    await waitFor(() => expect(result.current.isResolving).toBe(false));

    // Bern is geocoded with the origin (Genève) as proximity; Olten is
    // then geocoded with Bern's own just-resolved coordinates as
    // proximity, not the static default.
    expect(seenProximities[0]).toBe("6.1432,46.2044");
    expect(seenProximities[1]).toBe("7.4474,46.9481");
  });
});
