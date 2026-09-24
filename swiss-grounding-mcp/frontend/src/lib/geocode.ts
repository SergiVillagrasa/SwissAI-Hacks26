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
