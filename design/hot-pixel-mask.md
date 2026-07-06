# Hot-pixel masking — master + per-night (apply early)

**Status: master mask built 2026-07-06; early-application wiring pending.**
Prompted by repeatedly measuring hot pixels as "stars" until the mask was applied,
and Peter's question "are the daily masks consistent?" (they are — see below).

## The problem

The astrocam (IMX219) field is hot-pixel-dense (~2900 hot px, 0.14%). An
unmasked PSF/detection measurement is dominated by hot pixels (a hot px reads as
a 1-px "star" with dead neighbours — the source of every bad PSF measurement on
2026-07-06). The per-night `badpixel.fits` fixes this — but it is generated
POST-HOC by `nightly-cam` from the night's own min/max stack, so it does **not
exist at capture or at the start of processing**. Hence it kept being forgotten.

## Masks ARE consistent night-to-night (measured)

20 nightly masks (2026-06-09..07-05): ~2500–3000 flagged each (0.12–0.15%),
**night-to-night Jaccard 0.86–0.97**. **2482 px flagged in ALL nights** (stable
core), 3040 in ANY, 2868 in ≥50%. So ~82% is a stable sensor-defect core; only
~550 px are a transient fringe (borderline pixels flickering with nightly noise).
→ A stable master mask is valid *before* any given night's data exists.

## Two-tier design

### Master mask — `astrocam/hot-master.fits` (committed artifact)
- The **2879 pixels hot in ≥50% of nights**, aggregated from all nightly masks
  (`compute_bad_pixel_mask` outputs). Encoding: 0=good, 1=hot, 2=cold. Header:
  MASKTYPE=master, NNIGHTS, THRESH=0.5.
- **Binned resolution (1232×1640)** — upsample ×2 (`np.repeat`) to raw
  (2464×3280) when applying to raw mosaic frames.
- **Committed to the repo** → available to every tool and at capture time.
- **Regenerate occasionally** (monthly-ish; hot pixels grow slowly with sensor
  age) by re-aggregating the accumulated nightly masks. NOT nightly.
- **Apply EARLY**: the first step of any PSF/detection/streak work should load
  and apply it. Non-destructive (don't overwrite raw FITS) — apply in-memory.
  (Baking into capture is possible but loses raw hot-px values + rewrites frames;
  prefer the committed-artifact + step-0 approach.)

### Per-night mask — `<night>/badpixel.fits` (existing, refinement)
- Stays as-is: `nightly-cam` computes it from the night's min/max. Adds the ~550
  transient pixels the master misses on that night. Use downstream where
  photometry-grade cleanliness matters.

## Why two tiers
Master = the fixed sensor defect map (stable, early-available, catches 82%).
Per-night = the noise-dependent fringe (post-hoc, precise). This mirrors the
storage-schema "sensor map accumulates" idea — the hot mask is the binary version
of the accumulating per-pixel sensor map.

## Actions
1. **DONE**: build `astrocam/hot-master.fits` (2879 px, 20 nights, ≥50%).
2. Add a shared loader (`astro.process.badpix.load_master(camera)`) that returns
   the raw-resolution master mask; call it at step 0 in detect/PSF/streak tools.
3. (Optional) apply the master at capture for on-Pi starfind cleanliness.
4. Regenerate the master monthly as nights accumulate; consider a v3w master too.

## Lesson
ALWAYS apply the mask before PSF/detection/streak measurement. Without it,
astrocam measurements are hot-pixel garbage (relearned repeatedly 2026-07-06).
