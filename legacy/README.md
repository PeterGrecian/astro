# legacy/ — scripts from the 2026-05-20 night-mode session

Recovered from `puppy:~/tmp/starcam-night/2026-05-20-21/*.py` on
2026-05-22. These are the working scripts from the breakthrough
session that produced `photon_dark50.jpg`, `arc_walk3.jpg`, the
geometric pole estimate at (1919, -218), and the rotation-compensated
stack experiments.

**Status: reference, not maintained.** All scripts:

- Operate on `.npy` raw Bayer frames (need updating for the FITS
  pipeline that landed 2026-05-22).
- Use the old `raw/` path layout under `~/starcam-frames/night/`
  (gone; data is now at `~/starcam-frames/night/<night>/HH/`).
- Hard-code dates and paths from the original session.
- Are /tmp-era scratch quality — small, focused, but no docs/tests.

Use them as **algorithmic reference** when porting to the new pipeline:

| Group | Files | What they do |
|---|---|---|
| Stats | `stats.py`, `scan_brightness.py`, `plot_brightness.py`, `outliers.py`, `render_outliers.py` | Per-frame brightness CSV + outlier detection |
| Photon sum | `photon_sum.py`, `photon_darkest.py`, `photon_chunks.py` | Accumulate the darkest-N% of frames |
| Streaks | `streak_*.py` | Abs-diff accumulators (various reject variants) |
| Arcs | `arc_detect*.py`, `arc_walk*.py` | Connected-components + PCA elongation + perpendicular bisector → pole |
| Hot | `hot_from_walk.py`, `hot_mask.py` | Classify components by size+elongation → hot-pixel mask |
| Dark | `median_dark.py` | Per-pixel median across N dark frames → master dark |
| Derot | `derot_stack.py`, `derot_search*.py`, `render_derot.py` | Warp + sum around the pole; grid-search (pole_x, pole_y, ω) |
| Misc | `diff_render.py`, `render_latest.py` | Quick-look renderers |

## Canonical pipeline order

1. `scan_brightness.py` → per-frame stats CSV (mean, median, p95, max, sat%)
2. `photon_darkest.py` → photon-sum of the darkest 50% across a UTC window
3. `arc_walk3.py` → connected-components arc detection on the photon sum
   (uses GIMP-style DoG + threshold; PCA elongation; perpendicular
   bisector consensus for pole position with iterative outlier rejection)
4. `hot_from_walk.py` → extract hot pixels (short, non-elongated
   components from arc_walk) → boolean mask
5. `median_dark.py` → master dark from N darkest frames (per-pixel median)
6. `derot_stack.py` → warp each frame around the pole, sum → "points
   not arcs" (in theory; in practice still smears because of lens
   distortion not yet fitted)
7. `derot_search3.py` → grid-search (pole_x, pole_y, ω) by sharpness
   of the derotated stack

## Key results from 2026-05-20 session

- Pole at approximately (1919, -218) — off the upper-right corner.
- ~2800 hot pixels identified from arc-walk components.
- Photon-sum of darkest 50% (22:30–03:00 UTC, 10,789 frames) showed
  50+ visible star arcs (`photon_dark50.jpg`).
- Single-frame solve-field plate-solving has not been attempted yet
  (deferred to 2026-05-22 session); see source-count diagnostic.

## When to update

When the FITS-driven re-port reproduces these results cleanly with
the new path layout, delete this directory. Until then, it's the
authoritative reference for the algorithms that worked.
