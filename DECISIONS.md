# Decisions

Architectural choices, each with date + rationale. Only the
load-bearing ones; small implementation details belong in code.

## 2026-05-22 — Astro community tooling over bespoke code

**Decision.** Standardise on FITS + astrometry.net + Siril/oiiotool
for all astronomy image processing past the raw Bayer `.npy` buffer.
Drop plans for bespoke geometric pole-seeking and bespoke `splay`
plugin support.

**Why.**
- The previous session built a geometric perpendicular-bisector
  pole-finder from arc segments. It worked but is *less* than what
  `solve-field` gives for free: SIP-polynomial lens distortion, WCS,
  star catalog cross-reference.
- The Pi V1 lens has heavy barrel distortion. SIP up to 4th/5th
  order handles this; our home-built code does not.
- Visual inspection of stretched faint-star images is a solved
  problem (Siril asinh, ASIFITSView auto-stretch, FITS Liberator).
  Rebuilding it in GIMP recipes was a hack.
- Time spent on bespoke geometry is time not spent on capture,
  pre-processing, and dark frames — the actual bottlenecks.

**How to apply.**
- New code reads/writes FITS, not `.npy`, past the daemon's tmpfs
  buffer.
- Plate solving is `solve-field` invoked from `bin/platesolve`,
  not a custom geometric solve.
- Display tools are external (Siril, DS9, ASIFITSView, djv). No
  in-repo viewer.
- `oiiotool` for format conversions where needed.

## 2026-05-22 — Repo separation from photography/timelapse

**Decision.** Astro work lives at `~/astro/`, sibling to
`~/photography/timelapse/`, not nested under it.

**Why.** Different goals (measurement vs art), different inputs
(Bayer raw vs JPEG), different outputs (FITS+geometry vs MP4),
different tooling (astrometry.net+Siril vs ffmpeg). Mixing them
would muddle both repos' CLAUDE.md context.

## 2026-05-22 — Per-repo venv, no global Python deps

**Decision.** `~/astro/.venv/` (gitignored), pinned via
`requirements.txt`. Activate before running utilities.

**Why.** astropy + opencv + numpy versioning across repos has bitten
us. Isolation makes the repo portable to a future Pi4.

## 2026-05-22 — Night dir = noon-rollover, single date per night

**Decision.** A "night" is a single date string covering local-noon
to local-noon (Europe/London). The night of 2026-05-21 is
21st 12:00 → 22nd 12:00.

**Why.** Currently a night's data is split across two date dirs
(`night/2026-05-21/` and `night/2026-05-22/`) because UTC midnight
falls in the middle of the observation. Confusing. Noon-rollover
puts the whole session under one date.

**How to apply.** `bin/night-dir` is the canonical translator from
"a timestamp anytime during the observation" to "which night was
that?". All accumulator outputs are namespaced by night, not by UTC
date.

## 2026-05-22 — Drop bespoke splay plugin

**Decision.** No splay plugin. Use djv (EXR), Siril (FITS), or
oiiotool conversions instead.

**Why.** Splay was a "build our own viewer" line of work. The astro
community has better viewers already. Time better spent elsewhere.
