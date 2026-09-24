import type { CSSProperties } from "react";
import type { VoiceState } from "../lib/useVoiceAgent";

interface VoiceBorderGlowProps {
  state: VoiceState;
  level: number;
}

/**
 * A colorful, fluid glow that hugs the edges of the viewport while the
 * voice agent is listening or speaking — the center stays clear so the
 * conversation underneath is never blocked. Intensity follows `level`,
 * the live mic/TTS amplitude (0..1), so it visibly breathes with speech.
 */
export function VoiceBorderGlow({ state, level }: VoiceBorderGlowProps) {
  return (
    <div
      className="voice-border-glow"
      data-state={state}
      aria-hidden
      style={{ "--level": level } as CSSProperties}
    >
      <span className="voice-border-glow__blob voice-border-glow__blob--a" />
      <span className="voice-border-glow__blob voice-border-glow__blob--b" />
      <span className="voice-border-glow__blob voice-border-glow__blob--c" />
      <span className="voice-border-glow__blob voice-border-glow__blob--d" />
      <span className="voice-border-glow__blob voice-border-glow__blob--e" />
    </div>
  );
}
