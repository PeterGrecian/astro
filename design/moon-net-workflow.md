# Moon-net marking workflow

Building the per-camera **moon-net** — the accumulated set of hand-marked
moon curves (one *thread* per clear night) that pins each eclipticam's
pointing / plate-scale / distortion (see `project-astro-orientation-lock`).

Two cameras, each with its own `moon-net.json`:
`eclipticam-v1` (OV5647, day, full-res **2592×1944**) and
`eclipticam-v3w` (IMX708, day full-res **4608×2592**).

## The loop (every `p` counts)

For one camera + night:

1. **Splay the night, mark the moon.** Open the day frames and press `p`
   on the moon in each frame:

   ```
   splay ~/eclipticam-frames/day/<night>/<subcam>/     # subcam = v1 | v3w
   ```

   Press `1` first (zoom **1x** = native full-res) before marking. The
   p-probe now **always records native full-res coords** regardless of
   zoom (it rescales the draft-downscaled fit/2x surface up to native and
   tags the line `RES=WxH`), so fit-mode probes are no longer silently
   half-scale — but marking in 1x is still the most accurate.
   Each `p` appends to `~/.splay-probes.log`.

2. **Ingest probes → thread.** `mark-moon-net` reads the probe log,
   matches this camera+night's frames, derives UTC (EXIF for day),
   computes moon az/alt, rescales any old non-full-res probe, and writes
   the thread — deduped, idempotent, **every probe accounted for**
   (accepted / duplicate / skipped-with-reason):

   ```
   mark-moon-net --camera eclipticam-v3w --night <night> --mode day \
       --dec <moon_dec_deg> --phase <illum_pct> --dry-run   # preview
   mark-moon-net --camera eclipticam-v3w --night <night> --mode day \
       --dec <moon_dec_deg> --phase <illum_pct>             # write
   ```

3. **Auto-extend.** With ≥3 hand-marks seeding the fit, `moon-track`
   fills the rest of the arc automatically (box-around-prediction,
   saturation-tolerant centroid) and appends `source=auto` points:

   ```
   moon-track --camera eclipticam-v3w --night <night> --mode day --append
   ```

`mark-moon-net` and `moon-track` are both **camera-agnostic** — the
subcam (`v1`/`v3w`) is derived from `--camera`, and coords land in that
camera's own full-res space (its `capture_full_res` in `moon-net.json`).

## Why the net needs spread

A single moon arc is degenerate for pointing; the net breaks it with
arcs at **different declinations**. Pick nights spread in moon dec (the
moon sweeps ±27° over ~2 weeks) *and* with the moon above the horizon in
daylight. Compute dec/phase/alt per candidate night with a short ephem
script (see the session that built this) before choosing.

## Consumers

- `moon-overlay` — draws the net on a target frame, auto-scaling
  `capture_full_res` → the target's resolution.
- Future `wcs-from-moon-net` — the multi-anchor LSQ WCS fit (the "new
  bit" in `project-astro-orientation-lock`) over all net points.
