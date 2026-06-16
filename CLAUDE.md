# astro — project context

Astronomy image processing for a fleet of Pi-mounted
cameras. 

Related content at `~/photography/timelapse/starcam/` and '~/Berrylands/gardencam'

Aim is for daily/nightly deliverables to ~/mywebsite, development of algorithms
and long term artifacts. 

## Cameras

| Camera | Host | Sensor | Status | Notes |
|---|---|---|---|---|
| `astrocam` | astrocam (Pi 4) | IMX219 | live | Transparent cover; 24h capable. 8×1.2 s coadd at night. |
| `eclipticam-v1` | eclipticam | OV5647 | live | Day mode (sun-pointing candidate; future dark filter). |
| `eclipticam-v3w` | eclipticam | IMX708 (Module 3 Wide) | live | Night-mode streaming capture (`picamera2`), 55 s exposures. |
| `starcam` | puppy (was zeropi) | OV5647 | **decommissioned** | Raw data cold-archived; see `COLD_STORAGE.md`. CameraConfig kept so historical nights still process. |

`eclipticam-v1` and `eclipticam-v3w` are two CameraConfigs that
happen to share a host. They are not nested under one parent — each
has its own `camera.json`, occlusion, privacy. (Old `subcams` shape
removed 2026-06-16; see DECISIONS.md.)

## Pipeline — 4 separated concerns

Each stage is one Python executable in `bin/`, specialised by
config files. Command-line flags are for development and testing
only; production runs read everything from config + the shared
state record.

| # | Stage | Where it runs | Executable | Cadence |
|---|---|---|---|---|
| 1 | Day/night state controller | each Pi (and each NFS host) | `bin/astro-state` | continuous daemon |
| 2 | Capture (+ on-Pi first-pass: Rice-compress to `.fits.fz`, bin) | camera Pi | `bin/astro-capture` | continuous daemon, driven by state |
| 3 | Twice-daily processing (deliverables + publish) | NFS / CPU host (puppy, muppet) | `bin/astro-process` | continuous daemon, fires at dawn + dusk transitions |
| 4 | Storage management (squash, cold-archive, retention) | NFS host | `bin/astro-storage` | weekly (or daily under disk pressure) |

```
                ┌──────────────────────────────────────┐
                │  state record (shared file / KV)     │
                │  per-camera: mode, last-transition,  │
                │  current night, pending work flags   │
                └──────────────────────────────────────┘
                       ▲           ▲           ▲
                       │           │           │
   ┌───────────────────┼───────────┼───────────┼──────────────┐
   │                   │           │           │              │
[astro-state]    [astro-capture] [astro-process]  [astro-storage]
   Pi/NFS              Pi          NFS host           NFS host
   sets mode           reads mode   reads transition  reads age/size
                       → buffer    → deliverables    → squash / cold
                          to NFS    → S3 → website
```

**Stage 1 — state controller.** Computes day/night/dusk/dawn from
sun altitude (per camera location). Writes per-camera mode and
transition events to the state record. Today this logic lives
inline in `eclipticam/capture.py`; target is `astro.state` as a
standalone module driving the state record.

**Stage 2 — capture.** Continuous daemon. Holds the camera open
(`picamera2` streaming), reads its mode from the state record,
applies the mode's exposure/cadence/format from `camera.json`.
First-pass on-Pi processing (Rice-compress to `.fits.fz`, 2×2
bin) happens before landing on NFS. pi4 (astrocam) and pi5
(eclipticam) have enough CPU for this; if a pi1 were ever
reinstated, first-pass would move to the NFS host (the historical
`to-fits-sweep` path on puppy).

**Stage 3 — twice-daily processing.** Continuous daemon on the
NFS host. Watches the state record; when stage 1 logs a dusk-end
or dawn-end transition for a camera, runs the deliverables
pipeline for the just-finished window: stacks, sweeps, brightness
plot, `summary.json`, S3 upload. Today this is wired as a 07:00
BST systemd timer per camera; target is event-driven via the
state record so dusk processing also happens automatically.

**Stage 4 — storage management.** Periodic (weekly default,
daily under disk pressure). Squashes raw → sum-N derivatives,
moves to cold tiers, prunes per the retention policy. Reads
disk-pressure and per-night age from the state record /
filesystem; writes back what it moved.

## NFS layout

Canonical tree (full schema in `notes/storage-layout.md`):

```
~/astro-frames/YYYY/MM/DD/<camera>/
                          ├── brightness.csv
                          ├── state.json
                          ├── day/HH/HH-MM-SS.fits.fz
                          └── night/HH/HH-MM-SS.fits.fz
```

- `YYYY/MM/DD/` — noon-rollover night
  (`night_of(utc) = (utc - 12h).date()`), split across three path
  components. CLI / state / logs use the flat `YYYY-MM-DD` string
  form; translation to path happens at filesystem boundaries.
- `<camera>/` — top-level camera (`astrocam`, `eclipticam-v1`,
  `eclipticam-v3w`). One night dir aggregates every camera.
- `brightness.csv`, `state.json` — outside the mode dirs so they
  survive day↔night transitions without a circular path dependency.
- `<frame>` — `HH-MM-SS.fits.fz` (UTC). Legacy starcam (Pi 1B,
  decommissioned) wrote `<epoch_ms>.npy` converted to `.fits.fz`
  on puppy; reachable via the legacy reader in `astro.frames`.

The 23→00 wraparound inside a night is handled by
`astro.frames.sort_hours_for_night(hours)` — keys by
`(hour - 12) % 24`. Paths on disk stay standard UTC so FITS
headers and external tools round-trip without surprise.

## Config files drive everything

Production behaviour is read from config. Command-line flags exist
for dev/test only (re-running a specific night, restricting to a
UTC window, overriding the camera, etc).

Per-camera (`<camera>/`):
- `camera.json` — **mandatory.** Sensor, Bayer, resolution, plate
  scale, pedestal, frames root, night layout, S3 target, per-mode
  capture parameters (exposure / cadence / gain / format).
- `occlusion.json` — masked regions (trees, eaves, neighbours' chimneys).
- `quality.json` — per-camera quality thresholds (rarely used;
  gating is mostly derived).
- `privacy.json` — publication crop spec; `publish` refuses
  uncropped images when present.
- `location.json` — lat/lon for sun/moon altitude, used by stage 1.

Per-host (one file per Pi / NFS host, future):
- `host.json` — which cameras live here, cross-camera rules
  (e.g. eclipticam v3w gating v1). Empty `rules` for single-camera
  hosts. See `notes/capture-unification.md`.

Per-camera per-night state and signal (see `notes/storage-layout.md`
for the full schema):
- `<night>/<camera>/brightness.csv` — every captured frame's
  brightness, written by stage 2. Outside `day|night/` mode dirs
  so stage 1 can read dusk's day-mode samples to decide the
  day→night transition (no bootstrap circularity).
- `<night>/<camera>/state.json` — stage 1's latest decision +
  inputs that drove it (mode, transitioned_at_utc, latest_brightness,
  sun_altitude, pending_process flags). Stage 2 reads its own
  camera's file; stage 3 watches the files of every camera
  assigned to it via NFS.

## Shared Python package — `astro/`

- `config` — `CameraConfig.load(name)`
- `nightdir` — canonical noon-rollover (`(utc - 12h).date()`); every
  camera uses this so a night = one directory
- `frames` — `list_night_frames(cfg, night)` across the flat / percam /
  starcam-npy layouts
- `process/bayer` — sensor → Bayer registry + `bin2x2()` (2×2 sum-bin,
  uint32 on overflow — deliverables are derived from binned grey, never
  the raw mosaic)
- `process/badpix` — MAD hot/cold pixel mask from night min/max
- `process/brightness` — per-frame `mean/(EXPTIME×GAIN)` CSV; derives
  the "darkest 10 min" anchor used for frame-quality gating; log₂
  plot of stops above pedestal (BST/GMT auto-resolved)
- `process/pole`, `process/derot` — global LSQ pole fit + streaming
  per-tile derotated stack
- `process/detect` — DAOStarFinder candidates (`cands` CLI), JSON
  sidecars under `HH/cands/<frame>.json`
- `present/render` — asinh JPEG (`ignore_zero` for derot mosaics)
- `present/privacy` — publication crop + `.privacy-ok` sidecar
- `present/summary` — `summary.json` schema-2 for the website
- `present/publish` — S3 upload
- `capture/streaming` — generic `picamera2` streaming loop (used by
  eclipticam v3w; astrocam migration pending — see TODO.md)

## Frame-quality gating

Derived per night, not configured. Pass 1 finds the median per_s
(`mean / (EXPTIME × GAIN)`) over the darkest contiguous 10-minute
window. Pass 2 stacks every frame within ±30% of that anchor —
rejects twilight/dawn *and* spuriously-dark "flapping" frames. No
per-camera threshold to tune. A hard `+10 stops above pedestal` cap
on the anchor band catches fully-cloudy nights.

Explicit windows with `--window-start HH:MM --window-end HH:MM` (UTC,
noon-rollover-aware) skip the band gate. Useful for spot-checks like
"stack v3w 23:00–23:30 UTC for the dense star-trail picture."

## Conventions

- **Venv activation required** for every utility. Either
  `source ~/astro/.venv/bin/activate` or invoke as
  `~/astro/.venv/bin/python ~/astro/bin/<tool>`.
- **`astro-` prefix on the 4 stage executables only** (`astro-state`,
  `astro-capture`, `astro-process`, `astro-storage`). They run as
  daemons / cron under systemd and benefit from a globally distinct
  name. All other utilities in `bin/` have no prefix — `~/astro/bin/`
  is scope enough.
- **Python by default** for every executable. Shell wrappers only
  for trivial systemd glue (`services/*-run.sh`).
- **Config-driven, not flag-driven.** A new camera is added by
  creating its config dir, not by adding a CLI option. Flags are
  for dev/test overrides.
- **No `/tmp/`** for working files (volatile — see GLOBAL.md). Use
  `~/tmp/<camera>-night/<night>/`.
- **Internal timestamps UTC, human-facing Europe/London.** Frame
  filenames are epoch_ms or HH-MM-SS UTC; plots resolve BST/GMT.
- **Night dir = noon-rollover.** The "night of 2026-05-21" is
  2026-05-21 12:00 → 2026-05-22 12:00 (Europe/London noon), the whole
  observing session under one date string. `astro.nightdir.night_of(utc)`
  is the only correct source.
- **Bayer per-sensor**: OV5647 = SGBRG10 (NOT SRGGB10 — recurring
  mistake), IMX708 = SRGGB10, IMX219 = see `astrocam/camera.json`.
- **Per-sensor fixed pedestal** in `camera.json` so "stops above
  pedestal" is comparable across nights and across cameras.
- **Log-scale plots: base 2, not base 10.** Use `ax.set_yscale("log", base=2)`
  so each gridline is one stop.

## Tooling

- **FITS** for everything past the raw buffer. Rice-compressed
  `.fits.fz` is ~2× smaller, natively readable by every tool.
- **astrometry.net** (`solve-field --tweak-order 3 --pixel-error 1`)
  for plate solving when needed — writes SIP polynomial distortion
  into the WCS header.
- **Splay** (`~/super/bin/splay`) — preferred visual inspector for
  FITS and image sequences. Reach for it first.
- **oiiotool** (OpenImageIO) for format conversion (FITS ↔ EXR ↔
  standard images).
- **DS9** for region-based inspection. **djv** for `.exr` sequence
  playback. **Siril** as a last resort (painful UI).

## Related repos

- **`Berrylands/gardencam/`** — historical Pi-side capture for starcam
  (`starcam_night_daemon.py`) and skycam. The capture-unification
  plan (see `notes/capture-unification.md`) gradually pulls scientific
  capture into `astro/astro/capture/`. Berrylands keeps skycam.
- **`~/photography/timelapse/starcam/`** — day-mode timelapse, pretty
  pictures. Different repo, different goals.
- **`mywebsite`** — `/astro/astrocam` and `/astro/eclipticam` pages
  read the S3 deliverables.

## Systemd units

In `services/`, deployed via ansible. **Target state:** one
service per stage per host, all `Restart=always` continuous
daemons. No timers — stages 2 and 3 react to the state record.
Stage 4 is the exception (weekly timer).

| Service | Host | Stage | Status |
|---|---|---|---|
| `astro-state.service` | each Pi + NFS host | 1 | **landed** (2026-06-16) |
| `astro-capture.service` | each camera Pi | 2 | pending — current per-camera daemons run instead |
| `astro-process.service` | wherever `processing.host` points | 3 | **landed** (2026-06-16) |
| `astro-storage.timer` + `.service` | NFS host | 4 | pending |

Both new units read `$CAMERAS` from `/etc/default/astro-<stage>`.
Example env-files in the repo at
`services/astro-<stage>.env.<hostname>`; deploy them by copying to
`/etc/default/astro-<stage>` on the target host.

**Today (transitional):** old timer-driven units coexist with the
new daemons during the migration —
`publish-astrocam.timer` + `.service`,
`publish-eclipticam.timer` + `.service` (07:00 BST),
`astrocam-capture.service`,
`eclipticam-v3w-night.service`,
`eclipticam-v3w-uploader.service`,
`to-fits-sweep.service`,
`to-fits-watch.service`.
The old `publish-*` timers are redundant once stage 3 is enabled on
each host; disable them at the same `systemctl enable` step that
brings up `astro-process.service`. Capture units retire when
`astro-capture` is ready.

## Status as of 2026-06-16

- `unify-cameras` branch ready to merge into `main`. Single codebase.
- Three live cameras: astrocam, eclipticam-v1, eclipticam-v3w.
- starcam decommissioned; cold archival in progress (see `COLD_STORAGE.md`).
- Squashed-vs-raw scientific-equivalence experiment not yet run;
  documented in `COLD_STORAGE.md` for when it matters.
- Legacy starcam-only pipeline (`bin/pipeline-night`, `bin/pipeline-hour`,
  `bin/derot-patches`, `bin/fit-pole` bootstrap loop) — **pending
  deletion** per DECISIONS.md 2026-06-16.
- **4-stage architecture (`astro-state` / `-capture` / `-process` /
  `-storage`) adopted as the target shape.** Existing
  `bin/nightly-cam` and `bin/publish-night-cam` collapse into
  `astro-process`. Existing capture daemons collapse into
  `astro-capture`. State controller and storage manager are new
  executables. See TODO.md for the migration order.
- **Stage 1 (`bin/astro-state`) landed.** Reads `brightness.csv` per
  camera; falls back to sun altitude (`ephem`); cold-start fallback
  to `default_day`. Writes per-camera state.json at the canonical
  `<root>/YYYY/MM/DD/<camera>/state.json`.
- **Brightness writer wired into eclipticam-v3w capture.** Per-frame
  rows land at canonical `<root>/YYYY/MM/DD/eclipticam-v3w/brightness.csv`.
- **eclipticam-v1/v3w split landed.** Two flat CameraConfigs
  (`eclipticam-v1/`, `eclipticam-v3w/`), no more `subcams: {...}`.
  `--subcam` flag and `cfg.subcam()` method removed from all 10 CLIs
  + `astro.config` / `astro.frames` / `astro.present.privacy`. Old
  `eclipticam/` dir kept as the home of `capture.py`, the v3w
  streaming daemon, and the v3w uploader (these still write to the
  legacy `night/<date>/v1|v3w/HH/...` path; new configs use
  `night_layout: "percam"` so the post-split camera names resolve
  legacy data correctly). Migration to canonical layout pending —
  see TODO.md.
- **Systemd units updated.** `publish-{astrocam,eclipticam}-run.sh`
  reference `$HOME/astro` (was stale `$HOME/astro-unify`). The
  eclipticam runner iterates `eclipticam-v1, eclipticam-v3w` instead
  of passing `--subcam`.
