/**
 * Swisscom dual-color emblem: a four-blade vortex in Swisscom blue with the
 * trailing blade in signal red, paired with the lowercase "by swisscom"
 * attribution.
 */
export function SwisscomMark() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="font-inter text-sm font-medium tracking-tight text-swiss-ink/80">
        by swisscom
      </span>
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px]" role="img" aria-label="Swisscom">
        <path
          fill="#001AFF"
          d="M12 2C17.52 2 22 6.48 22 12h-5.2A4.8 4.8 0 0 0 12 7.2V2z"
        />
        <path
          fill="#001AFF"
          d="M22 12c0 5.52-4.48 10-10 10v-5.2a4.8 4.8 0 0 0 4.8-4.8H22z"
        />
        <path
          fill="#001AFF"
          d="M12 22C6.48 22 2 17.52 2 12h5.2A4.8 4.8 0 0 0 12 16.8V22z"
        />
        <path
          fill="#E30613"
          d="M2 12C2 6.48 6.48 2 12 2v5.2A4.8 4.8 0 0 0 7.2 12H2z"
        />
      </svg>
    </div>
  );
}
