# What accumulation actually buys — position saturates, structure doesn't

**Peter's question (2026-08-03): once a star is pinned to sub-pixel position, why
keep accumulating it? Answer: you don't — for its POSITION. Astrometry saturates
early and the star becomes fixed scaffolding. Deep integration keeps paying off
for three OTHER things, and the deepest is the one Peter named: resolving the
BUMPS in the PSF — unresolved companions, planetary/astrometric wobble, dark
companions.**

Drafted 2026-08-03 (astro-science). Reframes the accumulator's purpose. It does
NOT contradict the accumulation theory in STATE — it says *which* stars need depth
and *for what*, which is an efficiency + science-goal statement the theory lacked.

## The premise is correct — for position

Once a bright star is nailed sub-pixel (streak line-fit → 0.14 px in ONE 55 s
frame; ePSF centroids → CRLB ~0.006 px), **more frames do not improve its
position.** STATE already establishes 0.14 px is *systematics-limited* (per-pixel
gain, intra-pixel response), not photon-limited — so integrating a bright star's
centroid deeper is wasted effort. It's DONE early.

**Consequence (the efficiency win):** the bright anchors don't need deep
integration. They resolve fast and become **fixed scaffolding** — the vector
field's anchors, the photometric references, the clip references
(`accumulator-outlier-rejection.md`), the astrometric frame. Accumulation effort
should NOT be spent re-measuring what's already saturated. This is why "saturation
is not a constraint" (STATE): bright stars are anchors, not integration targets.

## But position is not what accumulation is for

Three things keep rewarding depth long after position has saturated. The first two
are about stars you HAVEN'T resolved; the third is Peter's — about the stars you
HAVE.

### 1. Detection of sources below the single-frame floor (the "see" number)
A mag-15 star isn't "resolved then done" — it isn't *detected at all* in one
frame. The whole "see 100,000" quest (`zenith-quests.md` Q6) is sources the SUM
*creates* out of noise. No amount of sub-pixel work on Altair reveals the faint
stars *between* the bright ones. Depth here = reaching fainter, forever.

### 2. Photometric depth on faint sources (brightness, variability, colour)
Even once a faint star is detected, its *flux* (and its time-variation, its
colour) needs √N integration to measure well. Position saturates; **flux and its
variability keep improving with N.** Light curves, the local `SC-` catalogue's
per-source photometry, variable-star and Cepheid science all live here.

### 3. Sub-PSF STRUCTURE on resolved stars — the bumps (Peter's target)
**This is the real reason to keep integrating a star you've already located.** The
question isn't "where is this star?" (saturated) but "**is this a single point, or
is there structure inside/beside the PSF the single frame can't show?**":

- **Unresolved binaries / close companions** — a second star inside the PSF wings
  shows as an asymmetric bump or a centroid that shifts with wavelength/seeing.
  Only a deep, well-sampled ePSF residual reveals it. (Polaris B, Titan-by-Saturn
  in the quest board are the bright-contrast versions of this.)
- **Astrometric wobble → planets / dark companions** — an unseen companion
  (planet, brown dwarf, dark star) pulls the visible star around the barycentre.
  The signature is a *tiny periodic motion of the centroid over time* — exactly
  what the sub-pixel machinery measures, integrated over the SEASON. Here depth
  buys **time baseline + centroid SNR**, not a single-epoch position: you already
  have position; you want its *derivative structure* across months.
- **PSF-residual photometry** — subtract the ePSF model (built from the clean
  bright anchors) and what remains is the bump: a companion's flux, a disc, a
  glint. This is why the ePSF must come from stars KNOWN to be single — the
  scaffolding stars — so a residual on a TARGET star is real structure, not model
  error.

So for a resolved star, accumulation shifts from *locating* it to **modelling what
the single point-source assumption leaves over**. Position was the easy part;
the bumps are the science.

## The reframing — accumulation is coarse-to-fine in WHAT, not just depth

The magnitude-ladder / brightest-first method (`hierarchical-vector-field.md`) has
a natural companion here: each star climbs a ladder of *questions*, and only the
last one wants unbounded depth:

| Stage | Question | Saturates at | Then the star becomes |
|---|---|---|---|
| **Locate** | where is it (sub-pixel)? | ~1 frame (bright) / few (faint) | an anchor / a catalogue entry |
| **Detect** (faint) | is it there at all? | the depth that clears noise | a new `SC-` source |
| **Photometer** | how bright, how variable, what colour? | √N (ongoing) | a light curve |
| **Resolve structure** | single point, or a bump (companion/wobble/planet)? | **never — deeper is always better** | a science result |

The bright stars finish at "locate" and hold still as scaffolding. Faint stars
climb through detect → photometer. And the deepest use of the accumulator — the
one that justifies *forever* integration — is **resolve-structure**: the bumps in
the PSF that are companions, wobbles and dark stars. That is the answer to "do we
really need to accumulate it further": not for its position, yes for its
*structure*.

## Practical consequence — don't integrate the anchors, DO keep their residuals

- **Skip deep integration of the anchors' centroids** — they're saturated
  information. Spend the accumulator on faint detection + faint photometry.
- **BUT keep the anchors' ePSF residuals over time** — the wobble/companion signal
  is IN the bright, well-measured stars (they have the SNR to show a tiny
  centroid perturbation). So the anchors are done for *position* but are the best
  targets for *structure*. The per-frame source tables (kept forever per the
  retention rule) already hold the centroid time series structure needs.
- **The ePSF must be built from confirmed-single scaffolding stars**, else a
  companion bump is indistinguishable from model error. Ties the "resolve
  structure" goal to the identification/local-catalogue work: knowing a star is
  single is a prerequisite for using it as a PSF template AND for trusting a
  residual on another star.

## Status / open questions
- **Design / framing only.** Detection + photometric depth are the accumulator's
  already-planned outputs; **PSF-residual structure is a new stated goal** — the
  ePSF residual pipeline (build model from single stars → subtract → hunt bumps)
  and the multi-month centroid-wobble search are not designed yet.
- **How deep before a wobble is detectable?** A planet/dark-companion wobble is
  sub-milliarcsecond for most systems — likely *below* this rig's floor except
  for nearby high-mass-ratio cases. Worth a feasibility estimate (which systems,
  if any, give a wobble within our centroid precision × season baseline) before
  committing — it may be a stretch goal like Titan, real but hard.
- **Companion inside the PSF** (not wobble, but a static asymmetric bump) is more
  reachable than dynamical wobble and is the natural first target — the same
  contrast problem as Polaris B / Titan, generalised to every resolved star.

## See also
- `design/hierarchical-vector-field.md` — brightest-first; the anchors this says become scaffolding.
- `design/accumulator-outlier-rejection.md` — clean-anchor ePSF is also the clip reference; single-star confirmation matters to both.
- `design/zenith-quests.md` — Q6 (see/identify depth), Polaris B + Titan (the bright-contrast structure targets), the sub-pixel info-theory (position saturates, systematics-limited).
- STATE.md (astro-science) — "saturation is not a constraint" (anchors, not targets); sub-pixel foundations (0.14 px, ePSF, CRLB).
