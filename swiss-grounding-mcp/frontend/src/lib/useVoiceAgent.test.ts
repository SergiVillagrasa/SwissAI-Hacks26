import { describe, expect, it, vi, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useVoiceAgent } from "./useVoiceAgent";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("useVoiceAgent", () => {
  it("starts idle and moves to the mic-denied error state when permission is refused", async () => {
    vi.stubGlobal("navigator", {
      ...navigator,
      mediaDevices: {
        getUserMedia: vi.fn().mockRejectedValue(new DOMException("Denied", "NotAllowedError")),
      },
    });

    const { result } = renderHook(() => useVoiceAgent("http://backend", vi.fn()));
    expect(result.current.state).toBe("idle");

    await act(async () => {
      await result.current.start();
    });

    await waitFor(() => expect(result.current.state).toBe("error"));
    expect(result.current.errorMessage).toMatch(/microphone access was denied/i);
  });

  it("cancel() resets back to idle and clears any error", async () => {
    vi.stubGlobal("navigator", {
      ...navigator,
      mediaDevices: {
        getUserMedia: vi.fn().mockRejectedValue(new DOMException("Denied", "NotAllowedError")),
      },
    });

    const { result } = renderHook(() => useVoiceAgent("http://backend", vi.fn()));
    await act(async () => {
      await result.current.start();
    });
    await waitFor(() => expect(result.current.state).toBe("error"));

    act(() => {
      result.current.cancel();
    });

    expect(result.current.state).toBe("idle");
    expect(result.current.errorMessage).toBeNull();
  });
});
