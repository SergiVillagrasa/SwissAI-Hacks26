import { describe, expect, it, vi, afterEach } from "vitest";
import {
  cleanStationName,
  clearGeocodeCache,
  extractPrimaryMunicipality,
  geocode,
  geocodeCached,
  haversineKm,
  isWithinCorridor,
} from "./geocode";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  clearGeocodeCache();
});

describe("geocode", () => {
  it("returns coordinates for a resolvable place", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ features: [{ center: [7.4474, 46.9481] }] }),
      })
    );

    const result = await geocode("Bern");

    expect(result).toEqual({ lat: 46.9481, lng: 7.4474 });
  });

  it("returns null without calling the API when no token is configured", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await geocode("Bern");

    expect(result).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns null when no features are found", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ features: [] }) }));

    const result = await geocode("Nonexistent Place");

    expect(result).toBeNull();
  });

  it("returns null when the geocoding request fails", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }));

    const result = await geocode("Bern");

    expect(result).toBeNull();
  });
});

// ── Generic name-cleanup pipeline (no per-city/per-station special cases) ──

describe("cleanStationName", () => {
  it("leaves names with no qualifiers untouched", () => {
    expect(cleanStationName("Milano Centrale")).toBe("Milano Centrale");
    expect(cleanStationName("Paris Gare de Lyon")).toBe("Paris Gare de Lyon");
  });

  it("strips rolling-stock/mode qualifiers wherever they appear", () => {
    expect(cleanStationName("Valence TGV Rhône-Alpes Sud")).toBe("Valence Rhône-Alpes Sud");
    expect(cleanStationName("Zürich HB")).toBe("Zürich");
    expect(cleanStationName("Freiburg(Breisgau) Hbf")).toBe("Freiburg(Breisgau)");
  });

  it("strips a comma-qualified public-transport suffix, without touching a bare 'Gare' in a proper name", () => {
    expect(cleanStationName("Genève-Aéroport, gare routière")).toBe("Genève-Aéroport");
    expect(cleanStationName("Annemasse, gare")).toBe("Annemasse");
    expect(cleanStationName("Genève, gare Cornavin")).toBe("Genève");
    expect(cleanStationName("Paris Gare de Lyon")).toBe("Paris Gare de Lyon");
  });

  it("strips a trailing canton/country code, parenthesised or not", () => {
    expect(cleanStationName("Romont FR")).toBe("Romont");
    expect(cleanStationName("Sion VS")).toBe("Sion");
    expect(cleanStationName("Basel (CH)")).toBe("Basel");
  });
});

describe("extractPrimaryMunicipality", () => {
  it("takes the first word/block before a space, comma, hyphen, or slash", () => {
    expect(extractPrimaryMunicipality("Valence Rhône-Alpes Sud")).toBe("Valence");
    expect(extractPrimaryMunicipality("Genève-Aéroport")).toBe("Genève");
    expect(extractPrimaryMunicipality("Fribourg/Freiburg")).toBe("Fribourg");
    expect(extractPrimaryMunicipality("Romont FR")).toBe("Romont");
  });
});

// ── Corridor-based outlier rejection (replaces a fixed bounding box) ──────

describe("haversineKm / isWithinCorridor", () => {
  const barcelona = { lat: 41.3789, lng: 2.1404 };
  const zurich = { lat: 47.3779, lng: 8.5403 };

  it("computes a plausible great-circle distance", () => {
    const distance = haversineKm(barcelona, zurich);
    expect(distance).toBeGreaterThan(700);
    expect(distance).toBeLessThan(900);
  });

  it("accepts a stop that genuinely sits on the corridor", () => {
    const valenceFrance = { lat: 44.9334, lng: 4.8924 };
    expect(isWithinCorridor(valenceFrance, barcelona, zurich)).toBe(true);
  });

  it("rejects a homonym on another continent", () => {
    const valenciaVenezuela = { lat: 10.162, lng: -68.0077 };
    expect(isWithinCorridor(valenciaVenezuela, barcelona, zurich)).toBe(false);
  });

  it("rejects a point that adds a large detour even on the same continent", () => {
    const malaga = { lat: 36.7213, lng: -4.4214 };
    expect(isWithinCorridor(malaga, barcelona, zurich)).toBe(false);
  });
});

// ── geocode(): cleanup + municipality fallback + proximity ────────────────

describe("geocode fallback behaviour", () => {
  it("retries with the primary municipality when the cleaned full name has no match", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      const query = decodeURIComponent(new URL(url).pathname.split("/").pop()!.replace(".json", ""));
      if (query === "Valence") {
        return { ok: true, json: async () => ({ features: [{ center: [4.8924, 44.9334] }] }) };
      }
      return { ok: true, json: async () => ({ features: [] }) };
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await geocode("Valence TGV Rhône-Alpes Sud");

    expect(result).toEqual({ lat: 44.9334, lng: 4.8924 });
    // First call for the cleaned name ("Valence Rhône-Alpes Sud"), second
    // for the municipality-only fallback ("Valence").
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("passes the given proximity through to the Mapbox request instead of the static Switzerland center", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    let seenProximity: string | null = null;
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      seenProximity = new URL(url).searchParams.get("proximity");
      return { ok: true, json: async () => ({ features: [{ center: [7.4474, 46.9481] }] }) };
    });
    vi.stubGlobal("fetch", fetchMock);

    await geocode("Bern", { proximity: { lat: 44.9334, lng: 4.8924 } });

    expect(seenProximity).toBe("4.8924,44.9334");
  });
});

describe("geocodeCached", () => {
  it("only issues one network request for repeat lookups of the same place", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ features: [{ center: [7.4474, 46.9481] }] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const first = await geocodeCached("Bern");
    const second = await geocodeCached("bern");
    const third = await geocodeCached("Bern");

    expect(first).toEqual({ lat: 46.9481, lng: 7.4474 });
    expect(second).toEqual(first);
    expect(third).toEqual(first);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("re-fetches after the cache is cleared", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "test-token");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ features: [{ center: [7.4474, 46.9481] }] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await geocodeCached("Bern");
    clearGeocodeCache();
    await geocodeCached("Bern");

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
