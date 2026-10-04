import type { HTMLAttributes, ReactNode } from "react";

export const glassTile =
  "rounded-3xl border border-white/60 bg-white/55 backdrop-blur-xl shadow-glass";

export const glassRow =
  "rounded-2xl border border-white/50 bg-white/45 backdrop-blur-md";

export const glassRowInteractive =
  "rounded-2xl border border-white/50 bg-white/45 backdrop-blur-md transition duration-200 ease-out hover:-translate-y-0.5 hover:bg-white/70 hover:shadow-glass-pop";

/** Applied to a selectable row's interactive classes when it is the
 * active/expanded choice. `border-*`/`bg-*` are prefixed with Tailwind's
 * `!important` modifier so the selected state reliably overrides
 * `glassRowInteractive`'s own `border-white/50 bg-white/45` (and its
 * `hover:bg-white/70`) when both class strings are applied to the same
 * element -- without `!`, class order in the compiled stylesheet (not the
 * order they're concatenated in JSX) decides which wins, which made the
 * "selected" look inconsistently disappear depending on build output. */
export const glassRowSelected = "!border-blue-500 !bg-blue-50/40 ring-2 ring-blue-400";

export const glassPill =
  "rounded-full border border-white/60 bg-white/55 backdrop-blur-xl shadow-glass";

interface GlassTileProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  interactive?: boolean;
}

/** Shared "liquid glass" tile: translucent, blurred, lit border, soft blue-cast shadow. */
export function GlassTile({ children, className = "", interactive = false, ...rest }: GlassTileProps) {
  return (
    <div
      className={`${glassTile} animate-rise ${interactive ? "transition duration-200 ease-out hover:-translate-y-0.5 hover:shadow-glass-pop" : ""} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}
