import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

interface ComposerProps {
  disabled: boolean;
  onSubmit: (text: string) => void;
}

const MAX_TEXTAREA_HEIGHT = 160;

export function Composer({ disabled, onSubmit }: ComposerProps) {
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
          className="max-h-40 flex-1 resize-none bg-transparent py-1 text-base leading-6 text-neutral-800 outline-none placeholder:text-neutral-500 disabled:opacity-50"
          placeholder="Ask about your journey"
          value={value}
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          aria-label="Send"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-white shadow-glass-sm transition duration-200 hover:bg-accent-dim disabled:cursor-not-allowed disabled:opacity-40"
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
