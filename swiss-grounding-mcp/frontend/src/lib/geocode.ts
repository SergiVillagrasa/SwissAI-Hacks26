export interface Coordinates {
  lat: number;
  lng: number;
}

/** Approximate center of Switzerland (lng/lat), used to bias ambiguous
 * place-name lookups (e.g. "Bern") toward the nearby match instead of a
 * homonym on another continent, without excluding legitimate international
 * stations on cross-border itineraries (Barcelona, Lyon, Milano, ...). */
const SWITZERLAND_CENTER: readonly [number, number] = [8.2275, 46.8182];

/** Very loose sanity box spanning Europe/North-Africa-adjacent longitudes,
 * just wide enough to cover any station a Swiss-connected itinerary might
 * plausibly include. It only exists to catch a wildly wrong geocode match
 * (a different continent) - it must NOT be narrowed to Switzerland alone,
 * or cross-border origins/transfers get silently dropped. */
const PLAUSIBLE_BBOX = [-15, 30, 40, 72] as const;

export function isPlausibleCoordinate(coords: Coordinates): boolean {
  const [minLng, minLat, maxLng, maxLat] = PLAUSIBLE_BBOX;
  return coords.lng >= minLng && coords.lng <= maxLng && coords.lat >= minLat && coords.lat <= maxLat;
}

/** Switzerland's bounding box (lng/lat), used for the business rule that at
 * least one point of a displayed itinerary must actually be in Swiss
 * territory - this app covers Swiss and Swiss-connected travel, not purely
 * foreign journeys. Distinct from `PLAUSIBLE_BBOX` above: that one is
 * deliberately wide so cross-border stops aren't discarded; this one is
 * exact, to decide whether a route is in scope at all. */
export const SWITZERLAND_BBOX = [5.95, 45.81, 10.49, 47.81] as const;

export function isWithinSwitzerland(coords: Coordinates): boolean {
  const [minLng, minLat, maxLng, maxLat] = SWITZERLAND_BBOX;
  return coords.lng >= minLng && coords.lng <= maxLng && coords.lat >= minLat && coords.lat <= maxLat;
}

export async function geocode(placeName: string): Promise<Coordinates | null> {
  const token = import.meta.env.VITE_MAPBOX_TOKEN ?? "";
  if (!token) return null;
  const params = new URLSearchParams({
    access_token: token,
    limit: "1",
    proximity: SWITZERLAND_CENTER.join(","),
    types: "place,locality,poi",
  });
  const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(placeName)}.json?${params.toString()}`;

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
    pending = geocode(placeName).catch((error) => {
      console.warn(`geocodeCached: lookup failed for "${placeName}"`, error);
      geocodeCache.delete(key);
      return null;
    });
    geocodeCache.set(key, pending);
  }
  return pending;
}

/** Test-only escape hatch to reset the memoization cache between cases. */
export function clearGeocodeCache(): void {
  geocodeCache.clear();
}
