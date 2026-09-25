import { useState, type FormEvent, type KeyboardEvent } from "react";
import type { VoiceState } from "../../lib/useVoiceAgent";

interface SearchPillProps {
  disabled: boolean;
  voiceState: VoiceState;
  onMicClick: () => void;
  onSubmit: (text: string) => void;
  onFocusChange: (focused: boolean) => void;
}

const MIC_LABEL: Record<VoiceState, string> = {
  idle: "Speak instead of typing",
  listening: "Stop and send",
  processing: "Transcribing your voice",
  speaking: "Assistant is speaking",
  error: "Speak instead of typing",
};

export function SearchPill({
  disabled,
  voiceState,
  onMicClick,
  onSubmit,
  onFocusChange,
}: SearchPillProps) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.currentTarget.blur();
    }
  }

  const micDisabled = disabled || voiceState === "processing" || voiceState === "speaking";
  const micListening = voiceState === "listening";

  return (
    <form role="search" onSubmit={handleSubmit} className="landing-pill">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className="ml-6 h-5 w-5 shrink-0 text-swiss-ink/45"
        aria-hidden
      >
        <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.8" />
        <path d="M20 20l-3.8-3.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      <input
        type="text"
        aria-label="Search your journey"
        placeholder="Buscar tus resultados..."
        className="quiet-focus-plain min-w-0 flex-1 bg-transparent px-4 font-inter text-base text-swiss-ink outline-none placeholder:text-swiss-ink/55 disabled:opacity-50"
        value={value}
        disabled={disabled}
        onChange={(event) => setValue(event.target.value)}
        onFocus={() => onFocusChange(true)}
        onBlur={() => onFocusChange(false)}
        onKeyDown={handleKeyDown}
      />
      <button
        type="button"
        disabled={micDisabled}
        aria-label={MIC_LABEL[voiceState]}
        aria-pressed={micListening}
        onClick={onMicClick}
        className={`quiet-focus-swiss flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
          micListening
            ? "voice-mic-active bg-swisscom-red text-white"
            : "text-swiss-ink/60 hover:bg-swiss-ink/[0.06] hover:text-swiss-ink"
        }`}
      >
        {voiceState === "processing" ? (
          <span className="voice-spinner" aria-hidden />
        ) : micListening ? (
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden>
            <rect x="5" y="5" width="14" height="14" rx="3" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]" aria-hidden>
            <path
              d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M19 11a7 7 0 0 1-14 0M12 18v3"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        aria-label="Search"
        className="quiet-focus-swiss mr-2 flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-swiss-navy text-white transition duration-200 hover:bg-[#14345f] active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]" aria-hidden>
          <path
            d="M4 12h15M13 5l7 7-7 7"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </form>
  );
}
