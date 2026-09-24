import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import type { VoiceState } from "../lib/useVoiceAgent";

interface ComposerProps {
  disabled: boolean;
  onSubmit: (text: string) => void;
  voiceState: VoiceState;
  onMicClick: () => void;
}

const MAX_TEXTAREA_HEIGHT = 160;

const MIC_LABEL: Record<VoiceState, string> = {
  idle: "Speak instead of typing",
  listening: "Stop and send",
  processing: "Transcribing your voice",
  speaking: "Assistant is speaking",
  error: "Speak instead of typing",
};

export function Composer({ disabled, onSubmit, voiceState, onMicClick }: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  }, [value]);

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

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  const micDisabled = disabled || voiceState === "processing" || voiceState === "speaking";
  const micListening = voiceState === "listening";

  return (
    <form onSubmit={handleSubmit} className="relative w-full max-w-2xl">
      <div
        aria-hidden
        className="absolute inset-x-6 -top-10 bottom-[-40px] -z-10 bg-pill-glow blur-2xl"
      />
      <div className="flex items-end gap-3 rounded-[28px] border border-white/60 bg-white/60 px-5 py-3.5 shadow-glass backdrop-blur-xl transition duration-200 focus-within:bg-white/75 focus-within:shadow-glass-pop">
        <textarea
          ref={textareaRef}
          rows={1}
          className="quiet-focus-plain max-h-40 flex-1 resize-none bg-transparent py-1 text-base leading-6 text-neutral-800 outline-none placeholder:text-neutral-500 disabled:opacity-50"
          placeholder="Ask about your journey"
          value={value}
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          type="button"
          disabled={micDisabled}
          aria-label={MIC_LABEL[voiceState]}
          aria-pressed={micListening}
          onClick={onMicClick}
          className={`quiet-focus flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
            micListening
              ? "voice-mic-active bg-rose-500 text-white"
              : "text-accent hover:bg-accent/10"
          }`}
        >
          {voiceState === "processing" ? (
            <span className="voice-spinner" aria-hidden />
          ) : micListening ? (
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5" aria-hidden>
              <rect x="5" y="5" width="14" height="14" rx="3" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden>
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
          aria-label="Send"
          className="quiet-focus flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-white shadow-glass-sm transition duration-200 hover:bg-accent-dim disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden>
            <path
              d="M4 12h15M13 5l7 7-7 7"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </form>
  );
}
