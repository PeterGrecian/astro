# Tracking is iterated derot at patch scale

Written 2026-06-05. Builds on [[per-tile-effective-pole]] and
[[zonal-derot-strategy]].

## The framing

Derot, stacking, and tracking aren't three operations. They're
**one operation — derot — applied at different scopes and used
for different purposes**:

- **Derot**: given `(pole, angle)`, transform coordinates from
  frame B's reference into frame A's reference. The primitive.
- **Stacking**: derot applied to many frames into a single
  accumulator → pulls signal from noise.
- **Tracking**: derot applied incrementally frame-by-frame to one
  patch. Predict where the candidate should appear next, look there,
  record where it actually appeared.
- **Track confirmation**: derot-stack the predicted positions of a
  candidate across N frames. Real stars sharpen into a point;
  noise stays smeared. Same as derot-patches but with a
  pole-evolving target position.

All four are the same coordinate transform. The differences are
*scope* (one patch vs whole frame), *timescale* (one frame vs
many), and *what you do with the result* (extend the track,
accumulate into stack, measure residual).

## Tracking requires re-derot of the same data

A track produces (predicted, actual) pairs across frames. Those
pairs feed pole-fitting, which produces a refined pole. The
refined pole changes predicted positions for every frame in the
track — even frames already processed.

So the loop is genuinely:

1. Derot a short window → find a candidate.
2. Track-derot the candidate forward frame-by-frame using current
   pole → build a partial track.
3. Use the partial track to refine the local (tile) pole.
4. **Re-derot the entire track under the new pole.**
   - Already-processed frames now have updated predictions.
   - Track may extend further forward.
   - Earlier frames previously rejected may now fit (track extends
     backward in time).
5. Refine pole from extended track.
6. Repeat until track and pole both stop growing.

Each iteration is a full derot pass *over the frames in the
track*, not over the archive. Cost is bounded by track length,
not by data volume.

## Patch-scale derot makes the iteration cheap

Tracking operates on small patches around the candidate (~20 px
square), not whole frames. A 20×20 warp is microseconds on any
modern CPU — orders of magnitude cheaper than full-frame derot.

Reference numbers from the benchmark on the camera pis:

| Operation | Pi 4 | Pi 5 |
|---|---|---|
| Full-frame warp (12 MP) | ~130 ms | ~40 ms |
| Patch warp (20×20) | ~10–100 µs | ~5–50 µs |

So even on Pi 1B class hardware, the iterative bootstrap is fast
when restricted to patches. Doing the derot dozens of times across
the convergence loop costs milliseconds total per star.

## What this means for the toolset

The existing `derot-patches` is already most of one iteration of
the tracker. It takes candidates, derot-stacks small patches over
N frames at a fixed pole. What it doesn't do is *extend the patch
position* between iterations using a refined pole.

Reused primitives from existing tools:

- Patch extraction and shifting (derot-patches)
- Per-patch derot-stack (derot-patches)
- Per-patch sharpness measure (fit-pole's score)
- Time-based per-frame angle from EPOCH_MS (shared utility)

New ingredients:

- Per-iteration patch re-centring using actual peak position
- Per-iteration pole refinement using vector residuals
- Per-iteration track extension forward (next frames) and backward
  (earlier frames now reachable with the better pole)
- Convergence detection (track stops extending, pole stops moving)

That's a surgical extension. The new tool — call it `track-stars`
or `bootstrap-tracks` — wraps the existing patch derot primitives
in an outer iteration loop with residual-driven updates.

## Track residual is also the goodness measure

There's no separate "is this candidate a star?" test. It IS the
track:

- Real star: residuals stay small under the improving pole, track
  extends frame after frame as the pole tightens.
- Noise / hot pixel: residuals don't tighten, track doesn't
  extend, pole-fit votes from this candidate become noise that
  the other candidates outvote.
- Slow-moving artefact (window reflection, satellite glint):
  residuals are systematically large in a consistent direction.
  Detectable as an outlier in the per-candidate residual
  distribution.

The tracker doesn't need a separate detection threshold. Stars
*are* the candidates whose tracks extend.

## Per-tile interaction

Each tile's inner loop runs this tracking process on its own
candidates, with its own local effective pole as the iterating
variable. Stars that cross tile boundaries become track segments
that get handed from one tile's loop to the next.

The outer unification (per-tile-effective-poles → global pole +
distortion field) happens at a slower cadence. Between
unifications, each tile evolves its tracks and pole
independently.

## Open questions

- Patch size for tracking. 20–30 px square is a reasonable
  starting guess; needs empirical tuning. Too small and a slightly
  wrong pole loses the star. Too large and the patch absorbs
  neighbouring stars or background variation.
- Re-centring method. Simple peak-find (cheap, fragile to hot
  pixels) vs. Gaussian centroid (robust, slower). Existing
  derot-patches uses peak-find; worth measuring if centroid gives
  noticeably tighter track residuals.
- Whether to track backward in time on every iteration, or only
  forward. Backward-extension catches stars that needed a better
  pole to be detectable early; cost is doing the patch warps for
  more frames each iteration.
- How to detect a genuinely lost star vs. one waiting on a better
  pole. Probably: keep candidates "in suspense" rather than
  dropping them, retry after each pole refinement.
