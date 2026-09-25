/**
 * "by swisscom" attribution: lowercase label beside the official Swisscom
 * dual-color lifeform emblem (blue #001AFF / red #E30613). The source JPG
 * sits on white; mix-blend-multiply dissolves that into the glacial gradient
 * behind it.
 */
export function SwisscomMark() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="font-inter text-sm font-medium tracking-tight text-swiss-ink/80">
        by swisscom
      </span>
      <img
        src="/swisscom.jpg"
        alt="Swisscom"
        className="h-7 w-7 select-none mix-blend-multiply"
        draggable={false}
      />
    </div>
  );
}
