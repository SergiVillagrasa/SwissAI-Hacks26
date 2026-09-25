import { describe, expect, it, vi, afterEach } from "vitest";
import { streamChat } from "./sse";
import type { ChatMessage } from "./types";

function fakeStreamResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("streamChat", () => {
  it("yields parsed events in order across chunk boundaries", async () => {
    const frames = [
      'data: {"type": "token", "text": "hi"}\n\n',
      'data: {"type": "widget", "tool": "find_connections", "status": "ok", "data": {}}\n\n',
      'data: {"type": "done"}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeStreamResponse(frames)));

    const messages: ChatMessage[] = [{ role: "user", content: "hi" }];
    const events = [];
    for await (const event of streamChat("http://backend", messages)) {
      events.push(event);
    }

    expect(events).toEqual([
      { type: "token", text: "hi" },
      { type: "widget", tool: "find_connections", status: "ok", data: {} },
      { type: "done" },
    ]);
  });

  it("includes the voice channel in the request body when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue(fakeStreamResponse(['data: {"type": "done"}\n\n']));
    vi.stubGlobal("fetch", fetchMock);

    const messages: ChatMessage[] = [{ role: "user", content: "spoken request" }];
    for await (const _event of streamChat("http://backend", messages, "voice")) {
      void _event;
    }

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.channel).toBe("voice");
    expect(body.messages).toEqual(messages);
  });

  it("omits the channel field for typed requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(fakeStreamResponse(['data: {"type": "done"}\n\n']));
    vi.stubGlobal("fetch", fetchMock);

    for await (const _event of streamChat("http://backend", [{ role: "user", content: "typed" }])) {
      void _event;
    }

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.channel).toBeUndefined();
  });

  it("throws when the backend responds with a non-OK status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 500 }))
    );

    const generator = streamChat("http://backend", [{ role: "user", content: "hi" }]);

    await expect(generator.next()).rejects.toThrow("Agent backend responded with 500");
  });
});
