# Decisions

Architectural choices, each with date + rationale. Only the
load-bearing ones; small implementation details belong in code.

## 2026-06-16 — Canonical storage layout: date-first, YYYY/MM/DD, per-camera artefacts

**Decision.** All frames and per-night artefacts live under a single
NFS-mounted root:

```
~/astro-frames/YYYY/MM/DD/<camera>/{day,night}/HH/HH-MM-SS.fits.fz
~/astro-frames/YYYY/MM/DD/<camera>/brightness.csv
~/astro-frames/YYYY/MM/DD/<camera>/state.json
```

The date `YYYY/MM/DD` is the noon-rollover night
(`night_of(utc) = (utc - 12h).date()`), split across three path
components. Per-camera `brightness.csv` and `state.json` live
*outside* the `day|night/` mode dirs. S3 deliverables tier mirrors
the same shape: `<camera>/nights/YYYY/MM/DD/...`. Cold tier the same.

Full schema, rationale, and migration plan in
`design/storage-layout.md`.

**Why.**
- **Date-first, not mode-first or camera-first.** One night = one
  dir across all cameras. Aggregation works at every level (year /
  month / day). Bounded fanout per level — friendlier to filesystem
  tools and S3 listing than a flat per-date layout would become at
  multi-year scale.
- **Split `YYYY/MM/DD`** (vs flat `YYYY-MM-DD`). Long-term win: a
  year of data fits naturally under one top dir, a month under one
  sub-dir. Trivial cost — CLI / state.json / logs keep the flat
  ISO string form; translation to path happens at filesystem
  boundaries only.
- **brightness.csv outside mode dirs.** Breaks the bootstrap
  circularity: if brightness.csv were under `day/` or `night/`,
  the state daemon couldn't read dusk's day-mode samples to decide
  the day→night transition. Mode-agnostic CSV decouples the signal
  from the decision the signal drives.
- **state.json per camera, not global.** Each camera's mode is its
  own decision. A host-level summary, if needed, is derived. No
  authoritative shared blob to corrupt or contend on.
- **UTC `HH/HH-MM-SS.fits.fz` preserved** rather than 24:00-style
  hour extension for sort order. The 23→00 wraparound becomes a
  five-line sort helper in `astro.frames`; the alternative makes
  every external tool that parses time disagree with the path.

**How to apply.**
- New captures land at the new path immediately once
  `astro-capture` ships.
- Existing data on puppy under `~/<camera>-frames/{day,night}/<date>/...`
  is migrated one-night-at-a-time via rsync; `astro.frames` gains
  a legacy reader for the old layout until migration completes.
- `camera.json` gains `frames_root` pointing at the unified tree
  and a `processing.host` field (`"self"` or a named host) so the
  "where stage 3 runs" decision is config, not topology.
- Cold-archive paths under `cold/<camera>/<mode>/...` adopt
  `YYYY/MM/DD/` too — keep the convention consistent.

## 2026-06-16 — Four-stage architecture, config-driven, state-record-driven

**Decision.** The pipeline is four separated concerns, each one
Python executable in `bin/`, each driven by config files + a shared
state record. Production behaviour reads from config; CLI flags are
for dev/test overrides only.

| # | Stage | Where | Executable | Cadence |
|---|---|---|---|---|
| 1 | Day/night state controller | each host | `bin/astro-state` | continuous daemon |
| 2 | Capture + on-Pi first-pass | camera Pi | `bin/astro-capture` | continuous daemon, state-driven |
| 3 | Twice-daily processing + publish | NFS host | `bin/astro-process` | continuous daemon, fires on dusk/dawn transitions |
| 4 | Storage management (squash, cold, prune) | NFS host | `bin/astro-storage` | weekly timer (or daily under disk pressure) |

Per-camera state lives at `<night>/<camera>/state.json` in the
canonical NFS tree (see storage layout decision above). Stage 1
writes; stages 2–4 read their own camera's file (and, for stage 3
on a multi-camera processing host, the state.json of every camera
assigned to it). Per-frame brightness lives in
`<night>/<camera>/brightness.csv`, written by stage 2, read by
stage 1.

**Why.**
- Today's collection of timers (per-camera capture services, per-camera
  publish timers at 07:00 BST, `to-fits-sweep`) maps loosely onto
  these four concerns but with overlapping scopes and per-camera
  duplication. The four-stage shape names the concerns directly.
- Driving stages 2 and 3 from a state record (rather than wall-clock
  timers) means dusk processing happens automatically as the sun
  goes down, not at a guessed time. Adding a new camera or moving
  one to a different location costs zero scheduling work.
- Config-only specialisation means a new camera = a new config dir,
  not new code. The dev/test flag carve-out is explicit so it doesn't
  silently become a production knob.
- Python everywhere (with thin shell wrappers only for systemd glue)
  keeps the cognitive load on one language.

**How to apply.**
- New work that previously went into `bin/nightly-cam` or
  `bin/publish-night-cam` goes into `astro.process` (the module
  behind `bin/astro-process`). Those two CLIs stay as compatibility
  shims until callers move over.
- New capture daemons live in `astro.capture`; per-camera Pi-side
  daemons (`eclipticam/v3w_night_daemon.py`, `astrocam/capture.py`)
  collapse into `astro-capture` driven by `camera.json` + the state
  record.
- `astro-state` and `astro-storage` are new executables.
- Migration is incremental: each stage can ship independently.
  Migration order in TODO.md.

## 2026-06-16 — One branch, one codebase

**Decision.** `unify-cameras` is merged into `main` and deleted. The
unified pipeline (`bin/nightly-cam`, `bin/publish-night-cam`, shared
`astro/` package, per-camera `camera.json`) is the only code path.

**Why.** Two-branch development was always meant to converge. The
unified pipeline has been running in production on eclipticam (v3w
publish timer at 07:00 BST since 2026-06-15) and is camera-parametric
end-to-end. astrocam has the same publish timer wired. Keeping a
"main" that lacks the shared code only invites drift and
half-applied bugfixes.

**How to apply.** New work lands on `main`. The starcam-only legacy
pipeline is gone (see next decision). Reprocessing historical
starcam nights uses `bin/nightly-cam --camera starcam` like any
other camera.

## 2026-06-16 — eclipticam v1 and v3w are two cameras, not one with subcams

**Decision.** Drop the `subcams: {v1: {...}, v3w: {...}}` shape and
`cfg.subcam("v3w")` view. `eclipticam-v1` and `eclipticam-v3w` are
two first-class CameraConfigs that happen to share a host. Each has
its own `camera.json`, `occlusion.json`, `privacy.json`. The `--subcam`
CLI flag is removed.

**Why.** The subcam abstraction added a special case to every CLI,
to `astro/frames.py` (percam layout required a subcam arg), and to
privacy lookup. The only thing the two cameras genuinely share is a
host and a location — neither of which justifies coupling the data
model. With them split, every camera in the fleet looks the same to
the pipeline. The per-host concerns (v3w gating v1, cross-camera
state) move into a future `host.json` (see `design/capture-unification.md`),
which is where they belong.

**How to apply.** New camera dirs are flat: `eclipticam-v1/`,
`eclipticam-v3w/`. CLIs take `--camera eclipticam-v3w`. Shared host
config (if needed) lives in `host.json` and is loaded separately
from `CameraConfig`.

## 2026-06-16 — Delete legacy starcam-only pipeline

**Decision.** Remove `bin/pipeline-night`, `bin/pipeline-hour`,
`bin/derot-patches`, `bin/fit-pole` (the bootstrap loop), and the
parked Gaia catalog-match exploration (`bin/wcs-from-anchors`,
`bin/cross-match-gaia`, `bin/find-known-stars`, `bin/match-from-capella`,
`bin/relative-pattern`, `bin/sky-chart-*`, `bin/orient-check`,
`bin/overlay-gaia*`, `bin/photo-compare`, `bin/convert_starcam.py`,
`bin/convert_legacy.py`, and assorted `streak_*` / `photon_*` /
`derot-night|stack|windows|sim` / `arc-walk` / `chain-tracks` /
`iter-stack-sweep` / `find-pivot-coarse` scripts).

**Why.** Starcam is decommissioned and the unified pipeline supersedes
all of these. The previous policy ("don't delete until side-by-side-
validated on real starcam nights") was sensible while starcam was
live; with the source camera gone and historical data cold-archived,
the legacy tools are no longer load-bearing. The parked Gaia work
(`TODO_fit.MD`) is preserved in git history and can be revived if
catalog matching becomes a goal again.

**How to apply.** Deletions land in the same commit as a TODO.md note
recording where the parked Gaia exploration left off, so it can be
resurrected from history if needed. `legacy/` stays — it's already a
quarantined reference dir and nothing imports from it.

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
