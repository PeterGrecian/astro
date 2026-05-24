# astro — TODO

Live work list. Move items to DECISIONS.md once they crystallise
into a load-bearing choice; delete done items.

## Foundations

- [x] Decide tooling — FITS + astrometry.net + Siril + oiiotool (DECISIONS.md, 2026-05-22).
- [x] Decide repo location — sibling of photography/, not nested.
- [x] Skeleton: README, CLAUDE.md, DECISIONS.md, bin/, astro/, notes/.
- [ ] `requirements.txt` finalised once we have the first utility working.
- [ ] `notes/tooling.md` — install commands + cheat-sheet for solve-field, Siril, DS9, ASIFITSView, oiiotool, djv.
- [ ] `notes/pi4-feasibility.md` — can a £35 Pi4 do FITS + plate solve + derot? RAM/CPU budget. Estimate vs £45 model.
- [ ] `notes/disk-budget.md` — 80 GB/night raw → ~35 GB FITS → ~1 GB/night accumulators. Confirm with real numbers once `to-fits` runs.

## Utilities (bin/, no astro- prefix)

- [ ] `night-dir` — translate timestamp → noon-rollover night date. Pure stdlib, no venv needed; keep it standalone bash/python.
- [ ] `night-stats` — produce brightness CSV for a night (mean / median / p95 / max / sat% per frame). Replaces the ad-hoc `/tmp/scan_brightness.py`.
- [ ] `gc-status` — human readout of `file-garbage-collector` on puppy: free space, target, what would be next to go.
- [ ] `to-fits` — `.npy` → `.fits.fz` with proper header (epoch_ms, exposure, gain, sensor, Bayer pattern). Bottleneck: unlocks all downstream tools.
- [ ] `platesolve` — wraps `solve-field` with our defaults; writes SIP into header.
- [ ] `derotate` — WCS-aware stack: read each frame's WCS, rotate to a common reference, sum.

## Pipeline

- [ ] Duff-pixel mask (per-camera, per-gain) — median of ≥100 dark frames. Store in repo? Or as a FITS sidecar per camera?
- [ ] Dark master per (gain, exposure) — capture procedure documented; subtraction step in `to-fits` or a separate `subtract-dark`?
- [ ] Cloud / sky-quality flag per frame — `notes/sky-quality.md`. Std-dev signal, mean/median ratio, centre-vs-edge.
- [ ] Coordination with `Berrylands/gardencam/starcam-daemon` — confirm input contract (filename, Bayer pattern, mtime semantics). Document in CLAUDE.md.
- [ ] Compress retention plan — keep raws for N days, FITS for M, accumulators forever.

## Aspirational (cameras)

- [ ] Decide camera identifier convention (`back`, `front`, `sky`, `experimental`). Reflect in path layout: `~/<cam>-frames/night/<night-dir>/HH/`.
- [ ] Per-camera config: gain, exposure, lens, sensor, Bayer pattern.

## Multi-night stacking (deferred — let the per-night pipeline mature first)

- [ ] `derot-week` — extension of `derot-night` that walks multiple
      night dirs, derotates by `omega × (epoch_ms - epoch_0) / 3000`
      so frames from different nights stack onto a common rotated
      reference. Stars near the pole stack perfectly; stars away
      from the pole accumulate only when above the horizon.
- [ ] **Lens distortion dominates atmospheric refraction** — when
      we start pulling refraction signal out of multi-night stacks
      it'll be a big deal, but first the per-frame distortion model
      (k1, k2 from `fit-geometry`) needs to be solidly fitting. The
      residual after a good distortion fit will be where we look
      for refraction effects.
- [ ] **Camera position drifts sometimes, possibly with
      temperature.** Within one night the pole moves <30 binned px
      (see pipeline-poles.csv across hours). Between nights it can
      jump (we've seen ~50 px shifts after physical repositioning).
      Multi-night stacks need a per-night pole, not a global one.
      A `fit-pole-multinight` would estimate per-night pole + a
      single shared distortion (k1, k2 are sensor properties).

## Disposable scratch

- Old per-`/tmp/` scripts (streak_window.py, streak_clean.py, streak_lum.py, run_streaks.sh) — port the useful patterns into `bin/` if needed, don't ressurrect the originals. They were /tmp violations; lesson logged.
