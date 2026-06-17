# Zonal derot strategy: leverage-aware accumulation

Written 2026-06-05. Builds on [[pole-from-sun-moon]] and
[[drift-scan-cadences]].

## Two trustworthiness maps

Pixels on the sensor are *not* equivalent for calibration purposes.
Two independent maps govern how much each pixel can be trusted:

### 1. Pole-leverage map

For a star at radius `r` from the pole, a small pole displacement
δp shifts its predicted position by approximately δp × (1/r) in
the angular direction along its arc. So:

- **Far from pole (large r)**: low leverage. Pole error rotates the
  tangent direction by a small angle. Position error stays small.
  Robust to coarse pole estimates.
- **Near pole (small r)**: high leverage. The tangent direction
  varies rapidly. Small δp can rotate the tangent significantly,
  or even reverse it. Predicted positions become essentially
  random with respect to truth.

**Sign of leverage:** high leverage means "very sensitive to pole
error" — so near-pole patches are catastrophically misleading when
the pole is seriously wrong, but the most precise refiners once
the pole is approximately right.

### 2. Lens-distortion-quality map

Lenses are sharpest and most linear at the centre, with distortion
growing outwards (typically as a low-order polynomial). For
fisheye/wide-field optics like the OV5647 / IMX708 used here:

- **Centre 9th**: lowest distortion, most trustworthy positions.
- **Edge 9ths (non-corner)**: moderate distortion.
- **Corner 9ths**: worst distortion. Useful only once the
  distortion model itself is well-characterised.

The maps are **independent**: a near-pole pixel can have low or
high distortion; an edge pixel can be near or far from the pole.
Camera-specific: starcam/astrocam have the pole in-frame so both
maps matter; eclipticam has the pole off-frame so only the
distortion map matters intrinsically.

## 3×3 zonal discretisation

A 3×3 grid (ninths) is the simplest discretisation that captures
both maps. Each ninth has its own treatment based on its position
relative to:
- the pole (for cameras that see it)
- the optical centre

The strategy unfolds in stages:

### Stage 1 — coarse pole fit

Use **edge ninths farthest from the pole**. For starcam, these are
3-4 ninths on the opposite side of the frame from Polaris. Stars
here:
- Have low pole-leverage (robust to coarse pole)
- Have moderate distortion (acceptable for coarse fit)
- Provide clean, well-behaved residuals → stable optimisation
  landscape

Run pole-fitting on these ninths only. The pole estimate that
comes out is approximately right (pixels, not arcseconds), but
that's enough to bootstrap.

### Stage 2 — pole refinement

Include progressively more ninths as the pole estimate tightens.
Near-pole ninths start contributing meaningful signal once the
pole is within their leverage radius. The convergence loop:

1. Run derot-accumulate on the included ninths.
2. Measure residuals (vector, per star — see below).
3. Update pole estimate from residual votes.
4. Re-derot.
5. If residuals are still tightening, **expand the included set**
   to bring in more ninths.
6. Repeat until residuals plateau.

### Stage 3 — distortion fit

Once the pole is solid and the centre ninth's stars are crisp,
the residuals in the **corner ninths** tell you about distortion,
not pole. Fit a low-order polynomial distortion model from those
residuals.

The structure is the same algorithm at every stage: derot,
accumulate, measure residuals, refit. The only thing that changes
is **which inclusion mask** is in play. Write one
`derot-accumulate` tool that takes a mask; the calibration
pipeline is a sequence of mask choices.

## Residual vectors, not RMS

A single star's measured-position minus predicted-position is a
**2D vector** in the image plane, not a scalar. Project it onto:

- **Tangent direction** (along the star's arc) → "is the rate
  right?"
- **Radial direction** (toward/away from pole) → "is the pole
  position right?"

Cross-track (radial) residuals at many stars **vote** on where
the pole should move:

- Far-from-pole stars vote weakly but unanimously.
- Near-pole stars vote strongly but each individually (so they
  need vetting against the consensus before being included).

A weighted average gives a pole-correction step. The weighting
is essentially the pole-leverage map — you trust each star's
vote in proportion to how cleanly it constrains the pole.

## Asymmetric raw retention

Stage 1's coarse-pole stack uses 3/4 of the frame; the near-pole
quarter is kept *raw* until stage 2/3 produces a good pole.
**Only the near-pole region needs raw retention** — the rest is
already accumulated into stacks.

For starcam (pole in-frame): keep ~1/4 of raw data per night
until pole converges; then retrospectively derot it with the
final pole estimate and trash the raws. Bounded retention
horizon, not "ever might want it."

For eclipticam (pole off-frame): the asymmetric retention doesn't
apply — there's no near-pole region to protect. Derot-accumulate
the full frame from the start, with the *distortion* map being
the dominant calibration challenge instead.

## Sub-zonal refinement

3×3 is a starting discretisation. If a particular ninth shows
**internal structure** in its residuals — e.g. one corner of one
ninth is systematically worse than the others — that's a hint to
sub-zone it. The pipeline is the same recursive structure: zones
within zones, each with their own inclusion mask.

Final form is per-pixel weighting in the stack, with weight =
some function of (distance from pole, distance from centre,
current calibration uncertainty). The 3×3 scheme is a
human-tractable proxy for that.

## Diagnostic value: the zonal residual map

A 3×3 grid of per-zone residual RMS, plotted over time, is
itself a useful diagnostic image. Patterns:

- All zones tighten together → pole was the dominant error.
- Centre tightens, corners stay loose → distortion is the
  next-dominant error.
- One zone always worse than the others → physical artefact
  (smudge, dust, vignette, hot region).
- All zones flat after stage 1 → pole is in a local minimum,
  consider reseeding.

The diagnostic loops back to operations: if a zone consistently
underperforms over many nights, the cause is probably hardware
(lens, sensor, window) rather than algorithm.

## Comparison with current astro/bin/ tools

The existing pipeline (`find-candidates` → `derot-patches` →
`fit-pole` → `derot-stack`) already does **patch-based pole
fitting**, which is the conceptual ancestor of this scheme. The
zonal strategy extends it in three ways:

1. **Mask-driven inclusion** rather than fixed-N-brightest
   patches. The mask encodes the leverage logic.
2. **Iterative refinement** rather than single-pass fit.
3. **Vector residuals** rather than sharpness scalar.

The existing tools should compose under this strategy without
rewrite — `derot-patches` becomes a primitive called by the
outer accumulate-and-refit loop.

## Open questions

- What's the right far-from-pole patch density for stage 1?
  Probably "as many bright stars as you can find in the eligible
  zones" — let `find-candidates` decide.
- What stops the refinement loop? Probably "residual change <
  threshold across an iteration" rather than fixed iteration
  count.
- Does the asymmetric retention help in practice, or is it a
  premature optimisation? Worth measuring on the 3 nights of
  starcam data on muppet before committing.
- Per-zone residual time-series: is this a per-night artefact
  or do patterns persist across nights? If they persist, that's
  a static distortion map worth fitting once and reusing.
