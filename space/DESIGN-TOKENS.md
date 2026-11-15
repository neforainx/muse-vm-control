# Design tokens — VM Control Spaces (exact)

The Spaces in this repo are rebuilt by the receiving Muse from
specs, so **these numbers are the UI**. Copy them verbatim; do not
approximate. `space/reference-ui.html` is the same tokens rendered —
open it side by side with your build and compare screenshots.

## Shell

- Font: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`;
  mono: `ui-monospace, "SF Mono", Menlo, Consolas, monospace`.
- Top navbar: **one long floating glass capsule**, `position: sticky;
  top: 12px`, max-width 860px, padding 6px, radius 999px, glass fill +
  1px translucent stroke, `backdrop-filter: blur(22px)
  saturate(180%)`, soft shadow. Items share the capsule equally; the
  active item is a lighter glass pill inside it.
- Sub-navbar (per page): **floating pill at the bottom**, centered,
  `bottom: 34px`, sitting **above a 20px blur-gradient strip** fixed
  to the very bottom edge (mask fades upward). Capsule above the blur,
  never inside it.
- Page column: max-width 860px, side padding 14px, bottom padding
  ≥120px so content clears the sub-navbar.
- **One** shared dark/light toggle for the whole Space, in the top
  capsule. Never per-page toggles.

## Surfaces and type

- Cards: radius **22px**, glass fill `rgba(255,255,255,.05–.08)` on
  dark / `rgba(255,255,255,.4–.55)` on light, 1px translucent stroke,
  same backdrop blur, padding 18px, grid gap 12px.
- Big numbers: **40px, weight 700**, tight leading. Mid numbers 22px.
- Labels: **11px, weight 700, uppercase, letter-spacing .08em**,
  muted colour. Body 14px. Secondary text 12px muted.
- **No descriptive paragraphs.** Numbers + short labels only; a chart
  beats a sentence every time.
- Status dots: 9px circles — green `#30d158` ok, orange `#ff9f0a`
  warn, red `#ff453a` bad. Accent blue `#0a84ff`, teal `#64d2ff`.
- Resource rings (CPU/RAM/disk): 92px conic-gradient rings, 70px
  inner disc, % in 17px bold, label under.
- Chips: pill radius, glass fill, 11px semibold.
- Buttons (controller): radius 14px, glass, 14px semibold.

## Page shapes

- **Beranda:** VM status card → resource rings card → two-up
  scorecard (collected cash vs monthly target with progress bar;
  fleet count) → fleet list with heartbeat ages.
- **Kantor:** 3D office panel (flat, soft colours, L-shaped, only
  active agents) → KPI trio → Statistik list grouped by work
  category; unreadable source renders "not yet recorded" + the error,
  never a zero.
- **File:** one card: path header + disk chip, rows with type and
  size; denylisted paths show a refusal chip, not an error page.
- **Terminal:** card with session header + quick-command chips, mono
  output block (dark in both themes), sessions persist across reloads.
- **Pengendali VNC** (separate Space): frame only (1280×800,
  letterboxed) + **Copy** and **Paste** buttons. Nothing else — see
  `PENGENDALI-VNC.md`.

## Merge rule (from production)

When pages are merged into one Space, each page's own appearance is
carried over **1:1** — unify only the shell (top capsule, sub-navbars)
and the single theme toggle. A merge that redesigns a page is a
failed merge.
