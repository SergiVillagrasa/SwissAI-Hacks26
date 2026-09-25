import { useEffect, useRef, type CSSProperties } from "react";

interface AlpsFacet {
  fill: string;
  d: string;
}

interface AlpsLayer {
  fill: string;
  d: string;
  facets: AlpsFacet[];
  /** Max horizontal pointer-parallax travel in px (near layers move most). */
  parallax: number;
  /** Curtain-sweep transition delay in ms (front curtain opens first). */
  delay: number;
  /** Paper drop-shadow cast onto the layer behind. */
  shadow: string;
}

/**
 * Paper-cut alpine range: five stacked vector ridges, each drawn as one
 * full-width silhouette. Every layer is rendered twice — once clipped to the
 * left half of the viewport, once to the right — so `.landing[data-open]` can
 * sweep the halves apart like curtains. Peaks are tallest near x=720 so the
 * closed range reads as an amphitheatre framing the search pill, and splitting
 * the central summit opens the canyon.
 */
const LAYERS: AlpsLayer[] = [
  {
    // Haze crest — furthest and tallest
    fill: "#E9F3FA",
    d: "M0 720 L0 316 L56 288 L128 310 L204 236 L284 276 L352 216 L428 268 L508 168 L584 224 L660 148 L736 208 L812 132 L886 196 L958 158 L1036 222 L1112 176 L1192 232 L1268 200 L1344 248 L1440 214 L1440 720 Z",
    facets: [],
    parallax: 6,
    delay: 220,
    shadow: "drop-shadow(0 -3px 6px rgba(11, 37, 69, 0.06))",
  },
  {
    // Back crests
    fill: "#D9E8F5",
    d: "M0 720 L0 372 L64 344 L140 372 L222 292 L306 338 L382 288 L462 350 L544 258 L622 314 L700 256 L778 310 L856 244 L936 302 L1014 268 L1094 326 L1172 286 L1254 336 L1332 302 L1440 336 L1440 720 Z",
    facets: [
      { fill: "rgba(255,255,255,0.55)", d: "M838 262 L856 244 L876 266 L862 260 L850 268 Z" },
      { fill: "rgba(255,255,255,0.45)", d: "M682 274 L700 256 L720 278 L706 272 L694 280 Z" },
    ],
    parallax: 10,
    delay: 165,
    shadow: "drop-shadow(0 -4px 8px rgba(11, 37, 69, 0.10))",
  },
  {
    // Mid peaks
    fill: "#94A8BD",
    d: "M0 720 L0 452 L84 424 L168 456 L252 380 L344 428 L428 374 L512 440 L596 362 L676 420 L756 350 L838 412 L918 364 L1000 424 L1082 380 L1166 436 L1250 396 L1336 440 L1440 412 L1440 720 Z",
    facets: [
      { fill: "rgba(233,243,250,0.5)", d: "M732 372 L756 350 L784 376 L766 368 L750 378 Z" },
      { fill: "rgba(233,243,250,0.4)", d: "M574 382 L596 362 L620 386 L604 378 L590 388 Z" },
      { fill: "rgba(233,243,250,0.4)", d: "M232 398 L252 380 L274 402 L260 396 L246 404 Z" },
    ],
    parallax: 16,
    delay: 110,
    shadow: "drop-shadow(0 -5px 10px rgba(11, 37, 69, 0.14))",
  },
  {
    // Fore slopes
    fill: "#5A728A",
    d: "M0 720 L0 544 L96 518 L190 550 L284 480 L384 528 L474 478 L566 544 L662 468 L748 528 L838 462 L928 520 L1016 482 L1106 540 L1196 498 L1288 546 L1378 510 L1440 536 L1440 720 Z",
    facets: [
      { fill: "rgba(148,168,189,0.6)", d: "M806 486 L838 462 L872 490 L848 482 L828 494 Z" },
      { fill: "rgba(148,168,189,0.5)", d: "M636 490 L662 468 L690 494 L668 486 L652 496 Z" },
      { fill: "rgba(148,168,189,0.4)", d: "M452 496 L474 478 L498 500 L482 494 L468 502 Z" },
    ],
    parallax: 24,
    delay: 55,
    shadow: "drop-shadow(0 -6px 12px rgba(11, 37, 69, 0.18))",
  },
  {
    // Deep navy base — nearest paper sheet
    fill: "#0B2545",
    d: "M0 720 L0 636 L120 612 L240 644 L360 596 L480 634 L600 590 L720 628 L840 588 L960 626 L1080 598 L1200 634 L1320 608 L1440 628 L1440 720 Z",
    facets: [
      { fill: "rgba(22,53,95,0.85)", d: "M560 720 L600 590 L720 628 L720 720 Z" },
      { fill: "rgba(22,53,95,0.85)", d: "M960 626 L1080 598 L1200 634 L1200 720 L960 720 Z" },
      { fill: "rgba(22,53,95,0.7)", d: "M240 644 L360 596 L480 634 L480 720 L240 720 Z" },
    ],
    parallax: 34,
    delay: 0,
    shadow: "drop-shadow(0 -8px 16px rgba(11, 37, 69, 0.24))",
  },
];

function LayerSvg({ layer }: { layer: AlpsLayer }) {
  return (
    <svg
      viewBox="0 0 1440 720"
      preserveAspectRatio="xMidYMax slice"
      className="alps-svg"
      style={{ filter: layer.shadow }}
      aria-hidden="true"
      focusable="false"
    >
      <path d={layer.d} fill={layer.fill} />
      {layer.facets.map((facet, i) => (
        <path key={i} d={facet.d} fill={facet.fill} />
      ))}
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
            <LayerSvg layer={layer} />
          </div>
          <div
            className="alps-half alps-half--right"
            style={{ transitionDelay: `${layer.delay}ms` }}
          >
            <LayerSvg layer={layer} />
          </div>
        </div>
      ))}
    </div>
  );
}
