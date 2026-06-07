# TODO — catalog matching (parked 2026-06-07)

## Current state

Confirmed orientation from observations on 2026-05-30 starcam at Surbiton:

- Zenith is at the **BOTTOM** of the image (cut off by eaves).
- Pole (Polaris) is at the **TOP-RIGHT** of the image.
- East is on the **LEFT**, west on the **RIGHT** (confirmed by direction
  of stellar drift at bottom-left).
- Camera points roughly NW (Big Dipper area), tilted east of N by ~20°.

## What worked

- **A5's brightest detection (5.1M flux) was misidentified as Capella**;
  Capella isn't visible at all (alt 7.5° below local horizon).
- Working hypothesis is now **A5 #1 = Alioth (ε UMa, V=1.76)** in the
  Big Dipper handle area. By pole-distance match, this is the best fit
  among V<2 northern stars at the right radius.
- True NCP pixel measured at **~(714, 344)** — about 210 px from A5's
  local effective pole (889.95, 175.23). The 210 px offset is lens
  barrel distortion at the corner.
- Camera-rotation angle θ_rot ~−157° (rough; not consistent across
  the field — see issue below).
- Plate scale ~156.6 arcsec/binned px at A5 radius from pole.

## What didn't work / open issues

- **The polar-projection sky chart did not visually match the camera frame.**
  We could not see Cassiopeia, Big Dipper, or Little Dipper patterns
  emerging from the comparison.
- The fitted rotation θ_rot varies by ~14° between Kochab and Alioth
  anchors. That's lens distortion in the azimuthal direction, not just
  radial. A simple polar projection with constant rotation is therefore
  the wrong model.
- The angle between (Polaris→Kochab) and (Polaris→Alioth) in our image
  is 19.3°, but on the sky it's 28.5°. The lens compresses angular
  separations at large radii — radial barrel distortion, as suspected.

## Path forward (when picked up)

The two simplest avenues are:

1. **More than two anchor stars per fit.** With Polaris + 3-4 confirmed
   Big Dipper stars, fit (pole_x, pole_y, plate_scale, rotation, k1, k2)
   all together rather than reading rotation from a single pair.

2. **Per-tile WCS instead of global WCS.** We already have 20 per-tile
   local poles fitted. Use each tile's own pole + a tile-local rotation
   to project Gaia stars within that tile only. Distortion is locally
   small, so a per-tile linear WCS should work where the global one
   doesn't.

Either way, **the manual identification step needs to be confirmed
visually before we commit to a model**. Best approach: render the
30-min derot whole frame at moderate stretch, side-by-side with a
planetarium chart of the visible northern sky at observation time
(any planetarium app or stellarium image), and confirm by eye which
detection is which star. Then the WCS fit becomes well-posed.

## Tools written this session

In `~/astro/bin/`:

- `wcs-from-anchors` — one- or two-anchor WCS builder (CD-matrix sign bug)
- `cross-match-gaia` — detections CSV + WCS JSON → Gaia matches
- `solve-detections` — wraps astrometry.net solve-field
- `photo-compare` — rank-based zeropoint without needing a WCS
- `sky-chart-polar` — polar projection chart oriented to match camera
- `find-known-stars` — match known bright stars to detections by pole-distance
- `relative-pattern` — distance + brightness match for cluster patterns
- `overlay-corrected` / `overlay-gaia` / `overlay-gaia2` — Gaia overlay on tile JPGs
- `orient-check` — rotation from anchor pair
- `match-from-capella` — match by sky-distance from a reference

Notes:
- `notes/star-ids-2026-05-30.md` — captures the Big Dipper / Alioth
  identification chain.

## Original numbered plan

1. Calculate position of A5 in sky from pole pixel + angular size + horizon angle.
2. Get Gaia candidates that fit A5's tile and are bright; plot for confirmation.
3. Sweep all non-rejected tiles with the same process.
4. Plot a Gaia sky map for visual matching against our camera frame.

Items 0 and (partially) 4 are done. Items 1, 2, 3 await a confirmed
orientation.
