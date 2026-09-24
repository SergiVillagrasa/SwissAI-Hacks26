import { useCallback, useEffect, useRef, useState } from "react";
import { meterFromAudioElement, meterFromStream } from "./audioLevel";
import { synthesizeSpeech, transcribeAudio } from "./voice";

export type VoiceState = "idle" | "listening" | "processing" | "speaking" | "error";

/**
 * Owns the full press-to-talk pipeline: mic capture -> transcribe -> hand the
 * transcript to the chat turn -> speak the reply back. `level` is a live
 * 0..1 amplitude read from whichever audio is currently flowing (mic while
 * listening, TTS playback while speaking), meant to drive reactive motion.
 */
export function useVoiceAgent(
  backendUrl: string,
  onTranscript: (text: string) => Promise<string>
) {
  const [state, setState] = useState<VoiceState>("idle");
  const [level, setLevel] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const stopMeterRef = useRef<(() => void) | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const cancelledRef = useRef(false);

  const teardown = useCallback(() => {
    stopMeterRef.current?.();
    stopMeterRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
  }, []);

  useEffect(() => () => teardown(), [teardown]);

  const start = useCallback(async () => {
    cancelledRef.current = false;
    setErrorMessage(null);
    setState("listening");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (cancelledRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      stopMeterRef.current = meterFromStream(stream, setLevel);

      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
    } catch {
      setErrorMessage("Microphone access was denied. Allow it in your browser settings to speak.");
      setState("error");
    }
  }, []);

  const speak = useCallback(
    async (text: string) => {
      if (!text.trim() || cancelledRef.current) {
        setState("idle");
        return;
      }
      setState("speaking");
      try {
        const audioBlob = await synthesizeSpeech(backendUrl, text);
        if (cancelledRef.current) return;
        const url = URL.createObjectURL(audioBlob);
        const audio = new Audio(url);
        audioRef.current = audio;
        stopMeterRef.current = meterFromAudioElement(audio, setLevel);

        await new Promise<void>((resolve) => {
          audio.addEventListener("ended", () => resolve(), { once: true });
          audio.addEventListener("error", () => resolve(), { once: true });
          audio.play().catch(() => resolve());
        });
        URL.revokeObjectURL(url);
      } finally {
        stopMeterRef.current?.();
        stopMeterRef.current = null;
        setLevel(0);
        if (!cancelledRef.current) setState("idle");
      }
    },
    [backendUrl]
  );

  const stopAndSend = useCallback(async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") return;

    setState("processing");
    setLevel(0);
    stopMeterRef.current?.();
    stopMeterRef.current = null;

    const blob = await new Promise<Blob>((resolve) => {
      recorder.addEventListener(
        "stop",
        () => resolve(new Blob(chunksRef.current, { type: recorder.mimeType })),
        { once: true }
      );
      recorder.stop();
    });
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (cancelledRef.current) return;

    try {
      const transcript = (await transcribeAudio(backendUrl, blob)).trim();
      if (cancelledRef.current) return;
      if (!transcript) {
        setErrorMessage("I didn't catch that. Try again.");
        setState("error");
        return;
      }

      const assistantText = await onTranscript(transcript);
      if (cancelledRef.current) return;
      await speak(assistantText);
    } catch {
      if (cancelledRef.current) return;
      setErrorMessage("Something went wrong reaching the assistant. Please try again.");
      setState("error");
    }
  }, [backendUrl, onTranscript, speak]);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    teardown();
    setLevel(0);
    setErrorMessage(null);
    setState("idle");
  }, [teardown]);

  return { state, level, errorMessage, start, stopAndSend, cancel };
}
