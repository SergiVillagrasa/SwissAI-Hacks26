export interface Coordinates {
  lat: number;
  lng: number;
}

export async function geocode(placeName: string): Promise<Coordinates | null> {
  const token = import.meta.env.VITE_MAPBOX_TOKEN ?? "";
  if (!token) return null;
  const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(placeName)}.json?access_token=${token}&limit=1`;

  const response = await fetch(url);
  if (!response.ok) return null;

  const body = await response.json();
  const feature = body.features?.[0];
  if (!feature) return null;

  const [lng, lat] = feature.center;
  return { lat, lng };
}

const geocodeCache = new Map<string, Promise<Coordinates | null>>();

/** Memoizing wrapper around geocode(): the same intermediate/transfer
 * station name is looked up repeatedly across connections and re-renders,
 * so this collapses duplicate concurrent and repeat requests to one
 * network call per place name for the lifetime of the page. */
export function geocodeCached(placeName: string): Promise<Coordinates | null> {
  const key = placeName.trim().toLowerCase();
  let pending = geocodeCache.get(key);
  if (!pending) {
    pending = geocode(placeName);
    geocodeCache.set(key, pending);
  }
  return pending;
}

/** Test-only escape hatch to reset the memoization cache between cases. */
export function clearGeocodeCache(): void {
  geocodeCache.clear();
}
