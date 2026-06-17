# Sim-based pipeline development

Status: **parked 2026-05-24**. Tooling works, algorithm needs more
thought.

## Why a simulator

The real pipeline (raw .npy → .fits.fz → derotated stack → arcs)
involves several stages where each step's correctness depends on the
previous. Debugging end-to-end on 100 GB nights with no ground truth
was getting nowhere. The sim gives:

- Known pivot, rate, star positions, distortion (FITS headers carry truth).
- 100x100 frames so visual inspection in a jpg is trivial.
- 10 frames per "night" → seconds per full re-run.

All sim artefacts live in `~/astro/sim/` (gitignored).

## What's built

| Tool | Purpose |
|---|---|
| `bin/sim-frames` | Generate N noise-free / noisy / distorted frames with K stars rotating about a pivot. Writes FITS with truth in headers + `truth.txt` manifest. |
| `bin/derot-sim` | Stack frames raw and/or derotated using the **header's** pivot+angle. Produces `stack-raw.fits.fz` and `stack-derot.fits.fz`. |
| `bin/fits-to-jpg` | Per-frame auto-stretch upscaled jpgs for eyeballing. Siril was overkill for 100x100. |
| `bin/find-pivot-coarse` | Threshold raw stack → connected components → fit circles to arc-shaped blobs → average centres → pivot estimate. **Doesn't work well yet** (see below). |

Typical end-to-end:
```bash
sim-frames --stars 2 --noise 20 --hot 5 --pincushion 0.05
derot-sim                # uses truth pivot from header
fits-to-jpg              # eyeball the stacks
find-pivot-coarse        # try to RECOVER the pivot blind
```

## Demonstrated

1. **Derotation geometry is correct.** With truth pivot+angle from
   the header, derotated stacks collapse a single-pixel star into a
   single bright pixel at 10× single-frame brightness. The opencv
   rotation direction is the opposite of math convention because
   image y is down — `derot-sim` documents the sign flip.
2. **Stacking discrimination works as expected.**
   - Raw stack: stars trace arcs (1× per pixel), hot pixels stack to
     10×, random noise stays 1×.
   - Derot stack: stars collapse to 10× points, hot pixels trace
     short arcs at 1× per pixel, noise stays 1×.
   - The two stacks are duals: each tells you what the other can't.
3. **JPG visualisation closes the feedback loop.** Auto-contrast
   per-frame plus 4× upscale makes the difference between a
   converging derotation and a smeared one immediately obvious.

## What didn't work (and why)

### Coarse arc-finder (`find-pivot-coarse`)

The intent: find a few bright arcs in the raw stack and fit a circle
to each — their shared centre is the pivot, seeding a later
sharpness optimiser.

The problem with the current sim:

- **Star arc pixels and noise pixels have identical brightness** in
  the raw stack. The star visits each pixel along its arc *once* per
  10-frame sequence — so a single arc pixel sums to 1 × brightness,
  the same as a noise hit. The only thing distinguishing arc from
  noise is structure, not intensity. Morphological closing
  (`MORPH_CLOSE`) helps merge arc pixels into a connected blob but
  noise dots remain isolated.
- **Algebraic (Kasa) circle fits are unstable on short arcs.** With
  only 20° of rotation and arc radii of 30–40 px, each arc covers
  ~10 pixels of a very small chord — ill-conditioned for solving
  (cx, cy, r) independently. The fits land on plausible-looking but
  wildly wrong centres (off by tens of pixels).
- **Joint fit would help.** All arcs in one frame share (cx, cy);
  fitting 2 + N parameters instead of 3N is far better conditioned.
  Not yet tried.

So `find-pivot-coarse` currently returns garbage for the sim case it
was designed for.

## Why parked

Two unresolved issues:

1. **The discrimination problem is harder than the sim shows.** In
   real data:
   - Individual star arcs in the raw stack are *sub-threshold* —
     stars are dim enough that no single arc-pixel stands out from
     sky background. The signal only emerges after spatial
     aggregation.
   - This means thresholding + connected-components is the wrong
     approach for real data. The sim accidentally papered over this
     by making stars bright enough to threshold.
   - Right approach is probably matched filtering / Hough-style
     voting on a continuum of brightnesses, not a hard threshold.

2. **Distortion vs pivot recovery interact.** With the V1 lens's
   barrel distortion (SIP polynomial from `solve-field`), arcs in
   pixel coords aren't circular — they're warped. Recovering a pivot
   *before* undistorting is geometrically wrong. The proper order is:
   plate-solve → undistort → derotate. So pivot recovery from raw
   pixel coords may be the wrong problem entirely; instead use
   `solve-field`'s WCS per frame and derotate to a common frame.

   That said, we can't plate-solve 100×100 sim frames or short-
   exposure dim night frames — solve-field needs detectable stars.
   So there's a real-data regime (faint nights) where pivot recovery
   from pixel coords is the only option.

## To resume

Open questions to decide first:

1. **Should the sim model real-data brightness more accurately?**
   E.g. each arc pixel = sky_background + ~5 ADU star signal, vs the
   current 1000-ADU arc pixels. Forces algorithms to confront the
   real SNR.
2. **Should we add the WCS / SIP undistort step to the sim?** I.e.
   simulate "perfect plate solve gives us a WCS, undistort first,
   then derotate." If the plate-solve route works on most nights,
   the pivot-from-arcs route is only needed for the worst nights.
3. **Joint circle fit + non-linear refinement.** Try the joint
   (cx, cy) + per-arc radius fit before declaring `find-pivot-coarse`
   dead.
4. **Sharpness optimiser as the next stage.** Even if the coarse
   finder is wrong, a good optimiser should refine it. Or it might
   not — the basin of attraction is the open question.

## Files

- `bin/sim-frames`
- `bin/derot-sim`
- `bin/fits-to-jpg`
- `bin/find-pivot-coarse`
- `sim/` (gitignored — generated frames, stacks, jpgs, truth.txt)
