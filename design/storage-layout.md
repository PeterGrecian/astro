# Storage layout — canonical tree

Drafted 2026-06-16 alongside the 4-stage architecture decision.
This doc captures the *target* layout. Migration from today's
`~/<camera>-frames/{day,night}/<date>/...` happens once per night,
per camera, via rsync.

## Canonical tree

```
~/astro-frames/                       # frames root (NFS-mounted everywhere)
└── 2026/06/15/                       # noon-rollover date, split YYYY/MM/DD
    ├── astrocam/
    │   ├── brightness.csv            # per-frame brightness, all of this night
    │   ├── state.json                # snapshot at noon-rollover (closing state)
    │   ├── night/
    │   │   └── HH/                   # UTC hour, 00..23
    │   │       └── HH-MM-SS.fits.fz  # UTC timestamp in filename
    │   └── day/
    │       └── HH/
    │           └── HH-MM-SS.fits.fz
    ├── eclipticam-v1/...
    └── eclipticam-v3w/...
```

## Why date-first, not mode-first or camera-first

- One night = one dir, across all cameras. Cross-camera comparison
  is `ls 2026/06/15/`, not a parallel walk of N camera trees.
- Aggregation works at every level: a year of data is `2026/`, a
  month is `2026/06/`. Bounded fanout per level (≤366 dirs at top,
  ≤12 per year, ≤31 per month) — friendlier to `ls`, `find`,
  `du`, S3 list operations, and cloud-archive layout.
- Mode (`day|night`) is a per-frame property, so it lives inside
  the camera dir as a sibling. `brightness.csv` and `state.json`
  sit *outside* the mode dirs — they're per-camera-per-night
  artefacts, not per-mode.

## Path conventions

| Level | Format | Notes |
|---|---|---|
| Date | `YYYY/MM/DD/` | Noon-rollover; `night_of(utc) = (utc - 12h).date()`. CLI / logs / state.json keep the flat `YYYY-MM-DD` string form — translation to path happens only at filesystem boundaries. |
| Camera | `<camera>/` | Top-level camera name; `eclipticam-v1` and `eclipticam-v3w` are siblings (no `subcams` nesting). |
| Mode | `day/` or `night/` | Set by the capture daemon based on stage 1's mode at the moment the frame is taken. A given hour dir is single-mode (mode only changes at dusk/dawn transitions, between hours in practice). |
| Hour | `HH/` | UTC hour, two-digit. We keep the hourly chop because flat per-night dirs hit 10⁴+ files. |
| Frame | `HH-MM-SS.fits.fz` | UTC. Matches eclipticam's existing convention. Sortable within an hour. Round-trippable with FITS `DATE-OBS`. |

The 23→00 wraparound inside a night is handled by a sort helper
in `astro.frames` (`sort_hours_for_night(hours)` returns the list
ordered by `(hour - 12) % 24`). The path on disk stays standard UTC
so every external tool (astropy, datetime, FITS headers) round-trips
without surprise. We considered extending past 23 (24:00 / Japanese-
style) — rejected because path/header disagreement is a much worse
trap than a five-line sort key.

## brightness.csv — schema

Path: `<night>/<camera>/brightness.csv`.

Owner: the capture daemon (stage 2). Append-only. One row per
captured frame. Cheap (`mean / (EXPTIME × GAIN)` is already computed
in `astro.process.brightness`).

```
utc_iso, epoch_ms, mode, exptime_s, gain, mean, per_s, stops_above_pedestal
2026-06-15T19:42:17Z, 1718480537000, day, 0.001, 1.0, 14112.3, 14.1e6, 11.2
```

Why outside the `day|night/` mode tree: capture writes here
*before* the mode is reconsidered. If brightness.csv lived under
`night/`, the state daemon couldn't read dusk's day-mode samples
to decide the day→night transition. The CSV being mode-agnostic
breaks the bootstrap circularity.

One file per camera (not per host). Eclipticam-v1 and v3w each have
their own brightness.csv. The state daemon reads both when deciding
the host's overall mode.

## state.json — per camera, per night

Path: `<night>/<camera>/state.json`.

Owner: stage 1 (`astro-state`) on the camera's host. Written on
every mode transition and at noon-rollover (closing state). Snapshot
of the latest decision plus the inputs that drove it.

```jsonc
{
  "camera": "astrocam",
  "host": "astrocam",
  "night": "2026-06-15",
  "mode": "night",
  "transitioned_at_utc": "2026-06-15T20:14:03Z",
  "previous_mode": "dusk",
  "latest_brightness": {
    "stops_above_pedestal": 4.2,
    "per_s": 38000,
    "ts_utc": "2026-06-15T20:14:01Z"
  },
  "sun_altitude_deg": -8.7,
  "pending_process": {
    "dusk_window_complete": false,
    "dawn_window_complete": false
  }
}
```

Stage 2 (`astro-capture`) reads its own camera's state.json to pick
the active mode's exposure/cadence/format from `camera.json`. Stage 3
(`astro-process`) watches state.json across all cameras assigned to
it; when `pending_process.dawn_window_complete` flips true, it runs
the deliverables pipeline for the just-finished window.

There is no global `state.json` — every artefact is per-camera-per-night.
A host-level summary (if needed for monitoring) is derived, not
authoritative.

## Where stage 3 runs — follows storage locality, not CPU

**Stage 3 runs where the frames physically live.** The earlier framing
("the Pis have enough CPU, so let them self-process") was wrong: CPU was
never the bottleneck — **I/O locality** is. Today the camera Pis write
their frames to puppy's NFS export. A Pi running its own stage 3 reads
every frame *back across NFS* from puppy, on a weak CPU, and writes the
deliverables back over NFS — the worst of both worlds.

Measured 2026-06-20 (astrocam backfill, 1674 frames/night): the Pi 4
managed ~30 frames/min over NFS; **puppy did ~400/min reading the same
data locally — ~13× faster.** So:

- **All cameras set `processing.host: "puppy"`** while the Pis write to
  puppy's NFS. The Pis keep stage 1 (`astro-state`, which must run where
  capture is — it reads brightness.csv and writes state.json) + capture.
- **`processing.host: "self"` only becomes correct when a Pi has its own
  local storage** for its frames. Then "self" means processing *local*
  data — the whole point of host independence. Until then, self is a
  trap.

In `camera.json`:

```jsonc
"processing": {
  "host": "puppy",           // run stage 3 where the frames live
                              // "self" only once the Pi stores locally
  "fallback_host": "muppet"  // optional; if the primary lags / is down
}
```

`astro-process` daemons run on every host that's a processing target
(its own + any cameras pointing at it). Each daemon watches the
state.json of every assigned camera over NFS; transitions trigger work
*locally to that host*. Switching hosts is a one-line config change plus
enabling the systemd unit on the target host (and disabling it on the
old one).

### 2026-06-25: eclipticam processing+storage MOVING puppy -> the Pi

The eclipticam Pi (Pi 5, 4 cores, **991 MiB RAM**) now has a **110 GB
local SSD** (`/mnt/ssd`, `eclipticam-frames` dir created). That meets the
"Pi has its own local storage" condition above, so processing moves to
the Pi — the storage-locality principle now points *to* the Pi (frames
local, no NFS round-trip). In progress, not complete: SSD provisioned,
but `~/eclipticam-frames` still the old path and Pi `astro-process` still
disabled. **Must not affect acquisition** (separate stage).

Why the CPU worry evaporates (Peter): this is real-time processing with a
**one-day interval**. The camera captures at night; the ~10-12 h of
DAYLIGHT is a huge idle window to process the one night's frames. Capture
and processing run at *different times* -> little contention, so
acquisition-safety is largely automatic (don't process during the capture
window). The 991 MB RAM ceiling still bounds per-job memory, but with all
day for one night's work, process serially / memory-bounded, no time
pressure.

The real constraint is STORAGE BUDGET — a tiered plan:

| Tier | Where | Purpose | Retention |
|---|---|---|---|
| Hot | Pi SSD (110 GB) | recent nights + **long-baseline keeps** | days..months |
| Warm | S3 standard | deliverables + raw, long-term | ongoing |
| Cold | S3 Glacier / Deep Archive | archival (raw Bayer "most options") | indefinite |

Budget math: full-res ~11 GB/night -> 110 GB SSD ≈ **10 nights** before
full. So the cadence MUST be reliable: capture -> process -> ship
deliverables+raw to S3 -> free local (EXCEPT long-baseline keeps, which
stay hot for cross-night/extreme-long-baseline re-stacking, e.g. the moon
net). If shipping lags, the SSD fills in ~10 days. This is what STAGE 4
(`astro-storage`, still unbuilt) must do for eclipticam: ship+free with a
keep-policy, and an S3->Glacier lifecycle for the cold tier. Follows the
COLD_STORAGE.md pattern (Hot/Warm/Cold -> Deep Archive) already used for
starcam.

Open: (a) long-baseline keep policy (how many nights/months stay hot);
(b) ship+free trigger (build astro-storage); (c) S3->Glacier transition
age; (d) OOMScoreAdjust on Pi processing so the OOM killer never kills
capture (belt-and-braces even if they rarely overlap in time).

## S3 layout (deliverables tier)

Mirrors the canonical tree:

```
s3://astro-berrylands-eu-west-1/
└── <camera>/
    └── nights/
        └── 2026/06/15/
            ├── summary.json
            ├── stacked.jpg
            ├── brightness.png
            ├── sweep.mp4
            └── ...
```

Cold-archive tier already uses `cold/<camera>/<mode>/<night>/...`
(see COLD_STORAGE.md); keep the slash-date convention there too:
`cold/<camera>/<mode>/2026/06/15/`.

## Migration

One-off, per night, per camera. For each existing night under
`~/<camera>-frames/{day,night}/<date>/<subcam?>/HH/...`:

1. Compute the new path: `~/astro-frames/<YYYY>/<MM>/<DD>/<camera>/<mode>/HH/`.
2. rsync the hour dirs into place.
3. Derive `brightness.csv` from frame headers (if not already
   present in legacy data) — one-time backfill.
4. Re-emit deliverables to the new S3 prefix from the moved tree.

Eclipticam's existing data uses `<night>/<subcam>/HH/...` — the
subcam becomes the camera (`eclipticam-v3w`) at the new layout's
camera level. Starcam's data stays in cold archive at the old
layout; reprocessing it (if ever needed) reads via the
backwards-compat reader in `astro.frames`.

## Failure modes

- **brightness.csv unbounded?** No — one file per camera per night,
  rolls naturally at noon-rollover. Max rows ≈ frames-per-night ≈
  10⁴ for a 3-second cadence camera.
- **NFS down on the processing host?** stage 3 logs warning, no-ops;
  stage 2 keeps capturing to local buffer (no NFS dependency on the
  capture path beyond eventual upload).
- **stage 1 starts cold, no brightness yet?** Falls back to
  sun-altitude only until the first brightness row appears. Logged
  as `degraded_mode: "sun_only"` in state.json.
- **Two writers on the same brightness.csv?** Doesn't happen — one
  camera = one file = one capture daemon. Eclipticam's two cameras
  have two separate CSVs.
- **Stale state.json from a crashed `astro-state`?** Add
  `written_at_utc` to state.json; stage 2/3 ignore state older than
  N minutes and fall back to capture-default / no-op respectively.
