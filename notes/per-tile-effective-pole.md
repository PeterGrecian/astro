# Per-tile effective poles: decoupling the inner loop

Written 2026-06-05. Builds on [[zonal-derot-strategy]] and the
bootstrap-loop synthesis (tracks ↔ pole co-estimation).

## The insight

Lens distortion means **each tile has its own effective pole**:
the rotation centre that correctly derotates stars *within that
tile* is the true celestial pole plus a local distortion-induced
offset at the tile's image position.

This is operationally good. Each tile can fit its own local pole
**independently and cheaply**, without needing a global distortion
model. The distortion field is then *recovered for free* from the
spatial pattern of per-tile effective poles.

## Why this decouples the bootstrap

The previous co-estimation picture had three coupled unknowns:
**pole**, **distortion**, **tracks**. Each interacts with the
others; bootstrap is hard.

Per-tile recasting:

- **Inner loop (per tile)**: only two unknowns — local effective
  pole + tracks within the tile. Distortion is constant *within
  the tile* and can be absorbed into the local pole offset.
- **Outer loop (across tiles)**: only one unknown — the global
  pole + distortion field, fit to the set of per-tile effective
  poles. No tracks involved at this level.

The chicken-and-egg with distortion is gone at the inner-loop
level. Distortion only re-enters when unifying the per-tile
results, and at that point it's a sparse fit (one constraint per
tile, ~30 tiles total) over a smooth field. Trivial.

## Properties

1. **Embarrassingly parallel across tiles.** Each tile's inner
   loop runs independently. Many small fits beat one big fit on
   convergence reliability and runtime.

2. **Small basin per tile.** Tracks within a tile span a small
   sky region; local pole-vs-tracks has a tight, convex-ish
   landscape. Bootstrap converges quickly per tile.

3. **The map of per-tile effective poles IS the distortion
   field.** `tile_pole - centre_tile_pole` (or
   `tile_pole - global_pole_estimate`) measured at each tile's
   centroid gives the distortion offset there. Plot it as a
   vector field and the distortion structure is immediately
   visible. Smooth low-order polynomial fits the field.

4. **Cross-tile track segments link tiles.** A single star
   crosses tile boundaries as it traverses the field. Its
   residuals contribute to each tile's local pole-fit in sequence.
   That same star also provides a cross-tile constraint: its
   position transitioning between tiles must be consistent across
   the boundary. Useful in the outer unification step.

5. **The leverage-vs-distance argument collapses within a tile.**
   All tracks in one tile are at roughly the same radius from
   that tile's local pole, so the weighting is approximately
   uniform within a tile. The "near-pole stars are leveraged
   differently from far-pole stars" reasoning becomes "different
   tiles have different fit-quality" — same idea, simpler
   bookkeeping.

## Pipeline shape

```
Inner loop (per tile, cheap, parallel):
  Inputs:  tile id, seed candidates, current local pole guess
  - extract track segments within the tile
  - co-estimate (local pole, tracks) by alternating:
      tracks → local pole correction
      local pole → predict next frame → extend tracks
  - converge → emit (tile_id, local_pole_xy, track_segments)

Outer loop (across tiles, occasional):
  Inputs: all (tile_id, local_pole_xy) tuples
  - fit global pole + low-order distortion model
  - emit improved distortion field + global pole
  - improved field → better starting guess for next inner-loop
```

The outer loop runs *much less often* than the inner — typically
once per night, or once per archive-wide re-calibration. The
inner loop runs every time new frames arrive.

## Implications for the track database

Tracks are no longer "this star, this sequence of frame positions"
as a single object. They are **(star_id, frame, tile, predicted_xy,
actual_xy)** records. A star contributes to multiple tiles over
its trajectory through the field. The database is keyed by all
three dimensions and queried per-tile in the inner loop, per-star
in the outer (cross-tile consistency check) loop.

This is also closer to how real survey instruments work:
per-detector astrometric calibration first, then a global solution
that ties detectors together via overlap stars.

## Implications for bootstrap

The 5 tiles with reliable bright stars (e.g. A5, C1, C3, D2, E1 on
the 2026-05-30/01b data) each become an **independent bootstrap
source**. Each can boot its own inner loop with no dependencies
on the others. Once a few inner loops have converged, their local
poles seed the outer unification, which seeds initial guesses for
inner loops on harder tiles.

Order of operations:

1. Hard-reject tiles with foliage, leakage, vignette (manual,
   per-night).
2. Per-tile candidate detection (existing find-candidates,
   restricted to one tile at a time).
3. Per-tile inner loop on tiles with strong seed candidates.
   Parallel. Each emits a local pole.
4. Outer unification → global pole + coarse distortion field.
5. Re-seed inner loops on harder tiles using the coarse
   distortion field's predictions. Parallel again.
6. Re-unify outer. Repeat until convergence.

## What this changes in the existing toolset

The existing tools (`find-candidates`, `derot-patches`, `fit-pole`,
`derot-stack`) are all *global*: they operate on whole frames with
a single pole. To support per-tile inner loops they need a
`--region` or `--tile` argument that restricts inputs to a
rectangular subset of the frame. The fit-pole optimisation
landscape becomes tile-local — almost certainly faster to converge
since the search space is smaller and the residual landscape
cleaner.

Track-segment management — the (star_id, frame, tile,
predicted_xy, actual_xy) database — is genuinely new code. Likely
a small SQLite database (or just a flat parquet/csv per session)
that the inner and outer loops both read/write.

## Open questions

- Tile size for inner-loop pole-fitting: the 8×6 = 48 grid was
  chosen for visual rejection. Is it also the right grid for
  per-tile pole-fitting? Probably finer would help precision but
  too fine starves each tile of stars. Empirical question once
  one tile's inner loop is working.
- How to handle stars that cross tile boundaries during their
  track: contribute to both tiles' fits with appropriate weighting?
  Tagged with a tile transition? Worth thinking about once we have
  data showing the effect.
- Whether the outer unification should treat distortion as static
  across nights or as slowly time-varying (thermal flex, mount
  settling). Probably static for the first version; revisit if
  per-night distortion maps show consistent drift.
