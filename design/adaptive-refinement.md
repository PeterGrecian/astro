# Adaptive refinement — coarse samples, increasingly refined

Peter, 2026-08-16: *"what I really want to do is coarse samples increasingly
refined."*

The accumulator is **not one resolution, nor a fixed stack of resolutions.** It
is an **adaptive tree**: coarse everywhere, refined only where the data shows
there is something to resolve. Depth follows information, not area.

This supersedes the "fixed ladder" framing (build at one N_side, read at
several), which was the weaker idea it grew out of.

## Why this is the right shape for this archive

`what-accumulation-buys.md` already establishes that accumulation is
**coarse-to-fine in the question asked** — locate → detect → photometer →
resolve-structure — and that *only* resolve-structure wants unbounded depth.
Adaptive refinement makes the **resolution** follow that same gradient.

The sky is mostly empty. A uniform 2× drizzle buffer for astrocam's cap is
**606 MB at N_side 8192**, and the fraction of it containing a star worth
resolving is tiny. Uniform depth pays full price for vacuum.

## Why HEALPix, specifically

Settled 2026-08-16. `whole-sky-context.md` recorded that the reason to diverge
from HEALPix (the integer-shift ring quantisation) had been withdrawn, leaving
the choice open. Peter's requirement closes it: *"we are going to do quick runs
through the data and will not be able to do that at full res."*

Ragged rings can be *built* at any resolution, but each build is a separate
structure with its own offset table, and nothing relates a coarse run to a fine
one except re-deriving the geometry. HEALPix gives three things rings do not:

**1. Binning down is EXACT — a bit shift, not a resample.** In `NESTED`
ordering four fine pixels sit exactly inside one coarse pixel, so the parent
index is `child >> 2`. Coarsening is integer addition of children.

**VERIFIED 2026-08-16** (`astropy_healpix` 1.1.2, nside 256 → 128): binning by
bit-shift produced a **byte-identical array** to binning via each fine pixel's
own lon/lat membership. Not approximately equal — `np.array_equal` True.

This matters more here than anywhere else, because the estate's standing rule
is that **resampling error bakes in permanently** (STATE, repeatedly). A
quick-look map made by binning down is *provably the same data* as the deep
map, only coarser. That is a far stronger guarantee than "close enough", and no
hand-rolled ring scheme offers it.

**2. One code path, one parameter.** A quick run and a deep run differ by
`N_side`. No second implementation to keep in sync — which is the class of bug
that produced the `map/accumulate.py` metric problem (two things that should
have agreed about geometry, didn't).

**3. It is a standard.** A set of HEALPix cells at mixed orders is a **MOC**
(Multi-Order Coverage map), an IVOA standard. Adaptive-depth sky maps are a
solved, named, interoperable thing — not something to invent. Our output stays
readable by other tools.

Equal area is confirmed by construction: every pixel has identical solid angle
at any N_side (measured: 169,957 sq-arcsec at nside 512, 10,622 at nside 2048).

## The N_side ladder for astrocam

Cap radius 51.39°, 7,755 sq°, plate scale 0.0207 °/px. **Independent check: the
cap's information floor computes to 1.810e7 elements, matching
`accumulation-bucket-refinement.md`'s 1.81e7 exactly** — two derivations, same
number.

| N_side | resolution | vs pixel | cap cells | uint32 | role |
|---|---|---|---|---|---|
| 512 | 412″ | 5.5× coarse | 5.9e5 | **2.4 MB** | quick run; fits in L3 |
| 1024 | 206″ | 2.8× | 2.4e6 | 9.5 MB | quick run |
| 2048 | 103″ | 1.38× | 9.5e6 | 37.8 MB | ≈ native |
| 4096 | 51.5″ | 0.69 | 3.8e7 | 151 MB | 1.4× drizzle |
| 8192 | 25.8″ | 0.35 | 1.5e8 | 606 MB | 2× drizzle (uniform budget) |

The point of adaptive refinement is that the deep end of this table is only
paid for where earned.

## The refinement criterion — children disagree (variance)

Chosen by Peter, 2026-08-16, over signal-threshold, SNR-budget and
catalogue-driven alternatives.

```
refine(cell):
    split into 4 children
    if spread(children) > k * sigma(cell):
        recurse on each child
    else:
        stop — flat, nothing further to learn
```

**Why this one is right:**

- **Self-terminating on physics, not on an arbitrary depth limit.** Refinement
  stops when children agree within noise, which is the honest statement that
  finer cells would carry no new information.
- **It follows STRUCTURE, which is the stated science goal.** `what-
  accumulation-buys.md` names sub-PSF structure — "the bumps" — as the target:
  unresolved binaries, companions, astrometric wobble. Those live in **PSF
  gradients**, exactly where child cells disagree.
- **It skips saturated cores automatically.** A saturated star is a flat
  plateau; children agree; refinement stops. This is precisely right — STATE
  already records that bright stars are astrometric anchors whose centroids
  saturate early in usefulness, and that *"position saturates, structure
  doesn't."* The criterion spends depth on wings, not plateaus.
- **It skips empty sky.** Background-only cells agree within noise at once.

**The `sigma` must be the cell's own noise**, from its count plane — not a
global threshold. Depth varies enormously across the cap (edge cells see far
fewer frames), so a global sigma would over-refine deep regions and under-refine
shallow ones. The per-cell count planes that
`accumulation-bucket-refinement.md` already mandates are what make this
computable.

**Open — `k` is uncalibrated.** Too low and the tree refines into noise
(expensive, and false structure); too high and real companions are missed.
Calibrate against known doubles: **Mizar & Alcor** is already the estate's
"calibration ruler" quest, and **Polaris B** is the target companion. A
criterion that resolves Mizar and stops is correctly tuned.

## Cadence — iterative, re-refined as data grows

Chosen by Peter, 2026-08-16, over one-pass and two-stage survey/target.

Each accumulation run **reconsiders** the refinement map: cells that were flat
last month may now show structure, because more nights have lowered the noise.
The tree deepens over the year as the data earns it.

This is `retrospective-reprocessing.md`'s "the archive appreciates" applied to
**geometry** rather than to models — a third instance of the same convergent
loop. Growing the archive lowers per-cell noise → the variance test passes in
more places → the tree refines further → finer structure becomes visible.

**The load-bearing constraint this imposes:** the tree must be **rebuildable
without re-reading all raws**. If refining a cell required going back to the
original frames, refinement would be bounded by the ~3-month raw retention
window (`retrospective-reprocessing.md`), and the year-scale goal would fail.

Two candidate resolutions, undecided:

- **Accumulate at a fixed fine N_side, refine the READ.** Store at (say) 4096
  uniformly; the tree is a view over it, recomputed freely. Simple and always
  re-refinable, but pays uniform storage — the thing adaptive refinement exists
  to avoid.
- **Store the tree, and split cells lazily on the next pass.** A cell that
  needs splitting is subdivided when the next night's frames arrive, so new
  data lands at the finer resolution while history stays coarse. Cheap, but
  a cell's history is then coarser than its present — depth becomes a function
  of *when* the structure was noticed.

**This is the main open question.** The second is more attractive and much
harder to get right; it may want the count planes to carry a "refined at epoch
N" marker so a cell's history is interpretable.

## Caveat — binning down is exact only for LINEAR statistics

Sums and counts bin exactly (integer addition of children). **Medians,
percentiles and the 99.9th-percentile sharpness metric `map/accumulate.py`
uses do NOT** — they must be recomputed at each resolution, never binned.

Easy to get wrong precisely because the sum case works so cleanly that one
stops thinking about it.

## `RING` vs `NESTED` — decided, with a note

Use **`NESTED`**. The `>> 2` hierarchy only exists in nested ordering, and the
hierarchy is the whole point.

`RING` is iso-latitude-contiguous and is where a rotation comes closest to an
index shift — which is the ghost of the withdrawn integer-shift argument
returning in new clothes. The answer is the same as before: **drizzle absorbs
the fractional shift; do not buy shift-cheapness with structure.** Convert to
`RING` only if a spherical-harmonic analysis is ever wanted.

## Visualisation — required, not decorative

Peter, 2026-08-16: *"we will need to visualise this."* Right, and it is a
correctness tool here rather than a presentation one.

**Why an adaptive tree specifically demands it.** A uniform grid can be checked
numerically — one resolution, one number per cell. An adaptive tree's central
question is *where did it refine, and was that sensible?*, which is inherently
spatial. `k` cannot be calibrated by reading statistics: the failure modes are
"refined into noise everywhere" and "refined nowhere", and both look plausible
as scalars while being obvious as pictures.

This estate's own record argues the point. **Three times the eyeball beat the
numbers** (STATE, transients): the foliage run where "every *number* looked
right (conf 1.00, ends=0, single sub); only the picture was wrong", the 08-11
contrail, and the detector calibration that came out inverted against Peter's
splay probes. `--save-cutouts` "earned its place on first use". The same
discipline applies here — **look at the tree before trusting its depth map.**

### Four views, in order of usefulness

1. **Depth map — the primary view.** Colour each cell by its refinement level
   (N_side order). This *is* the tree made visible: stars should appear as
   compact deep islands in a shallow sea, and the picture immediately shows
   whether refinement tracked structure or noise. A depth map that is uniformly
   deep means `k` is too low; uniformly shallow means too high; deep in a
   *ring* or along an *edge* means depth is tracking exposure rather than
   structure — the failure the per-cell sigma exists to prevent.

2. **Cell-boundary overlay on a real stack.** Draw the tree's cell edges over
   `max.jpg` or a de-rotated stack. Answers the question the depth map cannot:
   do deep cells sit *on* the stars? Wrong pole or wrong projection shows up
   instantly as a tree refined next to the trails rather than along them. This
   is the geometric sanity check, and it is the one worth building first
   alongside the depth map.

3. **Refinement history.** Since the cadence is iterative, colour by *when* a
   cell reached its depth. Directly visualises "the archive appreciates" — and
   is the diagnostic for the open storage question above, where a cell's
   history may be coarser than its present.

4. **Ladder comparison.** The same region at N_side 512 / 1024 / 2048 / 4096
   side by side — the coarse-to-fine idea shown directly, and the natural way
   to present the deliverable to a reader.

### Practicalities

- **House pattern**: a standalone `bin/` script, `--out` PNG, PIL or matplotlib,
  docstring stating the geometry — following `plot-distortion`,
  `plot-residuals`, `make-epoch-graticule`, `sky-chart-polar`.
- **Project HEALPix cells back through the camera→sphere map for display**, so
  views land in *pixel* space where they can be compared against real frames.
  A mollweide or orthographic all-sky plot is the wrong frame for checking
  against `max.jpg`. (`healpy` has all-sky plotting built in, but we did not
  install it — and its projections are not the ones we want to check against.)
- **Draw cell boundaries as polygons, not pixel fills.** The whole point is
  seeing *cell size vary*, which a fill hides. `astropy_healpix` gives cell
  corner coordinates directly.
- **Expect to view in `splay`** — the estate's still-image viewer, already the
  route for frame inspection and probe marking.
- **This is a `/astro` deliverable too.** A depth map is a genuinely striking
  image — the map showing you where it found things — and
  `catalogue-deliverable.md` wants exactly this kind of public face. But its
  first job is debugging.

## Status and next step

**Design + verified primitives. No accumulator code yet.**

Done: `astropy_healpix` 1.1.2 installed (apt `python3-astropy-healpix`, matching
the estate's system-python convention — note PEP 668 blocks `pip install` on
Ubuntu 25.10); lossless bin-down verified; equal area confirmed; the ladder
computed and cross-checked against the design's information floor.

Next: **prototype on one astrocam hour** — accumulate at N_side 512/1024/2048,
verify a direct build at 512 equals a 2048 build binned down (a correctness
test on the projection itself, not a quality comparison), and time it. Then
apply the variance criterion and see where the tree actually refines.

**Build the depth map and the boundary overlay in the same pass** — not
afterwards. The variance criterion cannot be calibrated without them, and the
estate's own history says the numbers will look right while the picture is
wrong.

## First prototype run — 2026-08-12 hour 01, astrocam (2026-08-16)

`bin/healpix-ladder` (accumulate + exactness test) and `bin/healpix-view`
(render back to pixel space). 20 frames, cap 20°, pole [1392, 978] and plate
scale 0.0208071 °/px — the values **measured from Polaris on 2026-08-14**, NOT
`astrocam/camera.json`, which still carries the stale epoch-1 geometry (a live
config bug already spooled to `ideas/`).

### PASS — bin-down is exact on real data

| step | result |
|---|---|
| nside 1024 → 512 | **IDENTICAL** (5,357,354,088 total) |
| nside 2048 → 1024 | **IDENTICAL** (5,357,354,088 total) |

Byte-identical arrays with matching totals at all three resolutions. The
projection is self-consistent and coarsening involves no resampling — the
property the whole design rests on, now verified on sky data rather than on
synthetic indices.

### FAIL — the variance criterion refined on HEALPix SEAMS, not stars

**And the numbers looked fine.** 1.74% of the frame reached the deepest level,
22% stayed coarse — a plausible "compact deep islands in a shallow sea". The
**picture** showed the deep cells tracing four enormous diamonds: the
boundaries of the **12 HEALPix base pixels** (confirmed — exactly base pixels
0,1,2,3 fall in this cap, and the refinement follows their edges). Real star
trails did refine, but as faint flecks under a dominant grid artefact.

**Fourth time the eyeball has beaten the numbers here** (foliage run, 08-11
contrail, inverted detector calibration, now this). The visualisation earned its
place on first use, exactly as `--save-cutouts` did.

**Root cause — the ladder was built one step deeper than the data supports:**

| | arcsec |
|---|---|
| nside 2048 cell | 103.1 |
| astrocam pixel, full-res | 74.9 (cell = **1.38×** px — good) |
| astrocam pixel, half-res | 149.8 (cell = **0.69×** px — **finer than the data**) |

Accumulating half-res frames into nside-2048 cells means **every cell is fed by
less than one camera pixel**. Neighbouring cells then disagree from sampling
aliasing, and at base-pixel seams — where two base grids meet at an angle —
that aliasing is worst. The criterion correctly reported "children disagree";
the disagreement simply was not sky.

**So the criterion is not wrong, the input was.** Same lesson as three times
before: measure structure on data still carrying its instrumental signature and
you measure the instrument.

**Fixes, in order:**
1. **Cap N_side at ~1.4× the camera pixel** — nside 2048 for full-res astrocam,
   1024 for half-res. Never build finer than the data; the drizzle supergrid is
   the *separate*, later step that earns sub-pixel cells, and it needs many
   dithered samples per cell to do so.
2. **Render with area-weighted sampling, not nearest-neighbour.** The seam
   artefact is amplified by point-sampling the map back into pixel space.
3. **Then re-evaluate `k`** — it cannot be calibrated until the input is clean.

Counts were healthy throughout (median 38 samples per cell from 20 frames, only
0.1% singletons), so accumulation itself is sound. This is a resolution and
rendering fault, not an accumulation one.

### Run cost — and the host rule

Ran on **pip**, which was the wrong call and Peter said so mid-run: *"we should
really be running this on muppet."* I had priced the read (~196 MB, ~40 s) and
judged it an acceptable one-off. That is re-deriving a settled rule instead of
applying it — STATE already records **compute follows the data**, and *"pip on
wifi is not a compute node, it's my interface to all this."*

Measured: **75/67/87 s per N_side for 20 frames** — most of it NFS read, since
each accumulate re-reads every frame. A full night is ~400 frames (20×), and the
year is ~100×. **The prototype was never a one-off**, which is exactly why the
rule exists.

**Next runs go to muppet** (local NVMe, the frames' own host). Note
`astropy_healpix` must be installed there too — and per
`muppet-interfaces-worn-not-silicon`, use its internal NVMe rather than USB.

**Also worth fixing:** the accumulate loop re-reads every frame once per
N_side. Read once, accumulate into all N_sides in the same pass — or better,
accumulate only at the finest and bin down, which is exact and now proven.

## Second run — on muppet, 2026-08-16. THREE bugs, criterion still not clean.

Moved to muppet (Peter: *"we should really be running this on muppet"*).
`astropy_healpix` 1.0.0 there vs 1.1.2 on pip — the exactness property was
re-verified on the older version before trusting any result. Frames are
**full-res 4608×2592**, so `[1392, 978]` is already the correct full-res pole.
Runtime **98 s** for 20 frames including the direct-rebuild check, reading local
NVMe instead of NFS.

**Bin-down exactness still PASSES** under the stronger test (coarsest rebuilt
directly from frames vs binned from the finest): IDENTICAL, 5,357,354,088.

**My oversampling diagnosis was WRONG.** Re-running at 1.38× px produced a
**byte-identical depth map** to the 0.69× run. Ruled out by measurement:
counts are uniform across base pixels (38.02 each) and
`corr(spread, child-count-imbalance) = -0.002`. Neither sampling ratio nor
depth explains the seams. *Recorded because the first run's writeup asserted it
confidently.*

Three real bugs, each found by instrumenting rather than reasoning:

1. **The noise model was invented, not measured.** `sqrt(mean)/sqrt(N)` on raw
   ADU gave σ=1.56 against a *measured* sibling scatter of 0.71 — 2.2× too
   large. These are co-added frames with gain; **ADU are not photons.** With
   3σ=4.84 against a median spread of 1.51, ordinary sky could never refine, so
   the only features clearing the bar were the abrupt cell-geometry steps at
   base-pixel seams. **The tree traced the grid because the bar was set where
   only the grid could reach it.**
2. **Refinement was not a tree.** Every cell was tested independently at every
   level, so a cell refined even when its parent had stopped. `k=3` and `k=40`
   gave byte-identical maps. Fixed by carrying the parent's decision down.
3. **σ collapsed to zero.** `depth_ref = median(kcnt.min(axis=1))` over ALL
   parents is **0**, because the cap covers ~3% of the sphere and only 94,612
   of 3.1M parents have all four children sampled. σ=0 ⇒ everything splits,
   regardless of `k`. Fixed by computing scatter and reference over judgeable
   cells only.

**`k` now responds monotonically** — 19.3% deep at k=1, 8.1% at k=2, 2.9% at
k=3, 0.13% at k=8.

**Status: partly working, not yet trustworthy.** At k=3 the refinement clearly
traces **concentric arcs about the pole** — real star trails, the first time
the tree has followed sky. But the diamond seam pattern is still faintly
present and refinement is scattered broadly rather than concentrating on
sources. The criterion is finding trails **and** grid.

**Do not tune `k` further until the seam residual is understood.** Three
diagnoses have already been wrong; the next step is to *measure* what
distinguishes seam cells from arc cells (e.g. compare spread distributions for
cells adjacent to a base-pixel boundary against the rest), not to guess a
fourth mechanism. The likely remaining candidate is the **nearest-neighbour
render** in `healpix-view` amplifying cell-to-cell steps — but that is a
hypothesis, not a finding.

## Related

- `accumulation-bucket-refinement.md` — the ring scheme this replaces for
  astrocam; the withdrawn integer shift; count planes.
- `whole-sky-context.md` — why HEALPix, and what MOC/IVOA standards apply.
- `what-accumulation-buys.md` — coarse-to-fine in the question; "the bumps".
- `retrospective-reprocessing.md` — the archive appreciates; raw retention.
- `zenith-quests.md` — Mizar & Alcor, Polaris B: the calibration targets for `k`.
