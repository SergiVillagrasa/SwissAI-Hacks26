import type { HTMLAttributes, ReactNode } from "react";

export const glassTile =
  "rounded-3xl border border-white/60 bg-white/55 backdrop-blur-xl shadow-glass";

export const glassRow =
  "rounded-2xl border border-white/50 bg-white/45 backdrop-blur-md";

export const glassRowInteractive =
  "rounded-2xl border border-white/50 bg-white/45 backdrop-blur-md transition duration-200 ease-out hover:-translate-y-0.5 hover:bg-white/70 hover:shadow-glass-pop";

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
