# Astro pipeline — canonical per-night process

Written 2026-05-25. Goal: a complete, reproducible chain from
raw `.fits.fz` (delivered to puppy by `starcam_night_daemon`) to
final per-night and per-hour derotated stacks with stars resolved.

The intent is that tomorrow's run is just:
```bash
pipeline-night /home/peter/starcam-frames/night/<YYYY-MM-DD>
```
…and everything below happens unattended.

---

## Inputs

- **Raw frames**: `<night>/<HH>/<epoch_ms>.fits.fz`
  (2592×1944 uint16 Bayer SGBRG, 2.9 s exposure, gain 16,
  one per ~3 s by `starcam_night_daemon` on starcam Pi).
- **Sky mask** (manual, dated): `~/astro/calib/sky-mask-starcam-<YYYY-MM-DD>.fits.fz`
  (972×1296 uint8 bitmap, 1 = exclude). Cover tree, house, edge
  light leaks. Re-paint when the camera moves.

## Outputs

For each night, under the same `<night>` dir:

```
<night>/
├── <HH>b/                            # binned data
│   ├── 0001.fits.fz … NNNN.fits.fz   # 2x2 sum-binned, renumbered
│   ├── brightness.csv                # per-frame stats
│   ├── sum.fits.fz                   # int32 pixel-sum
│   ├── candidates.csv                # per-cell argmax per frame
│   ├── patches-iter{1..N}/           # bootstrap iteration debug
│   └── final/
│       ├── derot.fits.fz             # converged per-hour derotated stack
│       └── mosaic.jpg                # top-N candidate patches, derot|raw
├── hot-pixels-<YYYY-MM-DD>.fits.fz   # PER-NIGHT hot mask (was per-hour; wrong)
├── pipeline-poles.csv                # per-hour pole estimate + status
├── pipeline.log                      # full run log
└── all-night-derot.{fits.fz,jpg}     # PROPERLY all-frames derotated stack
```

The two terminal deliverables are `all-night-derot.fits.fz`
(everything from the night collapsed to one image at the median
pole) and the per-hour `final/derot.fits.fz` (cleaner sharpness
per hour, lets you compare hours).

---

## Process

### Stage A — per-hour preparation (parallelisable across hours)

For each `HH/` dir whose mean brightness (via `brightness.csv`) is
below the sky-threshold (default 100 ADU; rejects twilight/dawn):

1. **`bin-frames <HH> <HH>b`**
   - 2×2 sum-bin uint16 → uint16 (clipped at 65535).
   - Renumber 0001..NNNN; carry DATE-OBS, EPOCH_MS, SRCFILE in headers.
   - Idempotent: skip if `<HH>b/0001.fits.fz` exists and frame counts match.

2. **`scan-brightness <HH>b`**
   - Per-frame mean/median/p95/max/bright-pixel-count CSV.
   - Falls back to EPOCH_MS header when filename isn't an epoch.

3. **`sum-frames <HH>b`** → `<HH>b/sum.fits.fz` (int32 accumulator).

### Stage B — per-night sensor calibration

After all hours are summed:

4. **Per-night hot-pixel mask** — sum every `<HH>b/sum.fits.fz` for
   the night into one super-sum, then threshold by percentile via
   `hot-pixel-mask --sweep`. Write to
   `<night>/hot-pixels-<YYYY-MM-DD>.fits.fz`.
   *Why per-night not per-hour:* hot pixels are a sensor property;
   averaging across a whole night smooths transient brightness
   variation across hours. Camera position drift means we don't
   trust a single mask across many nights.

5. **Pick sky mask**:
   `~/astro/calib/sky-mask-starcam-<YYYY-MM-DD>.fits.fz` (the most
   recent dated mask on or before `<night>`). Both masks combined
   (logical OR) form the **keep** bitmap used by every later step.

### Stage C — candidate stars + pole + plate fit per hour

For each viable hour:

6. **`find-candidates <HH>b --mask <combined>`**
   - Per-cell (default 100×100 raw grid) argmax per frame.
   - Skips pixels in the combined mask.
   - CSV ordered by cumulative peak-value-per-cell.

7. **Bootstrap loop** (max 10 iters, stop when pole moves <1 binned px):
   - Iter 1..2: `fit-pole` — 3D Nelder-Mead on (pole_x, pole_y, omega).
     Fast (100 frames, top-10 cells).
   - Iter 3+: `fit-geometry` — 5D add (k1, k2) radial distortion.
     Longer baseline (300 frames) for distortion to be visible.
   - After each fit: `derot-patches` with new geometry → re-runs
     `find-candidates` on the derot stack to harvest more (now
     point-like) candidates for the next iteration's fit.

8. **`derot-patches --frames <all>`** with converged geometry →
   `<HH>b/final/derot.fits.fz`. The per-hour science output.

### Stage D — per-night final

9. **`derot-night`** with median pole from `pipeline-poles.csv` —
   walks every binned frame in the night in time order
   (sort by EPOCH_MS), computes `angle = omega × (epoch_ms - epoch0) / 3000`,
   derotates, sums into one accumulator. Writes
   `<night>/all-night-derot.fits.fz` + `.jpg`.

   *Difference from per-hour:* per-hour stacks each derotate to their
   own frame-0; summing them naively re-introduces inter-hour
   rotation. derot-night handles the cumulative angle correctly.

---

## Sky-threshold gating

`pipeline-night` reads each HH's `brightness.csv` mean *before*
processing. Hours with mean > sky-threshold (default 100 ADU) are
skipped — too bright for stars to dominate the signal. Typically
this drops the twilight hour (19 or 20) and the dawn hour (03).

Status in `pipeline-poles.csv` will be `skipped-bright` for these.

## Order: darkest hour first

The darkest hour's data gives the cleanest pole fit (least sky
glow, least noise). Process it first; carry its converged pole as
the seed for the next-darkest hour, etc. Brighter hours get the
benefit of an already-good pole, so their fit converges in fewer
iterations.

## Camera drift handling

The pole can move ~50 binned px between nights (we've seen this
across repositioning). Within a night it's stable to ~30 px. So:

- Per-hour `fit-pole`/`fit-geometry` each refine locally.
- `derot-night` uses the **median** of the hour-poles as the
  per-night pole. This averages out within-night drift.
- Multi-night stacking would need per-night poles + shared
  distortion (see TODO.md).

## What's currently broken / to fix tomorrow

- **Per-night hot-pixel mask** isn't implemented — current code
  derives a fresh mask per hour from that hour's sum. Need to
  sum-of-sums first, then mask once.
- **Sky mask wiring** — `--sky-mask` not yet plumbed into any tool.
  Apply at load time across `sum-frames`, `find-candidates`,
  `fit-pole`, `fit-geometry`, `derot-patches`, `derot-night`.
- **derot-night not in pipeline-night** — currently a separate
  manual run; should be the last step of the night pipeline.
- **Sky-mask + hot-mask combination** — needs a tiny helper that
  loads both, ORs them, returns the keep bitmap. Avoid every tool
  doing this independently.

## Outputs for human inspection

- `<HH>b/final/mosaic.jpg` — 4×5 grid of derot|raw patches; tells
  you visually which candidates are real.
- `<night>/all-night-derot.jpg` — the night in one image.
- `<night>/pipeline-poles.csv` — pole consistency across hours
  (sanity-check: should all be within ~50 px of each other).
- `<night>/pipeline.log` — full audit trail.
