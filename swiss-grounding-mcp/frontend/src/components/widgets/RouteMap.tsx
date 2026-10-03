import { useEffect, useMemo, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { isWithinSwitzerland } from "../../lib/geocode";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN ?? "";

export type WaypointKind = "origin" | "via" | "destination";

export interface RouteWaypoint {
  /** Stable identity for React keys and marker/popup bookkeeping. */
  id: string;
  name: string;
  kind: WaypointKind;
  /** null while the station's position is still being geocoded or is unresolved. */
  coords: { lat: number; lng: number } | null;
  /** ISO departure/arrival time shown in the marker's popup. */
  time?: string | null;
  /** Free-text line/transfer info shown in the marker's popup. */
  detail?: string | null;
}

interface RouteMapProps {
  waypoints: RouteWaypoint[];
  /** True while at least one waypoint's coordinates are still being geocoded. */
  isResolving?: boolean;
}

const MARKER_COLOR: Record<WaypointKind, string> = {
  origin: "#16a34a", // green: departure
  via: "#f59e0b", // amber: intermediate stop / transfer
  destination: "#dc2626", // red: arrival
};

const POPUP_LABEL: Record<WaypointKind, string> = {
  origin: "Departure",
  via: "Transfer",
  destination: "Arrival",
};

const ROUTE_LINE_SOURCE_ID = "route-map-line";
const ROUTE_LINE_LAYER_ID = "route-map-line-layer";

function formatPopupTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function popupHtml(waypoint: RouteWaypoint): string {
  const time = formatPopupTime(waypoint.time);
  const rows = [
    time ? `${POPUP_LABEL[waypoint.kind]}: <strong>${time}</strong>` : null,
    waypoint.detail ? escapeHtml(waypoint.detail) : null,
  ].filter((row): row is string => row !== null);

  return (
    `<div style="font-family:inherit;min-width:150px;">` +
    `<div style="font-weight:600;font-size:13px;margin-bottom:4px;">${escapeHtml(waypoint.name)}</div>` +
    rows.map((row) => `<div style="font-size:12px;color:#475569;">${row}</div>`).join("") +
    `</div>`
  );
}

/** Renders an interactive Mapbox map for a single itinerary: color-coded
 * origin/via/destination markers with informational popups, a highlighted
 * line connecting them in order (so a transfer point is visibly on the
 * route, not just implied), zoom/rotate controls, and a "Fit route" button
 * that re-centers on demand. Degrades to an inline message - without
 * unmounting the map container - when there is no usable location data or
 * mapbox-gl itself cannot initialize (e.g. a missing access token). */
export function RouteMap({ waypoints, isResolving = false }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  const [mapReady, setMapReady] = useState(false);
  const [mapFailed, setMapFailed] = useState(false);

  // Itineraries may legitimately start or transfer abroad (Barcelona
  // Sants, Lyon, Milano, ...) on a Swiss-connected route, so this only
  // drops waypoints without any coordinates - it does not restrict to
  // Switzerland. Coordinate plausibility is already checked upstream in
  // useRouteWaypoints/geocode.
  const located = useMemo(
    () => waypoints.filter((w): w is RouteWaypoint & { coords: { lat: number; lng: number } } => w.coords !== null),
    [waypoints]
  );

  // Business rule: this app is scoped to Swiss and Swiss-connected travel.
  // A route where every located point falls outside Switzerland (e.g. a
  // purely foreign Madrid -> Barcelona hop) isn't something this map should
  // render, even if we happen to have coordinates for it. Only decide this
  // once resolving has finished, so an in-scope via-stop that's still being
  // geocoded doesn't cause a premature "out of scope" flash.
  const outOfScope = !isResolving && located.length > 0 && !located.some((w) => isWithinSwitzerland(w.coords));
  const mapWaypoints = useMemo(() => (outOfScope ? [] : located), [outOfScope, located]);

  function fitRoute() {
    const map = mapRef.current;
    if (!map || mapWaypoints.length === 0) return;
    if (mapWaypoints.length === 1) {
      map.flyTo({ center: [mapWaypoints[0].coords.lng, mapWaypoints[0].coords.lat], zoom: 11 });
      return;
    }
    const bounds = new mapboxgl.LngLatBounds();
    mapWaypoints.forEach((waypoint) => bounds.extend([waypoint.coords.lng, waypoint.coords.lat]));
    map.fitBounds(bounds, { padding: 40, maxZoom: 13, duration: 500 });
  }

  // Mount once: create the map, its navigation controls, and the (initially
  // empty) route-line source/layer. Waypoint data is applied by the effect
  // below so switching journeys updates markers/line/bounds in place
  // instead of tearing down and rebuilding the whole map.
  useEffect(() => {
    if (!containerRef.current || !mapboxgl.accessToken) {
      setMapFailed(true);
      return;
    }

    let map: mapboxgl.Map | null = null;
    try {
      map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/light-v11",
        center: [8.2275, 46.8182], // Switzerland, used until waypoints resolve
        zoom: 6,
        // Newer Mapbox styles default to the 3D "globe" projection; force
        // the flat Mercator projection so the map reads as a normal 2D map.
        projection: { name: "mercator" },
      });
      mapRef.current = map;
      map.addControl(new mapboxgl.NavigationControl({ showCompass: true }), "top-right");

      map.on("error", (event) => {
        console.error("RouteMap: mapbox-gl reported an error", event.error);
        setMapFailed(true);
      });

      map.on("load", () => {
        if (!map) return;
        map.addSource(ROUTE_LINE_SOURCE_ID, {
          type: "geojson",
          data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [] } },
        });
        map.addLayer({
          id: ROUTE_LINE_LAYER_ID,
          type: "line",
          source: ROUTE_LINE_SOURCE_ID,
          paint: { "line-color": "#2563eb", "line-width": 4, "line-opacity": 0.85 },
        });
        setMapReady(true);
      });
    } catch (error) {
      console.error("RouteMap: failed to initialize mapbox-gl", error);
      setMapFailed(true);
    }

    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      try {
        map?.remove();
      } catch (error) {
        console.error("RouteMap: failed to tear down mapbox-gl", error);
      }
      mapRef.current = null;
      setMapReady(false);
    };
  }, []);

  // Update markers, the route line, and the viewport whenever the resolved
  // waypoints change (new journey selected, or a geocode lookup resolves).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = mapWaypoints.map((waypoint) =>
      new mapboxgl.Marker({ color: MARKER_COLOR[waypoint.kind] })
        .setLngLat([waypoint.coords.lng, waypoint.coords.lat])
        .setPopup(new mapboxgl.Popup({ offset: 18 }).setHTML(popupHtml(waypoint)))
        .addTo(map)
    );

    const source = map.getSource(ROUTE_LINE_SOURCE_ID) as mapboxgl.GeoJSONSource | undefined;
    source?.setData({
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: mapWaypoints.map((waypoint) => [waypoint.coords.lng, waypoint.coords.lat]),
      },
    });

    fitRoute();
    // fitRoute reads mapRef/mapWaypoints by closure; re-running this effect
    // on waypoint/readiness changes is the intended trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapWaypoints, mapReady]);

  const hasLocatedWaypoint = mapWaypoints.length > 0;

  return (
    <div className="relative h-64 w-full overflow-hidden">
      <div ref={containerRef} data-testid="route-map" className="h-full w-full" role="img" aria-label="Route map" />
      {mapFailed && (
        <div
          data-testid="route-map-unavailable"
          className="absolute inset-0 flex items-center justify-center bg-white/85 p-4 text-center text-xs text-neutral-500"
        >
          Map unavailable for this location.
        </div>
      )}
      {!mapFailed && outOfScope && (
        <div
          data-testid="route-map-out-of-scope"
          className="absolute inset-0 flex items-center justify-center bg-white/75 p-4 text-center text-xs text-neutral-500"
        >
          This route is outside the Swiss transport network.
        </div>
      )}
      {!mapFailed && !outOfScope && !hasLocatedWaypoint && !isResolving && (
        <div
          data-testid="route-map-no-data"
          className="absolute inset-0 flex items-center justify-center bg-white/75 p-4 text-center text-xs text-neutral-500"
        >
          No location data available for this route.
        </div>
      )}
      {!mapFailed && isResolving && (
        <div
          data-testid="route-map-resolving"
          className="absolute left-2 top-2 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-medium text-neutral-600 shadow-glass-sm"
        >
          Locating stations…
        </div>
      )}
      {!mapFailed && hasLocatedWaypoint && (
        <button
          type="button"
          onClick={fitRoute}
          data-testid="route-map-fit"
          aria-label="Fit route"
          className="absolute bottom-2 right-2 rounded-full bg-white/90 px-3 py-1.5 text-[11px] font-medium text-accent-ink shadow-glass-sm transition duration-200 hover:bg-white"
        >
          Fit route
        </button>
      )}
    </div>
  );
}
