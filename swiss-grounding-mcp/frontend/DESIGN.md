# Design

<!-- impeccable:design-schema 1 -->

## Status

Replacement visual world (redesign), brief-pinned by the user. Two reference
images were supplied and named explicitly: macOS/iCloud.com's dashboard
(icloud.com — light, saturated blue glass, rounded widget tiles of varying
size) and Gemini's ambient dark chat home (a single glowing radial accent
behind a pill composer). The user resolved the light/dark conflict between
the two toward **iCloud's light glass** and asked for **Gemini's dashboard
grid habit** for arranging widgets, so the tournament/roll process in
new-work.md is skipped — this is a pinned direction, not an open choice.

## World

**Apple Liquid Glass**, applied as a real interface language, not a css
"glassmorphism" decoration. Every discrete unit of content — the composer,
each chat turn, every widget — is a rounded glass tile floating on a soft
blue gradient canvas, the way iCloud.com's home dashboard tiles Mail, Photos,
Drive, and Notes. Multiple widgets in one assistant turn lay out as a
dashboard grid (varying tile spans by content density), not a stacked list.
The composer borrows Gemini's home-screen habit: a full-width pill, ambient
ellipsis and mic affordances, sitting on its own soft glow.

## Color strategy

**Committed.** A blue gradient (`#eef5ff → #cfe4ff → #9fc7ff`, radial-lit
from upper-left like the iCloud reference) owns the full canvas at all
times — it is not a hero-only treatment. Glass tiles sit on top as
translucent white (`rgba(255,255,255,0.55–0.7)`) with backdrop blur, letting
the blue field read through every surface. Accent is Apple system blue
(`#0A84FF`, already the `accent` token) for primary actions, links, focus,
and the user's own chat bubble. Semantic colors (amber for disruptions,
etc.) stay desaturated enough to sit inside a glass tile without breaking
the blue field.

Light theme only for this redesign (per brief); do not wire
`prefers-color-scheme` for this surface.

## Type

Keep the existing system stack (`-apple-system, BlinkMacSystemFont, Inter,
Segoe UI`). This is a deliberate exception to defaulting away from system
faces: the brief's world *is* Apple's own system UI, so the real San
Francisco/system stack is the correct, specific choice, not a lazy fallback.
Headings sit at Apple's confident, slightly heavy weight (`font-medium`/
`font-semibold`, tight tracking); body copy stays regular weight at
comfortable line height for scanning journey data.

## Material system ("glass tile")

Shared visual contract every tile (composer, chat turns, widget cards,
status banner) follows:

- Background: translucent white glass, `backdrop-blur-xl`.
- Radius: large and consistent — 24px (`rounded-3xl`) for outer tiles,
  16px (`rounded-2xl`) for nested elements (buttons-as-rows, chips).
- Border: 1px hairline, `rgba(255,255,255,0.6)` on the light side, giving
  the glass a lit top edge.
- Shadow: soft, offset, colored from the blue field (never a flat gray
  card shadow) — depth, not decoration.
- Interactive rows/buttons inside a tile get a subtle lift + brighten on
  hover, never a hard border swap.

## Layout: dashboard grid

Assistant turns render their widgets in a responsive CSS grid (iCloud
habit), not a vertical stack:

- Rich/dense widgets (train connections + route map, flight-to-train,
  station board) span the full width or two columns on wide viewports.
- Compact widgets (fares, disruptions list, airport guidance, a single
  flight) take one column and pack side by side.
- Grid collapses to a single column below the tablet breakpoint (desktop
  is the priority target; mobile must remain usable, not optimized).

## Composer

A full-width glass pill (Gemini habit) with a soft ambient blue glow
seated behind it, most visible in the empty-state hero and persisting,
quieter, as the sticky footer once a conversation starts. Icon affordances
(send) sit inside the pill; the blue accent marks the active/primary
action.

## Motion

One authored moment: tiles and the composer glow softly settle in
(opacity + slight translate/scale, exponential ease-out) on first
appearance; nothing re-animates on every render. Hover states move at a
quick, quiet ease.

## Voice glow (intentional exception)

While voice mode is active — listening, processing, or speaking — an
ambient, colorful glow animates around the viewport's edges, masked clear
in the center so the conversation underneath stays fully visible. Its
five-color rainbow palette (`#7c6bff` purple-blue, `#ff5f7e` rose,
`#ff8a3d` orange, `#ffd23f` yellow, `#ff4fa3` pink) is a deliberate
departure from the rest of the app's blue-gradient, desaturated-semantic
color system, scoped only to this one voice-mode indicator — it signals a
live, energetic listening state the way a system blue accent could not.
Do not fold it into the blue palette during a consistency pass; it is a
one-off by design.

## Browser surfaces

Selection, focus ring, and scrollbar are themed from the blue accent, not
left at browser defaults.
