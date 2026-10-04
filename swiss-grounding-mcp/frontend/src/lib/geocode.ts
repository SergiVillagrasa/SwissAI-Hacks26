export interface Coordinates {
  lat: number;
  lng: number;
}

/** Approximate center of Switzerland (lng/lat), used as the proximity bias
 * for a lookup when no better (route-specific) proximity hint is given -
 * e.g. "Bern" should resolve to the nearby match instead of a homonym on
 * another continent, without excluding legitimate international stations
 * on cross-border itineraries (Barcelona, Lyon, Milano, ...). */
const SWITZERLAND_CENTER: Coordinates = { lat: 46.8182, lng: 8.2275 };

/** Very loose sanity box spanning Europe/North-Africa-adjacent longitudes,
 * used only when a journey's own origin/destination coordinates aren't
 * available to build a proper corridor (see `isWithinCorridor` below). It
 * only exists to catch a wildly wrong geocode match (a different
 * continent) and must NOT be narrowed to Switzerland alone, or
 * cross-border origins/transfers get silently dropped. */
const PLAUSIBLE_BBOX = [-15, 30, 40, 72] as const;

export function isPlausibleCoordinate(coords: Coordinates): boolean {
  const [minLng, minLat, maxLng, maxLat] = PLAUSIBLE_BBOX;
  return coords.lng >= minLng && coords.lng <= maxLng && coords.lat >= minLat && coords.lat <= maxLat;
}

/** Switzerland's bounding box (lng/lat), used for the business rule that at
 * least one point of a displayed itinerary must actually be in Swiss
 * territory - this app covers Swiss and Swiss-connected travel, not purely
 * foreign journeys. Distinct from the corridor/plausibility checks below:
 * this one is exact, to decide whether a route is in scope at all. */
export const SWITZERLAND_BBOX = [5.95, 45.81, 10.49, 47.81] as const;

export function isWithinSwitzerland(coords: Coordinates): boolean {
  const [minLng, minLat, maxLng, maxLat] = SWITZERLAND_BBOX;
  return coords.lng >= minLng && coords.lng <= maxLng && coords.lat >= minLat && coords.lat <= maxLat;
}

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

/** Great-circle distance in kilometres between two points (haversine). */
export function haversineKm(a: Coordinates, b: Coordinates): number {
  const EARTH_RADIUS_KM = 6371;
  const dLat = toRadians(b.lat - a.lat);
  const dLng = toRadians(b.lng - a.lng);
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
}

/** Default maximum "detour" a geocoded intermediate stop may add to the
 * straight-line origin -> destination distance before it's rejected as an
 * implausible match (e.g. Mapbox resolving a bare "Valence" to a homonym
 * city on another continent instead of the French one on a Barcelona ->
 * Zürich route). */
export const MAX_CORRIDOR_DETOUR_KM = 300;

/** Whether `point` plausibly lies on (or close to) the route from `origin`
 * to `destination`, expressed as the extra round-trip distance it would
 * add: `dist(origin, point) + dist(point, destination) - dist(origin,
 * destination)`. A point near the straight line barely adds any distance;
 * one that's badly wrong (behind the origin, beyond the destination, or
 * off on a sharp tangent) inflates it well past `maxDetourKm`. This single
 * formula captures both "too far to the side of the corridor" and
 * "extreme acute angle" outliers without needing separate ellipse/angle
 * geometry, and - unlike a fixed bounding box - scales naturally with how
 * long the journey actually is. */
export function isWithinCorridor(
  point: Coordinates,
  origin: Coordinates,
  destination: Coordinates,
  maxDetourKm: number = MAX_CORRIDOR_DETOUR_KM
): boolean {
  const direct = haversineKm(origin, destination);
  const viaPoint = haversineKm(origin, point) + haversineKm(point, destination);
  return viaPoint - direct <= maxDetourKm;
}

// Qualifiers that only ever indicate "this is a train/bus stop", never part
// of a place's actual name, when they immediately follow a comma (e.g.
// "Annemasse, gare", "Genève, gare Cornavin", "Freiburg, Bahnhof"). Stripped
// together with the comma. Deliberately does NOT match a bare "gare"/
// "Bahnhof" with no comma, which is how it appears inside a genuine proper
// name such as "Paris Gare de Lyon" or a German "Hauptbahnhof" - those must
// survive cleanup untouched.
const COMMA_QUALIFIER_PATTERN = /,\s*(?:gare routi[eè]re|gare(?:\s+\S+)?|bahnhof|stazione)\s*$/i;

// Qualifiers that are always redundant transport-mode/rolling-stock labels
// wherever they appear, so they're safe to strip as whole words anywhere in
// the string: "Valence TGV Rhône-Alpes Sud" -> "Valence Rhône-Alpes Sud",
// "Zürich HB" -> "Zürich", "Freiburg(Breisgau) Hbf" -> "Freiburg(Breisgau)".
const STANDALONE_QUALIFIER_PATTERN = /\b(?:tgv|ice|hbf?|s[\s-]?bahn)\b/gi;

// Trailing Swiss canton or neighbouring-country codes, optionally
// parenthesised: "Romont FR" -> "Romont", "Sion VS" -> "Sion",
// "Basel (CH)" -> "Basel". Deliberately a closed list of real codes (not
// "any trailing 2-3 letters") so a station whose name genuinely ends that
// way is never mangled.
const REGION_CODES = [
  "CH", "FR", "DE", "IT", "AT",
  "VD", "BE", "GE", "VS", "NE", "JU", "SO", "BS", "BL", "AG",
  "ZH", "LU", "UR", "SZ", "OW", "NW", "GL", "ZG", "TI", "GR",
  "SG", "AR", "AI", "TG", "SH",
];
const REGION_CODE_PATTERN = new RegExp(`\\(?\\b(?:${REGION_CODES.join("|")})\\b\\)?\\s*$`, "i");

/** Normalizes a raw station/stop name into something more likely to match
 * a real place in Mapbox's geocoder, by stripping transport-specific
 * qualifiers that carry no location information: public-transport suffixes
 * ("gare routière", "gare", "Bahnhof", "Stazione"), rolling-stock/mode
 * labels ("TGV", "ICE", "HB", "S-Bahn", "Hbf"), and trailing canton/country
 * codes ("FR", "VD", "BE", "(CH)", ...). This is a general-purpose pipeline
 * - it has no special-casing for any particular city or station. */
export function cleanStationName(name: string): string {
  let cleaned = name
    .replace(COMMA_QUALIFIER_PATTERN, "")
    .replace(STANDALONE_QUALIFIER_PATTERN, " ");
  cleaned = cleaned.replace(REGION_CODE_PATTERN, "");
  cleaned = cleaned
    .replace(/\s{2,}/g, " ")
    .replace(/[,\-/\s]+$/g, "")
    .trim();
  return cleaned || name.trim();
}

/** Last-resort fallback when even the cleaned full name fails to geocode
 * (or - for callers that check it - resolves implausibly): the first
 * word/block of the name, split on whitespace, commas, hyphens, slashes,
 * or parentheses. This reduces compound names most of the way down to
 * their municipality, e.g. "Valence TGV Rhône-Alpes Sud" -> "Valence",
 * "Genève-Aéroport, gare routière" -> "Genève", "Romont FR" -> "Romont". */
export function extractPrimaryMunicipality(name: string): string {
  const [first] = name.split(/[\s,/()-]+/).filter(Boolean);
  return first ?? name.trim();
}

interface MapboxGeocodeOptions {
  proximity?: Coordinates;
}

async function geocodeQuery(query: string, proximity: Coordinates): Promise<Coordinates | null> {
  const token = import.meta.env.VITE_MAPBOX_TOKEN ?? "";
  if (!token || !query) return null;
  const params = new URLSearchParams({
    access_token: token,
    limit: "1",
    proximity: `${proximity.lng},${proximity.lat}`,
    // Restricting to places/localities/POIs (rather than also matching
    // addresses or raw POI categories) avoids a station name being
    // confused with, say, an unrelated street of the same name on another
    // continent.
    types: "place,locality,poi",
  });
  const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(query)}.json?${params.toString()}`;

  const response = await fetch(url);
  if (!response.ok) return null;

  const body = await response.json();
  const feature = body.features?.[0];
  if (!feature) return null;

  const [lng, lat] = feature.center;
  return { lat, lng };
}

/** Geocodes a place name, first trying it with public-transport qualifiers
 * stripped (see `cleanStationName`), then - only if that yields nothing -
 * retrying with just the primary municipality name (see
 * `extractPrimaryMunicipality`). `proximity` biases Mapbox toward matches
 * near a known point (e.g. the previous confirmed stop on this itinerary,
 * or the route's own midpoint) instead of a fixed location; it defaults to
 * the center of Switzerland. */
export async function geocode(placeName: string, options?: MapboxGeocodeOptions): Promise<Coordinates | null> {
  const proximity = options?.proximity ?? SWITZERLAND_CENTER;

  const cleaned = cleanStationName(placeName);
  const direct = await geocodeQuery(cleaned, proximity);
  if (direct) return direct;

  const fallback = extractPrimaryMunicipality(cleaned);
  if (fallback && fallback.toLowerCase() !== cleaned.toLowerCase()) {
    return geocodeQuery(fallback, proximity);
  }
  return null;
}

const geocodeCache = new Map<string, Promise<Coordinates | null>>();

/** Memoizing wrapper around geocode(): the same intermediate/transfer
 * station name is looked up repeatedly across connections and re-renders,
 * so this collapses duplicate concurrent and repeat requests to one
 * network call per place name for the lifetime of the page. The cache key
 * is the name alone (not `proximity`), so the first resolution of a given
 * name wins even if a later call supplies a different proximity hint. */
export function geocodeCached(placeName: string, options?: MapboxGeocodeOptions): Promise<Coordinates | null> {
  const key = placeName.trim().toLowerCase();
  let pending = geocodeCache.get(key);
  if (!pending) {
    pending = geocode(placeName, options);
    geocodeCache.set(key, pending);
  }
  return pending;
}

/** Test-only escape hatch to reset the memoization cache between cases. */
export function clearGeocodeCache(): void {
  geocodeCache.clear();
}
