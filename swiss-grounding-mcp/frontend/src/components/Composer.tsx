import { useState, type FormEvent } from "react";

interface ComposerProps {
  disabled: boolean;
  onSubmit: (text: string) => void;
}

export function Composer({ disabled, onSubmit }: ComposerProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl">
      <div className="flex items-center gap-3 rounded-full border border-neutral-200 bg-white px-5 py-3 shadow-sm">
        <input
          className="flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400 disabled:opacity-50"
          placeholder="Ask about your journey"
          value={value}
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </form>
  );
}
