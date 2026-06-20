# Catalog-match & multi-night stacking — parked

**Status**: parked exploration, not active work. Moved out of TODO.md
2026-06-20 (it was resume-notes + design references, not a task list).
Revive when the per-night pipeline is mature enough to need it.

## Gaia catalog match

The Gaia catalog-match exploration is parked. Full design and what
worked / didn't is in `TODO_fit.MD` (deleted 2026-06-16; available in
git history at the commit before the legacy-pipeline deletion).

Resume points if revived:

1. Multi-anchor WCS fit (Polaris + 3–4 Big Dipper stars) to constrain
   (pole_x, pole_y, plate_scale, rotation, k1, k2) jointly.
2. Per-tile WCS instead of global — local distortion is small.
3. Visual side-by-side confirmation of identifications before
   committing to a model.

## Multi-night stacking

`derot-week` deferred until the per-night pipeline matures. Background
and approach in:
- `design/per-tile-effective-pole.md`
- `design/tracking-is-iterated-derot.md`
- `design/zonal-derot-strategy.md`
