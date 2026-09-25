import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN ?? "";

export function RouteMap({ origin, destination, originCoords, destinationCoords, }: {
  origin: string; destination: string; originCoords: { lat: number; lng: number } | null; destinationCoords: { lat: number; lng: number } | null;}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    if (!originCoords || !destinationCoords || !containerRef.current) {
      setUnavailable(true);
      return;
    }

    setUnavailable(false);

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: [originCoords.lng, originCoords.lat],
      zoom: 7,
    });

    map.on("load", () => {
      const bounds = new mapboxgl.LngLatBounds();

      bounds.extend([originCoords.lng, originCoords.lat]);
      bounds.extend([destinationCoords.lng, destinationCoords.lat]);

      map.fitBounds(bounds, {
        padding: 50,
        maxZoom: 12,
      });

      console.log("Adding origin marker:", [
        originCoords.lng,
        originCoords.lat,
      ]);

      console.log("Adding destination marker:", [
        destinationCoords.lng,
        destinationCoords.lat,
      ]);

      new mapboxgl.Marker()
        .setLngLat([originCoords.lng, originCoords.lat])
        .addTo(map);

      new mapboxgl.Marker()
        .setLngLat([destinationCoords.lng, destinationCoords.lat])
        .addTo(map);
    });

    return () => {
      map.remove();
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
