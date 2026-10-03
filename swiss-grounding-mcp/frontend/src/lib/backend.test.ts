import { afterEach, describe, expect, it, vi } from "vitest";
import { BackendError, backendHeaders } from "./backend";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("backendHeaders", () => {
  it("includes a bearer token when configured", () => {
    vi.stubEnv("VITE_AGENT_BACKEND_API_KEY", "test-key");

    expect(backendHeaders({ "Content-Type": "application/json" })).toEqual({
      Authorization: "Bearer test-key",
      "Content-Type": "application/json",
    });
  });

  it("omits authorization when no key is configured", () => {
    vi.stubEnv("VITE_AGENT_BACKEND_API_KEY", "");

    expect(backendHeaders()).toEqual({});
  });
});

it("retains the backend response status", () => {
  const error = new BackendError(429);

  expect(error).toBeInstanceOf(Error);
  expect(error.status).toBe(429);
});
