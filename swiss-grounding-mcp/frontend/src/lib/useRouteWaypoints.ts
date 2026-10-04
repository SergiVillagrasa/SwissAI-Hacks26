import { useEffect, useMemo, useState } from "react";
import { geocodeCached, isPlausibleCoordinate, isWithinCorridor, type Coordinates } from "./geocode";
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

/** Builds an ordered origin -> via* -> destination waypoint list from a
 * connection's legs. Walking legs are collapsed (a walk to/from a platform
 * isn't a distinct point of interest); every remaining leg boundary becomes
 * a "via" transfer waypoint carrying the incoming line's arrival and the
 * outgoing line's departure, so the popup can describe the actual change. */
export function buildRouteWaypointDrafts(connection: RouteConnection): WaypointDraft[] {
  const legs = connection.legs ?? [];
  if (legs.length === 0) return [];

  const railLegs = legs.filter((leg) => leg.mode !== "walk" && leg.mode !== "foot");
  const effectiveLegs = railLegs.length > 0 ? railLegs : legs;

  const originLeg = effectiveLegs[0];
  const destinationLeg = effectiveLegs[effectiveLegs.length - 1];

  const drafts: WaypointDraft[] = [
    {
      id: `origin:${originLeg.from_name}`,
      name: originLeg.from_name,
      kind: "origin",
      time: originLeg.departure,
      detail: legLabel(originLeg),
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
    id: `destination:${destinationLeg.to_name}`,
    name: destinationLeg.to_name,
    kind: "destination",
    time: destinationLeg.arrival,
    detail: legLabel(destinationLeg),
    lat: connection.destination_latitude,
    lng: connection.destination_longitude,
  });

  return drafts;
}

/** Turns a connection into map-ready waypoints, geocoding (and caching) the
 * name of any waypoint the server didn't already give coordinates for -
 * today that's every intermediate/transfer stop, since the API only
 * resolves the overall origin and destination. Returns `isResolving: true`
 * while any of those lookups are still in flight. */
export function useRouteWaypoints(connection: RouteConnection): {
  waypoints: RouteWaypoint[];
  isResolving: boolean;
} {
  const drafts = useMemo(() => buildRouteWaypointDrafts(connection), [connection]);
  const [resolved, setResolved] = useState<Record<string, Coordinates | null>>({});
  const [resolvingIds, setResolvingIds] = useState<ReadonlySet<string>>(new Set());

  // The server-resolved origin/destination coordinates define this
  // itinerary's corridor; memoized on the primitive lat/lng values (not a
  // fresh object each render) so the geocoding effect below doesn't
  // re-fire every time this hook's own state updates.
  const origin = useMemo<Coordinates | null>(
    () =>
      connection.origin_latitude !== null && connection.origin_longitude !== null
        ? { lat: connection.origin_latitude, lng: connection.origin_longitude }
        : null,
    [connection.origin_latitude, connection.origin_longitude]
  );
  const destination = useMemo<Coordinates | null>(
    () =>
      connection.destination_latitude !== null && connection.destination_longitude !== null
        ? { lat: connection.destination_latitude, lng: connection.destination_longitude }
        : null,
    [connection.destination_latitude, connection.destination_longitude]
  );

  useEffect(() => {
    const unresolved = drafts.filter((draft) => draft.lat === null || draft.lng === null);
    if (unresolved.length === 0) return;

    let cancelled = false;
    setResolvingIds(new Set(unresolved.map((draft) => draft.id)));

    // Resolve one stop at a time, in itinerary order, instead of firing
    // every lookup independently against a single static proximity: each
    // step uses the previous *confirmed* stop (falling back to the known
    // origin for the first one) as Mapbox's proximity hint, so a chain of
    // transfers converges on the real corridor instead of each being
    // geocoded in isolation.
    (async () => {
      let anchor: Coordinates | null = origin;
      for (const draft of unresolved) {
        if (cancelled) return;
        const coords = await geocodeCached(draft.name, anchor ? { proximity: anchor } : undefined);
        if (cancelled) return;

        // Reject a match that's wildly off the known origin -> destination
        // corridor (e.g. Mapbox resolving a bare "Valence" to a homonym on
        // another continent) rather than plotting it in the wrong place or
        // distorting the drawn route. Without both ends known, fall back
        // to a loose continent-level sanity check.
        const plausible =
          coords == null
            ? false
            : origin && destination
              ? isWithinCorridor(coords, origin, destination)
              : isPlausibleCoordinate(coords);
        const safeCoords = plausible ? coords : null;
        if (coords && !safeCoords) {
          console.warn(`useRouteWaypoints: discarding implausible geocode result for "${draft.name}"`, coords);
        }

        setResolved((current) => ({ ...current, [draft.id]: safeCoords }));
        setResolvingIds((current) => {
          const next = new Set(current);
          next.delete(draft.id);
          return next;
        });

        // Only chain forward from a confirmed-good match; a rejected one
        // must not drag the next lookup's proximity off-course too.
        if (safeCoords) anchor = safeCoords;
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [drafts, origin, destination]);

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

  if (import.meta.env.DEV) {
    console.log("WAYPOINTS:", waypoints);
  }

  return { waypoints, isResolving: resolvingIds.size > 0 };
}
