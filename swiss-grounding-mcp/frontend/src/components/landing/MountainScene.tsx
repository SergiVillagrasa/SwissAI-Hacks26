import { useEffect, useRef, type CSSProperties } from "react";

interface AlpsLayer {
  /** Gradient stops: haze tint at the ridge line fading into the sheet color. */
  from: string;
  to: string;
  /** Ridge y where the haze tint is full strength (userSpaceOnUse). */
  hazeFrom: number;
  d: string;
  /** Max horizontal pointer-parallax travel in px (near layers move most). */
  parallax: number;
  /** Curtain-split transition delay in ms (foreground leads, strata follow). */
  delay: number;
  /** Paper drop-shadow cast onto the layer behind. */
  shadow: string;
}

/**
 * Tectonic strata: five full-width zig-zag ridges of cut paper, each drawn as
 * one silhouette spanning the whole viewport. Every layer renders twice —
 * once clipped to the left half, once to the right — so `.landing[data-open]`
 * can split the range at the center seam and glide the halves ±55vw apart.
 * Foreground sheets lead the split; the opened center stays empty.
 */
const LAYERS: AlpsLayer[] = [
  {
    // Faintest mist crest — furthest sheet, dissolves into the pure sky
    from: "#FFFFFF",
    to: "#F6FAFD",
    hazeFrom: 140,
    d: "M0 720 L0 300 L90 210 L180 300 L270 170 L360 290 L450 150 L540 280 L630 140 L720 270 L810 160 L900 280 L990 180 L1080 290 L1170 200 L1260 300 L1350 220 L1440 310 L1440 720 Z",
    parallax: 6,
    delay: 240,
    shadow: "drop-shadow(0 -3px 6px rgba(24, 52, 78, 0.06))",
  },
  {
    // Layer 1 — pure sky fading into faint glacial mist
    from: "#FFFFFF",
    to: "#EAF1F7",
    hazeFrom: 230,
    d: "M0 720 L0 380 L100 300 L200 385 L300 250 L400 370 L500 230 L600 360 L700 250 L800 360 L900 240 L1000 350 L1100 270 L1200 370 L1300 290 L1440 380 L1440 720 Z",
    parallax: 10,
    delay: 180,
    shadow: "drop-shadow(0 -4px 8px rgba(24, 52, 78, 0.10))",
  },
  {
    // Layer 2 — soft glacial slate
    from: "#E7EFF6",
    to: "#D6E3EF",
    hazeFrom: 320,
    d: "M0 720 L0 460 L90 380 L190 470 L290 340 L390 455 L490 320 L590 445 L690 350 L790 450 L890 330 L990 445 L1090 360 L1190 460 L1290 380 L1390 465 L1440 420 L1440 720 Z",
    parallax: 16,
    delay: 120,
    shadow: "drop-shadow(0 -5px 10px rgba(24, 52, 78, 0.14))",
  },
  {
    // Layer 3 — muted alpine blue
    from: "#BCCEDD",
    to: "#9BB3C9",
    hazeFrom: 415,
    d: "M0 720 L0 540 L110 460 L220 550 L330 430 L440 545 L550 415 L660 540 L770 445 L880 545 L990 430 L1100 540 L1210 460 L1320 555 L1440 500 L1440 720 Z",
    parallax: 24,
    delay: 60,
    shadow: "drop-shadow(0 -6px 12px rgba(24, 52, 78, 0.18))",
  },
  {
    // Layer 4 — deep navy foreground, nearest sheet
    from: "#4E6E8C",
    to: "#18344E",
    hazeFrom: 540,
    d: "M0 720 L0 630 L120 560 L240 645 L360 545 L480 635 L600 540 L720 630 L840 555 L960 640 L1080 565 L1200 645 L1320 580 L1440 640 L1440 720 Z",
    parallax: 34,
    delay: 0,
    shadow: "drop-shadow(0 -8px 16px rgba(24, 52, 78, 0.24))",
  },
];

function LayerSvg({ layer, index }: { layer: AlpsLayer; index: number }) {
  return (
    <svg
      viewBox="0 0 1440 720"
      preserveAspectRatio="xMidYMax slice"
      className="alps-svg"
      style={{ filter: layer.shadow }}
      aria-hidden="true"
      focusable="false"
    >
      <path d={layer.d} fill={`url(#alp-g${index})`} />
    </svg>
  );
}

export function MountainScene() {
  const ref = useRef<HTMLDivElement>(null);

  // Pointer parallax: layers drift against the cursor, eased through a lerp so
  // the paper sheets feel like they sit at different depths. Disabled entirely
  // under prefers-reduced-motion.
  useEffect(() => {
    const node = ref.current;
    const reduceMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!node || reduceMotion) return;

    let targetX = 0;
    let targetY = 0;
    let x = 0;
    let y = 0;
    let raf = 0;

    const onMove = (event: PointerEvent) => {
      targetX = (event.clientX / window.innerWidth) * 2 - 1;
      targetY = (event.clientY / window.innerHeight) * 2 - 1;
    };

    const tick = () => {
      x += (targetX - x) * 0.06;
      y += (targetY - y) * 0.06;
      if (Math.abs(targetX - x) > 0.0005 || Math.abs(targetY - y) > 0.0005 || x !== 0 || y !== 0) {
        node.style.setProperty("--px", x.toFixed(4));
        node.style.setProperty("--py", y.toFixed(4));
      }
      raf = requestAnimationFrame(tick);
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    raf = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={ref} className="alps-scene" aria-hidden="true">
      {/* Shared gradient defs: each ridge fades from a haze tint at its peaks
          into its pinned strata color at the base. */}
      <svg width="0" height="0" className="absolute" aria-hidden="true" focusable="false">
        <defs>
          {LAYERS.map((layer, i) => (
            <linearGradient
              key={i}
              id={`alp-g${i}`}
              gradientUnits="userSpaceOnUse"
              x1="0"
              y1={layer.hazeFrom}
              x2="0"
              y2="720"
            >
              <stop offset="0" stopColor={layer.from} />
              <stop offset="1" stopColor={layer.to} />
            </linearGradient>
          ))}
        </defs>
      </svg>
      {LAYERS.map((layer, i) => (
        <div
          key={i}
          className="alps-layer"
          style={{ "--plx": `${layer.parallax}px` } as CSSProperties}
        >
          <div
            className="alps-half alps-half--left"
            style={{ transitionDelay: `${layer.delay}ms` }}
          >
            <LayerSvg layer={layer} index={i} />
          </div>
          <div
            className="alps-half alps-half--right"
            style={{ transitionDelay: `${layer.delay}ms` }}
          >
            <LayerSvg layer={layer} index={i} />
          </div>
        </div>
      ))}
    </div>
  );
}
