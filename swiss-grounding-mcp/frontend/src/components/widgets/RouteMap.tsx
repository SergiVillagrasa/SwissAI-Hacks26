import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { geocode } from "../../lib/geocode";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN ?? "";

export function RouteMap({ origin, destination }: { origin: string; destination: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function draw() {
      const [originCoords, destinationCoords] = await Promise.all([geocode(origin), geocode(destination)]);
      if (cancelled) return;

      if (!originCoords || !destinationCoords || !containerRef.current) {
        setUnavailable(true);
        return;
      }

      const map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/light-v11",
        center: [originCoords.lng, originCoords.lat],
        zoom: 7,
      });
      new mapboxgl.Marker().setLngLat([originCoords.lng, originCoords.lat]).addTo(map);
      new mapboxgl.Marker().setLngLat([destinationCoords.lng, destinationCoords.lat]).addTo(map);
    }

    draw();
    return () => {
      cancelled = true;
    };
  }, [origin, destination]);

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
