# Accumulator outlier rejection — keeping clouds, planes and glints out of the sum

**A cloud, plane, satellite or cosmic ray must not co-add into the sidereal
accumulator. The method: reject per sphere-cell, temporally — because de-rotation
turns the accumulator into a stack of independent samples per cell, contaminants
are rejectable as temporal outliers within each cell before the sum.**

Drafted 2026-08-03 (astro-science). Design only. Prompted by Peter's worry that
clouds and planes will spoil the accumulation. The accumulation theory in STATE
("the thrust" + "accumulation theory") assumes clean input; this doc adds the
robustness layer it needs. It is the co-add twin of the identification principle
already on record ("persistence = identity", `zenith-quests.md`): identity keeps
transients OUT of the catalogue; this keeps them out of the STACK.

## Why the naive sum is fragile

The accumulator co-adds thousands of de-rotated frames into each sphere cell. A
plain sum is **not robust**: a single contaminated frame injects its full flux.

| Contaminant | Signature in the accumulator | Why a sum fails |
|---|---|---|
| **Cloud** | broad, correlated brightening across *many* cells for a *run* of consecutive frames; raises the pedestal, scatters/absorbs starlight | adds a large slowly-varying background to every cell it covers; not a point, not rejectable per-cell in isolation |
| **Plane / satellite** | a bright **streak** crossing a line of cells, present in 1–few frames, moving frame-to-frame (NON-sidereal) | dumps a bright spike into each crossed cell for those frames — a classic positive outlier |
| **Meteor** | like a plane but faster (1 frame), brighter | single-frame positive spike |
| **Cosmic ray / hot pixel** | 1–2 px spike, hot pixel is *fixed in sensor coords* so it SMEARS to an arc on the sphere | spike; hot pixel already handled by the master mask but the arc-smear is the tell |
| **Aircraft strobe** | periodic bright point, non-sidereal | repeated single-frame spikes at drifting cell positions |

The unifying property: **contaminants are NOT sidereally persistent.** A real star
lands in the same sphere cell every frame it's visible (that's the whole point of
de-rotation); a plane, cloud edge, meteor or strobe does not — it is present in a
few frames and its position on the sphere is uncorrelated with the sky. That is
exactly the handle "persistence = identity" uses for the catalogue, applied here
to the sum.

## The method — per-cell temporal outlier rejection

**De-rotation is what makes this easy.** After mapping through the vector field
(`hierarchical-vector-field.md`), each sphere cell accumulates a *time series* of
samples — one per frame that landed there. A real star's samples are a tight
distribution (photon noise about its true flux); a contaminant is a gross
outlier in that per-cell series. So reject **in cell-space, temporally**, not in
frame-space:

1. **Robust per-cell statistic, not a sum.** For each cell, form the sample
   series {value, frame_time} and combine with a **robust estimator** —
   sigma-clipped mean, or a windowed median, so a few high samples (plane spike,
   meteor) are discarded before averaging. Keep a running (median, MAD) per cell
   as frames stream in; clip samples beyond κ·MAD (κ≈3–5). This is the drizzle
   accumulation with a robust combine instead of a straight add.
2. **The accumulator already holds the reference to clip against.** The whole
   value of the deep stack is a low-noise estimate of each cell's true brightness.
   Once seeded, that IS the "expected" value — a frame's sample far above it is a
   positive outlier (plane/cosmic ray); reject it, don't add it. Bootstrap from
   the robust median on the first pass, then clip against the accumulator itself.
3. **Weight by inverse variance / clip, per cell per frame.** A contaminated
   sample contributes 0 (rejected) or down-weighted; a clean sample contributes
   1/σ². Net: the sum sees only clean flux, and the effective N per cell is
   tracked (so faint-limit depth is honest — a cell clobbered by planes half the
   time is genuinely shallower there).

## The named technique — RANSAC at the model-fit layer (Fischler & Bolles, 1981)

The technique already in the estate for this (memory
`project-v3w-star-id-moon-anchor.md`) is **RANSAC** (RANdom SAmple Consensus,
Fischler & Bolles 1981 — the classic two-inventor robust-fitting method). It
rejects at a *different* level from the per-cell clip: it throws out whole bad
**tracks / anchors** from the geometry fit, rather than bad samples from a cell's
sum. The two are complementary layers of the same principle.

**How it's used (proven on real data):** fit the sidereal-rotation vector field
to the measured star tracks with RANSAC — a track is an *inlier* if its motion
obeys the rotation model within a tolerance (07-03: TOL = 0.10 px/s → 6 inliers
incl. Altair, 5 outliers = the bad dense-cluster tracks). The elegance Peter
noted: **"no need to classify; stars obey the rotation, everything else
doesn't."** A plane, a wind-jittered tree, a satellite, or a tracker that jumped
between neighbours simply fails the sidereal-consensus model and is dropped —
without ever labelling *what* it is. A whole catalogue of spurious "stars" that
DRIFTS ~9 px over 20 days while real stars stay fixed is rejected the same way.

So RANSAC protects the **field** (the camera→sphere map itself), and the per-cell
temporal clip protects the **sum** through that field. A contaminant that would
corrupt the geometry is rejected as a model outlier; one that only adds spurious
flux is rejected as a per-cell sample outlier. Same idea — *non-sidereal ⇒
reject* — applied at the two places the accumulator can be spoiled.

## Two scales, two mechanisms — reject cheap-and-coarse, then fine

Rejection is **hierarchical**, matching the field method: throw away obviously-bad
data cheaply before the expensive per-cell work.

### Coarse — frame/region gating (mostly EXISTS)
- **Whole-night cloud verdict** already gates stacking: `sky_clear_max_stops` +
  the dark-trough brightness anchor call a night cloudy and skip it (astrocam
  `camera.json`; the 2026-08-03 miscalibration in STATE was exactly this gate).
  Keep it as the first filter — a solid-overcast night never enters the
  accumulator.
- **Per-frame / per-region brightness** rejects *partial* cloud a whole-night
  verdict misses: a frame (or a sky-region within it) whose brightness/star-count
  drops is cloud-veiled *now*; gate that frame's contribution to the cells it
  covers. The v3w `brightness_roi` (top-half) and the per-frame sensitivity
  already computed by the pipeline are the inputs. This is where **partial and
  moving cloud** is caught — the case a night-level verdict cannot see.
- **Streak pre-detection** catches planes/satellites at the frame level: a bright
  elongated **non-sidereal** connected component (moves the wrong way / wrong
  rate vs the known drift field) is masked out of that frame *before* de-rotation,
  so its pixels never reach the cells. Reuses the trail-line-filter machinery
  (`trail-line-filter.md`) — sidereal trails are the wanted signal at the known
  analytic angle; a plane is a streak at the *wrong* angle/rate → reject.

### Fine — per-cell temporal clipping (NEW, the method above)
Whatever survives coarse gating still gets the per-cell robust combine, because
(a) coarse gating has false negatives (a thin cloud edge, a faint satellite glint
below the streak-detect threshold), and (b) cosmic rays and hot-pixel arc-smear
are inherently per-cell. The per-cell clip is the backstop that needs no
detector — a contaminant that slips every frame-level filter is *still* a
temporal outlier in its cell.

## Clouds are the hard case — a note

Point contaminants (plane, meteor, cosmic ray) are **positive** outliers and fall
cleanly to per-cell clipping. **Cloud is harder** because it is (a) *correlated*
across many cells (so it's not an isolated per-cell spike — a whole region lifts
together) and (b) can *dim* as well as brighten (absorbing starlight → a
*negative* excursion the clip must also catch, or the star just goes missing that
frame, biasing the mean down). Handling:
- Cloud's correlated, extended signature is what frame/region **brightness
  gating** is *for* — reject the frame's contribution where the region is veiled,
  rather than trying to clip cloud cell-by-cell (it's not an outlier locally, it's
  a consensus shift).
- The residual (thin high cloud that dims uniformly by a fraction) shows as a
  frame-wide scale factor; a **per-frame transparency estimate** (ratio of bright-
  anchor fluxes this frame vs their accumulator reference — the bright stars serve
  again, as photometric references) either normalises the frame or, if too low,
  drops it. This reuses the bright-anchor grid the vector field already tracks.

## Why this fits the estate cleanly

- **Same principle, new use.** "Non-sidereal ⇒ not real" already powers
  identification (persistence = identity); here it powers the sum (persistence ⇒
  keep, transience ⇒ clip). One idea, two products from the same per-cell/
  per-source time series.
- **The bright anchors work triple duty:** geometry (vector field), photometry
  (per-frame transparency reference for cloud), and now the clip reference.
- **Honest depth.** Tracking effective-N per cell after rejection means the
  accumulator reports where it is genuinely deep vs where planes/cloud thinned the
  sample — feeds the capacity-law accounting in STATE.
- **Prior art to reuse:** legacy `median_dark.py` (per-pixel median across
  frames), `arc_walk3` iterative outlier rejection (pole fit already clips), the
  streak "reject variants" (`legacy/README.md`), the master hot-pixel mask, and
  `trail-line-filter.md` (analytic sidereal-angle filter → planes are off-angle).

## Status / open questions

- **Design only.** The per-cell robust combine is the piece to prototype: on an
  archived night, stack a region with (a) straight sum vs (b) sigma-clipped, with
  a known plane/satellite pass in frame — confirm the streak vanishes from the
  clipped stack with negligible loss of stellar depth.
- **Clip vs frames-are-few.** Near a bright star, or in a cell a bright anchor
  only visits briefly, N per cell can be small — sigma-clipping needs enough
  samples. Choose κ and the minimum-N guard so we don't clip real signal in
  low-N cells (fall back to median, or don't clip below N≈5).
- **Negative-outlier cloud** (starlight absorbed) is the subtlest: prefer
  frame/region gating + transparency normalisation over per-cell negative
  clipping, which would bias against real variability (e.g. a genuinely variable
  star dimming). Keep the variable-star science safe — don't clip a star just for
  being faint one night; clip the *frame* when the *anchors* say it was cloudy.

## See also
- `design/hierarchical-vector-field.md` — the field the samples are de-rotated through; "persistence = identity" is the identification twin of this.
- `design/trail-line-filter.md` — analytic sidereal-angle streak filter → off-angle streaks are planes.
- `design/zenith-quests.md` — persistence = identity (the catalogue-side rejection).
- STATE.md (astro-science) — "accumulation theory" (drizzle/TDI) this robustifies; the 2026-08-03 cloud-verdict fix (the coarse gate).
- legacy: `median_dark.py`, `arc_walk3.py`, streak reject variants — reusable robust-combine prior art.
- memory `project-v3w-star-id-moon-anchor.md` — RANSAC (Fischler & Bolles) rejecting planes/trees/bad-tracks against the sidereal model; the proven model-fit rejection layer.
