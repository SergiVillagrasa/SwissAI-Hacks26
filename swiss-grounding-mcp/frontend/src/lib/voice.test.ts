import { describe, expect, it, vi, afterEach } from "vitest";
import { synthesizeSpeech, transcribeAudio } from "./voice";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("transcribeAudio", () => {
  it("posts the audio as form data and returns the transcript text", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ text: "trains from bern to zurich" }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);

    const text = await transcribeAudio("http://backend", new Blob(["audio"]));

    expect(text).toBe("trains from bern to zurich");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend/api/voice/transcribe");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("throws when the backend responds with a non-OK status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 500 })));

    await expect(
      transcribeAudio("http://backend", new Blob(["audio"]))
    ).rejects.toMatchObject({ status: 500 });
  });
});

describe("synthesizeSpeech", () => {
  it("posts the text as JSON and returns the audio blob", async () => {
    const audioBytes = new Uint8Array([1, 2, 3]);
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(audioBytes, { status: 200, headers: { "Content-Type": "audio/mpeg" } })
    );
    vi.stubGlobal("fetch", fetchMock);

    const blob = await synthesizeSpeech("http://backend", "hello there");

    expect(blob.type).toBe("audio/mpeg");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend/api/voice/speak");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ text: "hello there" });
  });

  it("clips speech text to 1500 characters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(new Uint8Array([1]), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);

    await synthesizeSpeech("http://backend", "x".repeat(1501));

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      text: "x".repeat(1500),
    });
  });

  it("throws when the backend responds with a non-OK status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 500 })));

    await expect(synthesizeSpeech("http://backend", "hello")).rejects.toMatchObject({
      status: 500,
    });
  });
});
