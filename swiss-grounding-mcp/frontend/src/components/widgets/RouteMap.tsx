import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN ?? "";

export function RouteMap({ origin, destination, originCoords, destinationCoords, }: {
  origin: string; destination: string; originCoords: { lat: number; lng: number } | null; destinationCoords: { lat: number; lng: number } | null;}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    if (!originCoords || !destinationCoords || !containerRef.current || !mapboxgl.accessToken) {
      setUnavailable(true);
      return;
    }

    setUnavailable(false);

    // Guard the whole SDK interaction: an invalid/expired token or any
    // other mapbox-gl failure must degrade to the "unavailable" message
    // instead of throwing inside an effect, which would otherwise crash
    // the widget tree with no error boundary to catch it.
    let map: mapboxgl.Map | null = null;
    try {
      map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/light-v11",
        center: [originCoords.lng, originCoords.lat],
        zoom: 7,
      });

      map.on("error", (event) => {
        console.error("RouteMap: mapbox-gl reported an error", event.error);
        setUnavailable(true);
      });

      map.on("load", () => {
        if (!map) return;
        const bounds = new mapboxgl.LngLatBounds();

        bounds.extend([originCoords.lng, originCoords.lat]);
        bounds.extend([destinationCoords.lng, destinationCoords.lat]);

        map.fitBounds(bounds, {
          padding: 50,
          maxZoom: 12,
        });

        new mapboxgl.Marker().setLngLat([originCoords.lng, originCoords.lat]).addTo(map);
        new mapboxgl.Marker().setLngLat([destinationCoords.lng, destinationCoords.lat]).addTo(map);
      });
    } catch (error) {
      console.error("RouteMap: failed to initialize mapbox-gl", error);
      setUnavailable(true);
    }

    return () => {
      try {
        map?.remove();
      } catch (error) {
        console.error("RouteMap: failed to tear down mapbox-gl", error);
      }
    };
  }, [originCoords, destinationCoords]);

  if (unavailable) {
    return <p className="p-4 text-xs text-neutral-500">Map unavailable for this location.</p>;
  }

  return (
    <div
      ref={containerRef}
      data-testid="route-map"
      className="h-64 w-full"
      role="img"
      aria-label={`Map from ${origin} to ${destination}`}
    />
  );
}
