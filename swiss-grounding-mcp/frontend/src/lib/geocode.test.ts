import { describe, expect, it, vi, afterEach } from "vitest";
import { geocode } from "./geocode";

afterEach(() => vi.restoreAllMocks());

describe("geocode", () => {
  it("returns coordinates for a resolvable place", async () => {
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

  it("returns null when no features are found", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ features: [] }) }));

    const result = await geocode("Nonexistent Place");

    expect(result).toBeNull();
  });

  it("returns null when the geocoding request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }));

    const result = await geocode("Bern");

    expect(result).toBeNull();
  });
});
