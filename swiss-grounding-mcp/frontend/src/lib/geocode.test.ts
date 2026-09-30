import { describe, expect, it, vi, afterEach } from "vitest";
import { clearGeocodeCache, geocode, geocodeCached } from "./geocode";

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
