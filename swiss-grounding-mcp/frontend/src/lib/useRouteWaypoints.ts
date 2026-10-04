import { useEffect, useMemo, useState } from "react";
import { geocodeCached, isPlausibleCoordinate, type Coordinates } from "./geocode";
import type { RouteWaypoint, WaypointKind } from "../components/widgets/RouteMap";

interface RouteLeg {
  mode: string;
  line: string | null;
  from_name: string;
  to_name: string;
  departure: string | null;
  arrival: string | null;
}

interface RouteConnection {
  legs: RouteLeg[] | undefined;
  origin_latitude: number | null;
  origin_longitude: number | null;
  destination_latitude: number | null;
  destination_longitude: number | null;
}

interface WaypointDraft {
  id: string;
  name: string;
  kind: WaypointKind;
  time: string | null;
  detail: string | null;
  lat: number | null;
  lng: number | null;
}

function legLabel(leg: RouteLeg): string {
  if (leg.mode === "walk" || leg.mode === "foot") return "Walk";
  return leg.line ?? leg.mode;
}

function normalizeStationName(name: string): string {
  return name.trim().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

/** Builds an ordered origin -> via* -> destination waypoint list from a
 * connection's legs. Walking legs are collapsed (a walk to/from a platform
 * isn't a distinct point of interest); every remaining leg boundary becomes
 * a "via" transfer waypoint carrying the incoming line's arrival and the
 * outgoing line's departure, so the popup can describe the actual change.
 * Requested via stops are included even when they aren't a leg boundary. */
export function buildRouteWaypointDrafts(
  connection: RouteConnection,
  viaStopName?: string | null
): WaypointDraft[] {
  const legs = connection.legs ?? [];
  if (legs.length === 0) return [];

  // The trip's overall origin/destination are its true first and last
  // legs -- walk legs included. A walk to/from a platform is still part
  // of getting from the real starting point to the real end point, so
  // excluding it here (as the via-boundary filtering below intentionally
  // does) would report the wrong origin/destination, e.g. the station
  // walked to rather than where the journey actually began.
  const firstLeg = legs[0];
  const lastLeg = legs[legs.length - 1];

  // Via (transfer) waypoints, on the other hand, are only derived from
  // rail-leg boundaries: a walk to/from a platform isn't a distinct point
  // of interest worth its own marker.
  const railLegs = legs.filter((leg) => leg.mode !== "walk" && leg.mode !== "foot");
  const effectiveLegs = railLegs.length > 0 ? railLegs : legs;

  const drafts: WaypointDraft[] = [
    {
      id: `origin:${firstLeg.from_name}`,
      name: firstLeg.from_name,
      kind: "origin",
      time: firstLeg.departure,
      detail: legLabel(firstLeg),
      lat: connection.origin_latitude,
      lng: connection.origin_longitude,
    },
  ];

  for (let i = 0; i < effectiveLegs.length - 1; i += 1) {
    const arriving = effectiveLegs[i];
    const departing = effectiveLegs[i + 1];
    drafts.push({
      id: `via:${arriving.to_name}:${i}`,
      name: arriving.to_name,
      kind: "via",
      time: arriving.arrival,
      detail: `Change from ${legLabel(arriving)} to ${legLabel(departing)}`,
      lat: null,
      lng: null,
    });
  }

  drafts.push({
    id: `destination:${lastLeg.to_name}`,
    name: lastLeg.to_name,
    kind: "destination",
    time: lastLeg.arrival,
    detail: legLabel(lastLeg),
    lat: connection.destination_latitude,
    lng: connection.destination_longitude,
  });

  if (
    viaStopName?.trim() &&
    !drafts.some((draft) => normalizeStationName(draft.name) === normalizeStationName(viaStopName))
  ) {
    drafts.splice(drafts.length - 1, 0, {
      id: `via-requested:${viaStopName}`,
      name: viaStopName,
      kind: "via",
      time: null,
      detail: "Requested stop on the way",
      lat: null,
      lng: null,
    });
  }

  return drafts;
}

/** Turns a connection into map-ready waypoints, geocoding (and caching) the
 * name of any waypoint the server didn't already give coordinates for -
 * today that's every intermediate/transfer stop, since the API only
 * resolves the overall origin and destination. Returns `isResolving: true`
 * while any of those lookups are still in flight. */
export function useRouteWaypoints(connection: RouteConnection, viaStopName?: string | null): {
  waypoints: RouteWaypoint[];
  isResolving: boolean;
} {
  const drafts = useMemo(() => buildRouteWaypointDrafts(connection, viaStopName), [connection, viaStopName]);
  const [resolved, setResolved] = useState<Record<string, Coordinates | null>>({});
  const [resolvingIds, setResolvingIds] = useState<ReadonlySet<string>>(new Set());

  useEffect(() => {
    const unresolved = drafts.filter((draft) => draft.lat === null || draft.lng === null);
    if (unresolved.length === 0) {
      // Clear any resolvingIds left over from a previous draft set (e.g.
      // the user switched to a connection whose via stops are all already
      // located) -- otherwise this effect returns without ever touching
      // resolvingIds again, and isResolving stays stuck true forever.
      setResolvingIds((current) => (current.size > 0 ? new Set() : current));
      return;
    }

    let cancelled = false;
    setResolvingIds(new Set(unresolved.map((draft) => draft.id)));

    // Resolve every unresolved stop concurrently (each waypoint's
    // coordinates are independent of the others, so there's no reason to
    // wait on one lookup before starting the next) rather than serializing
    // them one at a time. Each entry still updates `resolved`/
    // `resolvingIds` for its own draft.id as soon as it individually
    // settles, so the UI reflects whichever stops resolve first.
    Promise.all(
      unresolved.map(async (draft) => {
        const coords = await geocodeCached(draft.name);
        if (cancelled) return;
        // Only guards against a wildly wrong match (a different continent);
        // legitimate cross-border stations (Barcelona, Lyon, Milano, ...)
        // must still resolve, so this is intentionally not restricted to
        // Switzerland alone.
        const safeCoords = coords && isPlausibleCoordinate(coords) ? coords : null;
        if (coords && !safeCoords) {
          console.warn(`useRouteWaypoints: discarding implausible geocode result for "${draft.name}"`, coords);
        }
        setResolved((current) => ({ ...current, [draft.id]: safeCoords }));
        setResolvingIds((current) => {
          const next = new Set(current);
          next.delete(draft.id);
          return next;
        });
      })
    );

    return () => {
      cancelled = true;
    };
  }, [drafts]);

  const waypoints = useMemo<RouteWaypoint[]>(
    () =>
      drafts.map((draft) => {
        // Origin/destination coordinates come straight from the server's
        // own station resolution and are always trusted, even abroad
        // (Barcelona Sants, Paris Gare de Lyon, ...); only the free-text
        // geocoded via-stops (in `resolved`) were sanity-checked above.
        const apiCoords = draft.lat !== null && draft.lng !== null ? { lat: draft.lat, lng: draft.lng } : null;
        return {
          id: draft.id,
          name: draft.name,
          kind: draft.kind,
          time: draft.time,
          detail: draft.detail,
          coords: apiCoords ?? resolved[draft.id] ?? null,
        };
      }),
    [drafts, resolved]
  );

  return { waypoints, isResolving: resolvingIds.size > 0 };
}
