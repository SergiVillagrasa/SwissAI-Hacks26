import { useState, type ReactNode } from "react";
import type { VoiceState } from "../../lib/useVoiceAgent";
import { MountainScene } from "./MountainScene";
import { SearchPill } from "./SearchPill";
import { SwisscomMark } from "./SwisscomMark";

interface LandingScreenProps {
  disabled: boolean;
  onSubmit: (text: string) => void;
  voiceState: VoiceState;
  voiceActive: boolean;
  onMicClick: () => void;
  onVoiceCancel: () => void;
  voiceError: ReactNode;
}

/**
 * "Swiss Travel by Swisscom" landing surface. A full-width geometric zig-zag
 * alpine range rises in five strata behind the floating search pill; focusing
 * the pill (or starting voice input) triggers the tectonic horizon split —
 * every layer's clipped halves glide ±55vw apart, foreground first — while
 * the pill elevates. Blurring slides the strata back to their resting
 * positions. Nothing renders in the opened center: no cards, no previews,
 * only the search.
 */
export function LandingScreen({
  disabled,
  onSubmit,
  voiceState,
  voiceActive,
  onMicClick,
  onVoiceCancel,
  voiceError,
}: LandingScreenProps) {
  const [focused, setFocused] = useState(false);
  const open = focused || voiceActive;

  return (
    <div className="landing" data-open={open} data-testid="landing-screen">
      <header className="absolute left-8 top-8 z-20 select-none font-display text-[15px] font-semibold uppercase tracking-[0.14em] text-swiss-ink">
        Swiss Travel
      </header>

      <MountainScene />

      <div className="relative z-10 flex h-full flex-col items-center justify-center px-6">
        <div className="flex w-full max-w-xl -translate-y-[4vh] flex-col items-center gap-4">
          <SearchPill
            disabled={disabled}
            voiceState={voiceState}
            onMicClick={onMicClick}
            onSubmit={onSubmit}
            onFocusChange={setFocused}
          />
          {voiceActive && (
            <button
              type="button"
              aria-label="Close voice mode"
              onClick={onVoiceCancel}
              className="quiet-focus-swiss flex h-11 w-11 items-center justify-center rounded-full border border-white/95 bg-white/80 text-swiss-ink/70 shadow-[0_8px_24px_-8px_rgba(16,42,69,0.25)] backdrop-blur-xl transition hover:bg-white"
            >
              <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden>
                <path
                  d="M6 6l12 12M18 6L6 18"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          )}
          {voiceError}
        </div>
      </div>

      <footer className="absolute bottom-8 right-8 z-20">
        <SwisscomMark />
      </footer>
    </div>
  );
}
