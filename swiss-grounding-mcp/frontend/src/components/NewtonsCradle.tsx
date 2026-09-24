import { GlassTile } from "./GlassTile";

/** Thinking indicator shown while the assistant's next turn has no content yet. */
export function NewtonsCradle() {
  return (
    <GlassTile className="flex w-fit items-center gap-3 px-5 py-4">
      <div className="newtons-cradle" role="status" aria-label="Thinking">
        <div className="newtons-cradle__dot" />
        <div className="newtons-cradle__dot" />
        <div className="newtons-cradle__dot" />
        <div className="newtons-cradle__dot" />
      </div>
      <span className="text-sm text-neutral-500">Thinking…</span>
    </GlassTile>
  );
}
