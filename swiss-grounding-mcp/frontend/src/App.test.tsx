import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./App";

function fakeStreamResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame));
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("shows the empty-state hero before any message is sent", () => {
    render(<App />);
    expect(screen.getByPlaceholderText(/ask about your journey/i)).toBeInTheDocument();
  });

  it("collapses the hero and renders the streamed reply after submitting", async () => {
    const frames = [
      'data: {"type": "token", "text": "Here is what I found."}\n\n',
      'data: {"type": "widget", "tool": "find_connections", "status": "ok", "data": {"connections": [{"departure": "2026-09-24T18:04:00Z", "arrival": "2026-09-24T18:10:00Z", "duration_minutes": 6, "changes": 0, "legs": []}]}}\n\n',
      'data: {"type": "done"}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeStreamResponse(frames)));

    render(<App />);
    const input = screen.getByPlaceholderText(/ask about your journey/i);
    fireEvent.change(input, { target: { value: "Trains from Bern to Zürich" } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByText("Trains from Bern to Zürich")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("Here is what I found.")).toBeInTheDocument()
    );
    expect(screen.getByText(/direct/i)).toBeInTheDocument();
  });

  it("re-enables the composer and shows an error turn when the stream fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 500 })));

    render(<App />);
    const input = screen.getByPlaceholderText(/ask about your journey/i);
    fireEvent.change(input, { target: { value: "hi" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() =>
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    );
    expect(input).not.toBeDisabled();
  });
});
