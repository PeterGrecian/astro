# Repo boundaries and reuse — direction notes

Across the personal stack there are several repos that touch cameras,
displays, and Pi devices in overlapping ways. This doc captures the
direction of travel, not the current state (which is mostly
copy-paste duplication).

Drafted 2026-06-17 from notes in `TODO-other.md`.

## The repos and what they do

- **`astro`** (this repo) — scientific astronomy: FITS, plate
  solving, derot stacks, brightness arcs, per-night deliverables
  for live cameras (`astrocam`, `eclipticam-v{1,3w}`) and the
  decommissioned `starcam`. Has the unified pipeline + 4-stage
  architecture.
- **`Berrylands/gardencam`** — historical Pi-side capture daemons
  for skycam (still live, runs every day) and the old
  `starcam_night_daemon`. The capture-unification plan
  (`design/capture-unification.md`) is gradually moving scientific
  capture into `astro/astro/capture/`; skycam stays put.
- **`photography/timelapse/`** — pretty-picture timelapse stuff,
  including a `starcam/` subdir that is intentionally different
  from this repo's scientific work (different inputs, different
  goals, different tools).
- **`mywebsite`** — the Lambda + routes serving
  `www.petergrecian.co.uk`, including the per-camera pages, the
  skycam advanced player, the astro pages.

## Patterns worth lifting

### The skycam advanced player

Already captured as a reusable pattern — see
`design/meta-conventions.md` and the
[astro-website-player memory](file:///home/peter/.claude/projects/-home-peter/memory/project_astro_website_player.md).
The web player today is imported directly by astro routes
(`render_astro_player` calls `render_skycam_player`). Refactor it
into a shared component when a third consumer appears.

### The skycam calendar

The per-day calendar layout on `/skycam` is the model the
eclipticam (and astrocam) per-night pages should adopt. Currently
each astro camera renders its own bespoke calendar in
`lambda/routes/astro.py:render_astro_camera_calendar`. The skycam
calendar in `lambda/routes/gardencam.py` is more polished
(thumbnails, day/week navigation, hour-strip).

Direction: extract the skycam calendar into a shared component
that both `/skycam` and `/astro/<camera>` consume, parameterised by
S3 bucket + prefix + thumbnail-key pattern. Same pattern as the
player — start with inline-import, refactor when there's a clear
third consumer (likely `astrocam`).

### The stereo viewer

Lives in `photography/` somewhere. Will be reused by Splay (see
`design/splay-standalone-direction.md` shader list — stereo as a
single GLSL shader with mode selector). When Splay lands, the
photography stereo viewer should either redirect to Splay or get
merged into it. Defer until Splay exists.

## Extraction targets

### Skycam extraction from Berrylands

Skycam is stable and live. Its current home in
`Berrylands/gardencam/` is awkward because:

- Berrylands accumulates Pi-side daemons across many projects
  (servos, sensors, cameras) and Skycam is the largest of them.
- New skycam work (the advanced player iterations, the rerender
  pipeline) increasingly needs to interact with mywebsite-side
  code, not other Berrylands code.
- The `astro.capture` module is pulling scientific capture out of
  Berrylands — the symmetric move for cosmetic capture (skycam) is
  a separate `skycam/` repo.

Direction: when skycam needs significant work next, extract it
into its own repo (`skycam/`), factorise the capture +
re-render + S3 pipeline cleanly, and only then build on it.
Don't attempt extraction *while* doing the work — extract first,
then iterate.

### gardencam rationalisation

The `Berrylands/gardencam` name covers three different things:
- The skycam camera daemon (above).
- The "gardencam" daily-image gallery (older, low-cadence).
- Various legacy hardware glue.

After skycam extraction, what remains under "gardencam" is small
enough to either fold into Berrylands proper or absorb into the
photography repo.

## Cross-cutting principle

**Two runtimes, shared JSON.** Where the same data is consumed by
multiple frontends (web Lambda, future Splay, possibly an Android
app one day), the canonical contract is the JSON + S3 layout in
`design/meta-conventions.md`. Frontends don't share code — they
share schemas. That keeps each idiomatic in its runtime without
forcing a lowest-common-denominator library.

## Open boundary questions

Carried over from TODO.md 2026-06-20 — these are boundary decisions to
make as `astro.capture` matures, not tasks to schedule:

- **The astro / `Berrylands/gardencam` / `super/services` boundary.**
  gardencam (Pi capture) is gradually emptying as `astro.capture`
  absorbs the camera daemons; `super/services` owns the async
  file-transfer queue. The `pilib` / `piservices` focused-Pi-repo idea
  is still open — revisit when gardencam is nearly empty.
- **Where `astrocam-capture.service` lives.** Today it's in `astro/`.
  Once `astro.capture` takes over capture, the systemd unit may belong
  in `ansible/` (fleet config) rather than the code repo. Decide at the
  capture-unification cutover.

## Not now

Anything in this doc is design-level direction, not action items.
The pull toward "rationalise everything before doing more work"
is real but premature — skycam is still earning its keep where it
is, and the website astro routes are not yet duplicative enough to
need a calendar extraction. Revisit when the next concrete pain
shows up.
