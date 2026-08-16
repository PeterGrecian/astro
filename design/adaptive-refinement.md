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

## Related

- `accumulation-bucket-refinement.md` — the ring scheme this replaces for
  astrocam; the withdrawn integer shift; count planes.
- `whole-sky-context.md` — why HEALPix, and what MOC/IVOA standards apply.
- `what-accumulation-buys.md` — coarse-to-fine in the question; "the bumps".
- `retrospective-reprocessing.md` — the archive appreciates; raw retention.
- `zenith-quests.md` — Mizar & Alcor, Polaris B: the calibration targets for `k`.
