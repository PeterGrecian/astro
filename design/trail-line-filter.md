# Trail line-filter — extract star trails, suppress dots + cloud

Drafted 2026-06-28. For the diff-sweep deliverable: it shows two unwanted
classes alongside the star trails —
1. **dense single-pixel dots** (noise / hot pixels), and
2. **fuzzy non-linear cloud** (a smooth bright glow).
Both make the mp4 high-bandwidth and noisy. Goal: keep the linear trails,
suppress the rest. (Less critical: the cloud. More critical: the dots.)

## The approach (validated on crops 2026-06-28)

**Oriented morphological line-filter, per-pixel, along the ANALYTIC trail
direction:**
- `along  = open(img, line_kernel @ local_angle(x,y))`
- `across = open(img, line_kernel @ local_angle(x,y) + 90°)`
- `out    = clip(along - across, 0, 255)`, then threshold.

Why each unwanted class dies:
- **dots**: smaller than the line kernel → erased by the opening at any angle.
- **cloud**: isotropic/smooth → responds equally along & across →
  `along - across ≈ 0` → cancels.
- **trails**: bright along their orientation, dark across → `along - across`
  survives.

Kernel length must MATCH the trail length. Measured (eclipticam-v3w diff,
binned): trails are ~8-11 px dashes → **L ≈ 7** works; L=15 erodes them.

## The KEY simplification (Peter's hint): orientation is ANALYTIC

The trails are co-oriented *locally* but the direction VARIES across the
frame (barrel curvature). Do NOT estimate it (structure tensor catches cloud
edges, noisy). **Compute it from the calibration we already trust:**
- detrans `angle_deg = 7.8°` = the uniform star-motion direction in
  UNDISTORTED space.
- distortion `k1=-0.636, k2=0.311` bends that into the curved trail direction
  in the DISTORTED frame (diff-sweep does NOT undistort — frames are distorted
  binned 1152×648).

Local trail angle field = inverse-Jacobian of the undistort map applied to the
7.8° unit vector. Validated (closed-form FD, eps=2px, on 1152×648):
- centre 7.8°, corners ~53° / ~109° (symmetric), smooth, no noise.
- This is the per-pixel `local_angle(x,y)`; precompute once per camera.

## Implementation plan (chosen: in bin/diff-sweep)

1. Precompute `local_angle(x,y)` once from camera.json (k1,k2,detrans.angle).
   Discretise to ~12 orientation bins.
2. Precompute the N oriented openings of the diff frame; index each pixel into
   its local-angle bin for `along`, +90° for `across`.
3. `out = threshold(along - across)`. ~0.05s/frame at 1152×648 (measured on
   crops, scales linearly).
4. Add as a diff-sweep post-step behind a flag (e.g. `--line-filter`) so we
   can A/B it; default on for eclipticam-v3w once verified on a full frame.

## Status / next
- Algorithm + analytic field VALIDATED on crops (~/tmp/trails*.png,
  final-*-L7.png, lo-*.png). Trails kept (0.4% lit), dots ~gone (34062→70px),
  cloud cut (21%→~3%).
- TODO: implement in diff-sweep, validate on a real FULL diff frame (curved
  trails near edges — the analytic field's reason to exist), tune threshold,
  flag-gate. Then the diff sweep emits clean low-bandwidth frames.
