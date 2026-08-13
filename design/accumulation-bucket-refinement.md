# the map — all-time accumulation by quality buckets, recursively refined

**THE NAME: `map`.** The long-timebase sidereal accumulator is called **the
map**, chosen by Peter 2026-08-13: *"it's a mapping of image space to the
celestial sphere. we know its in astro."*

The word is meant in its **mathematical** sense — a mapping from image space to
the celestial sphere — not in the "picture of a place" sense. That is precisely
what the accumulator is: every frame from every camera and every epoch is
*mapped* onto one sidereal coordinate system and summed there. It is the same
sense as the remap in `hierarchical-vector-field.md`.

Rejected, and why (the reasoning is worth keeping, because names get
re-litigated): `astromap`/`astrochart` — redundant, everything here is already
astro, and *astrochart* collides with astrology; `chart` — evokes sailors and
superstition, and a chart is a *finding aid*, not accumulated photons;
`starsum`/`starchart` — narrows to stars, but `what-accumulation-buys.md` shows
the payoff is *structure* (PSF bumps, companions, wobble) plus anything
extended; `atlas`/`skyatlas` — good, but `atlas` is heavily overloaded in
computing; `coadd` — accurate survey jargon but names the operation, not the
thing. **`map` also retires the placeholder "the thrust"**, which named nothing.

Paths follow: `<instrument>/map/`, `/astro/map`. Derived vocabulary: a **map
tile** (one cell of the sky grid), **map depth** (total integrated exposure at a
point), a **contributing night** (one admitted to the map).

### There is not ONE map — there is a map per PROJECTION

Peter, 2026-08-13: *"there are multiple mappings or projections. polecam does
not easily map onto the celestial sphere so we might use a different projection
for that. it would be good for eclipticam."* Correct, and the geometry forces
it. STATE's accumulation theory already anticipated this — *"Polar coords about
the pole for astrocam/polecam; curved bands for eclipticam's 102° field"* — but
the naming above assumed a single map, which is wrong.

| Instrument | Projection | Why |
|---|---|---|
| **polecam** | **polar / azimuthal about the celestial pole** | It stares at the pole, which is a *coordinate singularity* in RA/Dec: meridians converge, RA is meaningless there, any equatorial grid degenerates. But the sky **rotates about that point**, so a star sits at constant radius and only its angle advances. Polar coords are not a workaround — they are the frame the data is already in, and they make the sidereal shift a pure rotation in one coordinate. |
| **eclipticam** | **ecliptic-aligned curved bands** | A 102° field cannot use one tangent plane: gnomonic projection diverges long before that. Bands aligned to the ecliptic match what the camera is actually pointed along, and keep distortion bounded across the field. |
| **astrocam / canon** | polar about the pole (astrocam), TBD for canon | astrocam per STATE. canon's pole and plate scale are both **UNSOLVED** (`pole_prior_xy: null`), so its projection cannot be chosen yet — see the calibration by-product below. |

**Consequences for the design:**

- **The projection is a property of the instrument's geometry, not a global
  choice.** It belongs in `camera.json` beside `plate_scale` and `pole_prior_xy`
  — the same calibration-epoch family, and therefore also **epoch-bounded**: an
  epoch change can change the projection.
- **`<instrument>/map/` is already the right shape** — each instrument's map
  lives in its own tree and carries its own projection. Nothing to rename.
- **Combining instruments happens on a common sphere, late.** Per-instrument
  maps accumulate in their native projection (where shifts are cheap and
  distortion is bounded); cross-instrument combination re-projects onto a shared
  frame only at the end. This is the same discipline as epochs: accumulate in
  the native frame, combine only where the frames are commensurable.
- **Record the projection in the map's own metadata**, so a map file is
  self-describing and cannot be silently misread — the same reasoning that put
  `POSINDEX` in every frame.

Note "map" is unqualified here; existing masks keep their qualifiers
(*occlusion map*, *hot-pixel map*) and do not collide.

---


**Accumulate the ENTIRE archive, but not as one undifferentiated sum. Sort
frames into quality buckets, accumulate best-first, and use each accumulation
to re-judge the frames — the sum becomes the reference that grades its own
inputs, so the buckets improve on every pass.**

Peter, 2026-08-13: *"I want to start accumulation over the entire data set.
bucket sorting the quality of the data and recursively refining it."* Noted as
needing coordination with **astro-storage** (it owns the bytes; this strand owns
the method).

## What this adds to what is already designed

Two layers exist and are not this:

- `what-accumulation-buys.md` + STATE's **capacity law / TDI** settle *how* to
  accumulate: remap-then-shift, drizzle onto a finer grid, CFA planes never
  demosaiced. Output is small — ~400–700 MB **total forever** per instrument,
  per-night marginal cost ≈ 0.
- `accumulator-outlier-rejection.md` settles *per-sample* robustness: once
  de-rotation has turned each sphere cell into a time series, a cloud/plane/
  meteor sample is a temporal outlier **within that cell** and is rejected or
  down-weighted there.

Neither answers **frame-level admission**: of ~62 astrocam nights (606 GB) plus
canon (97 GB), which frames should enter the sum at all, in what order, and
with what weight? Per-cell rejection is a scalpel — it cannot save a frame that
is globally fogged, defocused, or trailed by wind. Feeding those in and letting
the scalpel work is both wasteful (they are read, remapped, then mostly
discarded) and harmful (they inflate the per-cell variance that rejection
thresholds are derived from).

## Why bucketing, specifically

The archive's quality is **wildly non-uniform** and the variation is
*measurable before accumulation*:

- cloud (the existing `verdict` + `sky_clear_max_stops` machinery already
  scores this per night and per 10-min anchor);
- focus (astrocam epoch 2 dithers `LENSPOS` 1.3–1.6 deliberately — some frames
  are known-sharper by construction; canon is by-eye MF at "marker 0");
- moon (a bright moon raises the floor across the whole frame);
- capture continuity (2026-08-12 had six >90 s gaps — see the inch-worm
  finding; a pass boundary or a wedge recovery brackets frames taken while the
  camera was settling);
- **epoch** (the hard one — see below).

A single all-time sum weights a fogged, moonlit, defocused frame the same as a
pristine one. The capacity law says the deep sum is information-rich enough
that the *marginal* faint star is exactly what we are chasing; that faint limit
is set by the WORST frames admitted, not the best.

## The buckets

Grade each frame into a tier, cheapest signals first (all derivable from data
already computed per night, no new passes):

| Tier | Meaning | Signals |
|---|---|---|
| **A** | pristine | clear verdict, dark trough, in-focus, no moon, mid-pass (not adjacent to a gap) |
| **B** | good | clear but moonlit, or slightly off best focus |
| **C** | usable | thin cloud, dawn/dusk twilight edge, focus dither extremes |
| **D** | suspect | cloud verdict, adjacent to a capture gap or wedge recovery |
| **X** | excluded | saturated, tracking/wind smear, frames during a power-cycle recovery |

Tiers are **per frame**, not per night — a night degrades mid-way and the
existing 10-min anchor already resolves that finely.

## The recursion — why this is not just sorting

Accumulate **A first**, then fold in B, then C. Each accumulation is a
**deeper, cleaner reference than any single frame**, and that reference can
re-grade the archive:

1. **Sum A.** Even a partial A-sum has far better SNR than one frame.
2. **Re-grade every frame against the A-sum.** Now real per-frame quality is
   measurable rather than inferred: register the frame to the sum and measure
   residual, PSF width against the sum's stars, transparency (photometric zero
   point against the sum's own stars), astrometric scatter. These are *direct*
   quality measures; the tier-0 signals (cloud verdict, LENSPOS) were only
   proxies.
3. **Re-bucket.** Frames promote and demote. A frame the proxies called C may
   register beautifully; a nominally clear frame may show a transparency dip
   the verdict missed.
4. **Re-accumulate** with the improved buckets and per-frame weights
   (weight ∝ transparency / variance, the standard inverse-variance form).
5. **Repeat until the bucket assignment is stable.** Expect very few passes —
   this converges fast because the sum is dominated by the good frames from
   pass 1.

This is self-bootstrapping: the sum grades the frames, better frames make a
better sum. It also **produces the calibration the estate lacks** as a
by-product — canon's `plate_scale_deg_px` and `pole_prior_xy` are both `null`,
and registering frames against a deep sum is exactly how to solve them.

## Epochs are bucket boundaries, not obstacles

Peter: *"we can work out the epochs from the images."* Confirmed — the epoch is
unambiguous per frame from sensor + resolution + Bayer, and the astrocam
boundary is sharp (2026-07-28 imx219/3280×2464/BGGR → 2026-07-29
imx708/4608×2592/RGGB). `POSINDEX` exists only from epoch 2 onward, so **derive
the epoch from the image, do not trust the header to be present** (76% of the
astrocam archive is epoch-1 and unstamped).

An epoch change means different plate scale, pole, FOV, orientation, pedestal.
So:

- accumulate **per epoch into its own accumulator** — never co-add across a
  boundary in sensor coordinates;
- combine epochs **only on the sky grid**, after each epoch's own remap, where
  they are commensurable;
- this is a feature: epoch 1 is 47 nights (76%) of astrocam and must not be
  thrown away just because the camera changed. Two epochs registered onto one
  sky grid is a *deeper* result than either alone.

## Coordination with astro-storage

This strand owns the method; **astro-storage owns the bytes and must be
consulted before any all-time pass**. The constraints that matter:

- **Reading 703 GB repeatedly is the cost**, not storing the output (the
  accumulator is MB-scale by the capacity law). A recursive scheme that
  re-reads the archive per pass multiplies that.
  → Mitigation: compute per-frame quality metrics **once**, in a single pass,
  into a small sidecar table (one row per frame). Recursion then re-grades and
  re-weights from the *table*, and only re-reads pixels when actually summing.
- **Compute follows the data** (house rule): this runs on muppet where the
  frames are, never over the wifi mount from pip.
- muppet is ONE SMART-blind copy (`redundancy-not-capacity`) — an all-time read
  pass is a good moment to notice unreadable frames; log them, do not silently
  skip them.
- the accumulator output is small and precious: it is a derived product that
  took the whole archive to make. It belongs in the backed-up set, not in
  scratch.

## astro-storage's answers (2026-08-13) — binding constraints

Asked; answered. These are not suggestions:

- **A sustained multi-hour full-archive read on muppet is approved**, no window
  needed — nothing else contends but `canon-nightly` at ~06:05 BST. Two
  conditions:
  - **`nice -19` / `ionice -c3`.** muppet NFS-exports the tree to the whole
    192.168.0.0/24; an unthrottled pass is felt by every host reading over NFS.
  - **The pass MUST be resumable, checkpointed per night.** bigstore is
    USB-attached, and muppet's failure mode is *physical interfaces, not
    silicon* — a multi-hour saturating read is exactly the load that surfaces a
    marginal cable. A mid-pass USB reset must cost one night, not the run.
- **Log bad reads as an archive-wide scrub — requested, not merely permitted.**
  This is the part astro-storage values most. Rationale earned the same day:
  **2026-05-27 (40 GB starcam) is GONE** — on no online disk anywhere, recorded
  as present since 2026-06-13, and nothing noticed for over two months. bigstore
  is also **SMART-blind** (the Seagate Expansion bridge blocks ATA pass-through),
  so there is no pending-sector warning; the first symptom is data loss. This
  pass would be the first archive-wide integrity check the estate has ever had.
  Log **path, night, camera, error, bytes-read-before-failure**, emit as a file
  that diffs between runs. **Do not repair or quarantine — log and carry on.**
- **Output location: `/mnt/bigstore/astro-data/<instrument>/map/`** (agreed with
  astro-storage as `…/accumulator/` before the artefact was named; the
  convention is theirs, the spelling is the rename — confirm with them) —
  inside the tree being accumulated from, so it inherits the path conventions,
  the storage-report scan, and the backup story. Give it a `MANIFEST.sha256`
  like the night dirs, **re-emitted whenever the accumulator is rewritten**, so
  `cold-archive-night` can take it. It is the "irreplaceable, tiny" class:
  400–700 MB that costs the whole archive to regenerate.
  The **sidecar quality table goes in the same tree but is DERIVED** — mark it
  regenerable so nobody pays to replicate it. (If it turns out to cost many
  hours to rebuild, say so and it gets reclassified.)
- **Do not touch:**
  - starcam **2026-05-21** and **2026-05-23** (40 GB each) — bigstore-only,
    single copies, unsquashed raw. Reading is safe; never move, rewrite or clean.
  - **2026-07-04 eclipticam-v3w exists ONLY in Deep Archive** — do not read it.
    A restore costs money and takes hours. **Skip it and note the gap.**
  - `/mnt/bigdisk` (97% full) and `/mnt/bigdisk2` (93%) — reads fine, **no
    writes**.
  - `/mnt/astrobackup` — a manually-mounted USB stick with no fstab entry; it
    may vanish mid-pass. Ignore it.
  - `/mnt/bigstore/astro-data/_non-astro/`.

**Caveat carried over:** "on bigstore" is **not** "backed up" — bigstore is one
SMART-blind copy (`redundancy-not-capacity`).

### Tree shapes — FOUR, and do not hand-roll a resolver

Confirmed by astro-storage 2026-08-13 and verified against disk:

Durable copy of the layout survey:
`strands/astro-storage/for-astro-science-tree-shapes.md`.

| Camera | Layout |
|---|---|
| astrocam | **`astrocam-frames/YYYY-MM-DD/` (FLAT)** — this is where the 606 GB is |
| eclipticam | `eclipticam-frames/night/YYYY-MM-DD/v3w/` |
| starcam | `starcam-frames/night/YYYY-MM-DD/`, hour dirs **either** raw `HH`+`HHb` **or** squashed `HH-sum8`+`HHb-sum2` |
| eos / canon | `eos-frames/YYYY-MM-DD/`, `canon-frames/YYYY-MM-DD/HH/HH-MM-SS.fits.fz` (plus `eos-frames-live/` = live preview JPEGs, low value, probably skip) |

**Three walk hazards — all verified against disk 2026-08-13:**

1. **astrocam has TWO coexisting layouts.** The flat `YYYY-MM-DD/` tree holds
   the real data (2026-08-12: 4.6 GB, **434 FITS**). A nested
   `astrocam-frames/YYYY/MM/DD/astrocam/` tree also exists but is **metadata
   only** — 748 KB total, **zero FITS**, just `brightness.csv` + `state.json`.
   A naive date-dir glob matches **both** and will double-count or silently
   pick the empty one. (This doc briefly recorded the nested form as *the*
   astrocam layout — it is not.)
2. **`astrocam-frames/latest-astrocam` is a symlink OFF bigstore** into
   `/home/peter/astrocam-frames/<date>`. **Do not follow symlinks in the walk**
   or the pass leaves the archive, re-reads counted data, and may wander onto
   another disk.
3. **Date dirs mix hour dirs with product dirs and loose files.** canon
   2026-08-12 has `00 01 02 03 20 21 22 23` beside `badpixel.fits`,
   `brightness.csv/png`, `max.fits.fz`, `sweep-*/`… → **filter children to
   two-digit names**. eclipticam likewise has `moon/`, `sweep-colour/`,
   `sweep-diff/` beside `v3w/` → **take `v3w` explicitly, never glob `*/`**.
4. **NEVER ingest night-level FITS — they are DERIVED, and one of them is an
   accumulation.** This is the two-digit filter with teeth. Measured on
   astrocam 2026-08-13:

   | Depth | What | Count |
   |---|---|---|
   | 3 (inside `HH/`) | **real captures** | **88,415** |
   | 2 (night level) | `sum.fits.fz` ×57, `min` ×57, `max` ×57, `badpixel.fits` ×57, `derot.fits.fz` ×3 | 231 |

   **`sum.fits.fz` is an already-accumulated night stack.** Ingest it as a
   frame and the pass accumulates an accumulation — a whole night's photons in
   one object, silently biasing every bucket it lands in. `max`/`min` are
   extrema, not exposures; `badpixel` is a mask.

   A plain `find -name '*.fits.fz'` returns **88,589** = 88,415 captures **+
   174 derived** — this doc's own first count made exactly that mistake, and it
   is invisible without the depth breakdown (the arithmetic still "looks
   plausible"). **Rule: take FITS only from depth 3, under two-digit-named
   children. Everything at the night level is derived — skip it.**

**Known-empty night:** `astrocam-frames/2026-06-08` is an empty directory stub
(zero entries of any kind). astrocam is **61 populated + 1 empty = 62 dirs**.
astro-storage is recording it in the inventory as known-empty so
`inventory-drift` will not later flag it as drift. The metrics pass should log
it as a zero-frame night and carry on.

**Use `astro/bin/astro-where <camera> <night>`** — it resolves (camera, night)
across every root and layout, so a fifth hand-rolled resolver inherits nothing
and rots. Verified working for all four shapes. **Pass the FULL camera name**:
`eclipticam-v3w`, not `eclipticam` (the bare name resolves nothing — an easy
false "the tool is broken" conclusion).

**Run `astro/bin/inventory-drift` BEFORE any multi-hour pass.** It stats every
inventory row against disk and exits 1 on drift, so a dead path costs 30 seconds
instead of surfacing three hours in. Verified 2026-08-13: 35 rows, 32 ok, 0
missing, 0 size-drift, 3 skipped (two Deep Archive, one known-missing).

**The inventory was rotten until today** (`astro f6736fc`, 22 → 35 rows): it
asserted a squashed 2026-05-21 at a `/mnt/bigdisk` path that does not exist,
omitted **nine** bigstore copies entirely, and pointed 2026-05-23 at puppy after
it had moved. Anything reading `whereisallthedata.csv` to enumerate nights must
re-read the new one.

**Squash is DORMANT** (Peter's call, 2026-08-13: *"we don't do squashes much now
— because we have more storage"*). The pressure that justified it (bigdisk 97%,
bigdisk2 93%) went away when streams moved to bigstore (27% used). So **raw
`HH`/`HHb` and squashed `HH-sum8`/`HHb-sum2` both persist indefinitely** — the
metrics pass must treat both as a permanent condition, not a transitional one,
and the frame count being budgeted against will not shrink.

### "Backed up" — nothing here is, yet

astro-storage closed the caveat explicitly: putting the accumulator on bigstore
makes it **conventional, not safe**. bigstore is ONE copy and SMART-blind, so
the first symptom of decay is data loss. **Right now nothing in this estate is
genuinely backed up except what has reached Deep Archive.**

Practical consequence: emit the `MANIFEST.sha256` as agreed, and treat the
accumulator as a **cold-archive candidate**. When there is a stable version
worth keeping, tell astro-storage and they will run it through
`cold-archive-night` to Deep Archive. At 400–700 MB that is pennies, and it is
the one artefact whose regeneration cost (a full 703 GB re-read) massively
exceeds its storage cost. **Do not consider it safe until that has happened.**

## Scratch runs — start low-resolution (Peter, 2026-08-13)

*"We should start doing scratch runs. low resolution accumulations. coarse
buckets for sorting good pixels from bad."*

The theory is settled; the **plumbing** is not, and every error this project has
hit has been in the plumbing — a night-level `sum.fits.fz` counted as a frame, a
nested metadata tree mistaken for the data, a threshold guessed from three
frames that scored 1/38 against ground truth. A decimated pass exercises the
walk, the epoch split, the derived-product exclusion and the bucket logic at
1/64 of the pixels, so a mistake costs minutes.

**Measured read costs (muppet, local disk, 2026-08-13):**

| Method | Per frame | 88,415 frames |
|---|---|---|
| pip, over the wifi mount | 1.65 s | ~40 h |
| muppet, full read | 0.15 s | ~3.7 h |
| muppet, `.section[::8,::8]` | **0.09 s** | **~2.2 h** |
| header only | 0.002 s | ~3 min |

An 11× penalty for reading over wifi — *compute follows the data*, quantified.
Use `hdu.section[::8,::8]`: it reads a strided slice **without materialising the
full array**, so decimation saves TIME, not just memory. (Decimating after a
full read saves nothing — the cost is decompression.)

A full-archive scratch pass is therefore a **single-digit-hours** job.

### First scratch result — metrics are NOT comparable across epochs

Three nights × 20 frames, both epochs, 0 bad reads:

| Night | Epoch | median | contrast |
|---|---|---|---|
| 2026-06-10 | 1 (imx219, 3280×2464, BGGR) | **518** | 4.2 |
| 2026-07-28 | 1 | **516** | 3.8 |
| 2026-08-12 | 2 (imx708, 4608×2592, RGGB) | **78** | 2.2 |

Two things confirmed, one hazard found:

- **Epoch is derivable from the image** — sensor + resolution + Bayer separate
  cleanly, and epoch-1 frames show `POSINDEX = none`, so the header genuinely
  cannot be relied on.
- **HAZARD: a raw threshold on `median` would bucket by CAMERA, not by
  QUALITY.** The 518 → 78 drop is not a darker sky; it is a different sensor
  with a different pedestal (registry: epoch 1 = 512, epoch 2 = 50). Any
  absolute cut would put every epoch-1 frame in one bucket and every epoch-2
  frame in another — a plausible-looking number measuring the wrong thing, the
  same failure shape as the delivery bug and the `sum.fits.fz` miscount.
- **Therefore: bucket thresholds must be derived PER EPOCH**, or the metrics
  normalised to their epoch's pedestal (the `log2(mean/pedestal)` "stops" axis
  the brightness charts already use) before any cut is applied. Percentile-
  within-epoch is the safer default: it cannot be fooled by a pedestal change.

## FFTs, and where the bottleneck actually is

Peter, 2026-08-13: *"I think ultimately we will be doing FFTs … to transform
subpixels to the accumulation. Those will take some CPU so I think the network
might become less significant."*

**Answering the direct question: no, FFTs have not been discussed before for the
map.** The only prior mention anywhere is FFT phase-correlation in
`speaker-dither-rig.md`, an unrelated subsystem. The sub-pixel path on record is
**drizzle** (`what-accumulation-buys.md`, STATE accumulation theory), chosen
because naive interpolation aliases on undersampled data.

So this is a genuinely new direction, and it is a real alternative: Fourier
shifting applies a sub-pixel translation as a **phase ramp**, which is exact for
band-limited data and has no interpolation kernel to smear the PSF. That is
attractive precisely where drizzle is fiddly. The open question is whether the
data is band-limited enough — the archive is *undersampled* (that is why drizzle
was chosen), and Fourier shifting an aliased signal moves the aliases too.

**MEASURED, muppet, 2026-08-13 — the CPU premise does not hold:**

| Stage | Per frame (4608×2592) |
|---|---|
| read + decompress, local disk | **0.09–0.15 s** |
| `numpy.fft.rfft2` | 0.18 s |
| **`scipy.fft.rfft2(workers=-1)`** (8 cores) | **0.01 s** |
| `irfft2` | ~0.02 s |

A multithreaded forward+inverse round trip is **~0.03 s against 0.09–0.15 s of
I/O** — so even with FFTs in the loop, **I/O still dominates by roughly 3–10×**,
and the network/storage path stays the thing to optimise. (Use `scipy.fft` with
`workers=-1`, not `numpy.fft`: 18× on the same machine and the same array.)

This does not argue against FFTs — it argues that adding them **does not change
where the pressure is**, so the SSD-staging idea below is worth doing on its own
merits rather than as CPU-hiding.

### Staging to a fast local SSD

Peter: *"we might be transferring to a fast local SSD whilst a batch is being
processed. we will defo not be processing on pip."*

Agreed on pip, emphatically — measured 11× penalty over the wifi mount. On
staging: the shape is right (overlap transfer of batch N+1 with compute on batch
N, so reads are hidden behind work), but note the measurement above means there
is **not much compute to hide behind** yet. Staging pays when either:
  - the accumulation per frame grows well past ~0.1 s (deeper per-frame work,
    drizzle onto a fine grid, multiple projections per frame), **or**
  - the source is slower than muppet's local disk (bigstore is USB, and
    astro-storage warns a sustained saturating read is exactly what surfaces a
    marginal cable — a staged copy is also *gentler* on that interface).
Both are plausible; neither is established. **Measure before building it** —
this doc's own history is a series of plausible premises that measurement
inverted.

## The coarse accumulation buffer

Peter: *"we probably need to design the coarse accumulation buffer."* Yes — and
the scratch pass is what sizes it honestly. Open design points:

- **Dtype — and canon is the case that bites.** Per
  `nit-accumulator-is-not-a-cache` the accumulator is a **non-volatile int32**
  structure tiled to RAM/L3, not a cache and not RAM-resident. Computed at
  88,415 frames:

  | Source | Max possible sum | int32 headroom |
  |---|---|---|
  | 10-bit Pi sensors (imx219/imx708) | 9.0e7 | **23.7×** — comfortable |
  | **14-bit canon** | **1.45e9** | **1.5×** — thin |

  So int32 is fine for the Pi cameras but **canon has almost no margin**: a
  longer baseline, a brighter sky, or any pre-scaling overflows it. Either
  accumulate canon in **int64**, or subtract the pedestal before summing (canon's
  pedestal is 2048 of a 16383 full scale — removing it recovers most of the
  range). Decide per instrument; do not assume one dtype fits the estate.
  **float32 is unusable regardless**: its 24-bit mantissa (1.68e7) loses integer
  exactness after only **~16,400 frames** at full scale, well inside a single
  instrument's archive. **int32/int64, never float32.**
- **Coarse first.** At `[::8,::8]` a frame is 324×576. A coarse map at that
  scale is ~0.75 MB per plane — trivially RAM-resident, so the whole
  bucket/projection/epoch pipeline can be exercised end-to-end before any
  tiling machinery exists. That is the point of coarse: **make the plumbing
  cheap enough to be wrong repeatedly.**
- **Per CFA plane, never demosaiced** (STATE: "the Earth demosaics") — so four
  half-res planes, or shift by the 2×2 CFA period.
- **Counts alongside sums.** Every cell needs its own contributing-frame count
  (coverage is not uniform: gaps, cloud rejection, bucket admission all vary per
  cell), else depth cannot be normalised and `map depth` is unmeasurable.
- **Sizing follows the projection**, which is per-instrument — so there is a
  coarse buffer per instrument, not one shared array.

### Polar buffer vs south buffer — separate, and the south one is EMPTY

Peter, 2026-08-13: *"we are thinking about the max size the polar buffer needs
to be and the south buffer. I think they are separate."* They are separate, and
for a stronger reason than organisation. **Site latitude is 51.3948°N
(Surbiton, `location.json`)**, which partitions the sphere into three regions
with genuinely different accumulation regimes:

| Region | Dec | Sky | Regime |
|---|---|---|---|
| **Circumpolar cap** | > +38.61° | 7,757 sq° (**18.8%**) | **Never sets** — 24 h/day available, every clear night, no seasonal gap |
| **Transit band** | −38.61° … +38.61° | **62.4%** | Rises and sets; availability varies 24 h → 0 h with dec, and seasonally |
| **South cap** | < −38.61° | **18.8%** | **Never rises — permanently invisible from this site** |

Hours above horizon by declination (`cos H = −tan φ tan δ`):

| Dec | +90 | +50 | +38.6 | +30 | 0 | −20 | −38.6 |
|---|---|---|---|---|---|---|---|
| h/day | 24 | 24 | 24 | 18.2 | 12 | 8.4 | **0** |

**Consequences:**

1. **There should be no south buffer.** 18.8% of the sphere never clears the
   horizon from 51.39°N. Allocating for it stores guaranteed zeros. (If the
   estate ever travels, that is a *new site*, not a bigger buffer.)
2. **The real split is circumpolar vs transit, not north vs south.** They differ
   in the natural coordinate (polar (r,θ) about the NCP vs RA/Dec bands), in
   how the sidereal shift acts (a **rotation at constant radius** vs a
   **translation along RA**), and in how depth accrues (uniform vs seasonal).
   That is three good reasons for separate buffers with separate code paths.
3. **Depth is wildly non-uniform across the map** — 24 h/day at the pole, 8.4 h
   at dec −20°. The per-cell **count planes are not optional**: without them
   `map depth` is unmeasurable and the two regions cannot be compared.

**Coarse polar buffer sizing** (astrocam, plate scale 0.0207 °/px, full
circumpolar cap radius 51.39°, int32, 4 CFA sum planes + 4 count planes):

| Resolution | Edge | One plane | 4 sums + 4 counts |
|---|---|---|---|
| **coarse `[::8]`** | 620 px | 1.5 MB | **12.3 MB** |
| `[::4]` | 1,241 px | 6.2 MB | 49.3 MB |
| native | 4,965 px | 98.6 MB | 789 MB |
| 2× drizzle | 9,931 px | 394 MB | 3.2 GB |

So the **coarse polar buffer is ~12 MB — trivially RAM-resident**, and even the
native buffer at 789 MB fits in muppet's memory. Only the drizzled buffer needs
the tiling that `nit-accumulator-is-not-a-cache` describes. This is why coarse
comes first: the entire polar pipeline can be exercised end-to-end in RAM.

Store the cap in **polar (r, θ)** rather than a square array: a cap is a disk,
so a bounding square wastes 1 − π/4 ≈ **21%**, and (r, θ) additionally makes the
sidereal shift a pure index-shift along θ.

### 24-bit: measured, and NOT worth it

Peter, 2026-08-13: *"we might use 24 bit integers."* Tested rather than assumed.
**numpy has no `int24`** — it must be packed as 3×`uint8` and unpacked on every
access, which defeats SIMD. Measured on a 2000×2000 accumulate:

| Accumulator | Per frame | 88,415 frames |
|---|---|---|
| `uint32` | 3.6 ms | **5.3 min** |
| packed 24-bit | 59.4 ms (**16.6× slower**) | **87.5 min** |

So 24-bit costs **~82 extra minutes of CPU to save 3 MB** on the coarse buffer
(25% of 12 MB). Even at native resolution it saves ~200 MB for hours of CPU.
**Use `uint32`/`int32`.** The dtype question that *does* matter is canon's
14-bit headroom (see above), not the width of the Pi-camera accumulator.

### Different depths for I and chrominance — YES, this one pays

Peter, same message: *"maybe different depths I = R + G + B and the
chrominance."* This is the better idea, and it is physically justified rather
than a storage trick:

- **Luminance carries the faint-detection signal.** Summing all four CFA
  positions into one I plane gains ~2× SNR over any single colour plane and is
  what sets the faint limit — the map's headline result.
- **Chrominance is low-spatial-frequency and low-priority.** Colour varies
  slowly across a star field, is not what detects a faint source, and the drift
  already sweeps each sky point across R/G/B pixels (STATE: *"the Earth
  demosaics"*), so chroma fills in without needing full resolution or full
  depth.

| Scheme | Coarse | Native |
|---|---|---|
| **A**: 4 CFA sums + 4 counts, all full depth | 12.3 MB | 789 MB |
| **B**: deep I + 2 chroma at half linear res + 1 count | **3.8 MB (31%)** | **247 MB (saves 542 MB)** |

Scheme B is the one to build, and the saving grows with resolution — at 2×
drizzle it is the difference between ~3.2 GB and ~1 GB per instrument.

**Caveats to settle when implementing:**
- Keep chroma as **difference planes** (e.g. R−I, B−I) rather than raw R and B,
  so the deep I plane carries the precision and chroma stays small-valued —
  which also means chroma may genuinely fit in `int16`, a real saving where
  24-bit was not.
- **The count plane must follow I**, since I is what depth is measured against.
  Chroma at half resolution needs its own count only if its rejection differs.
- Do **not** demosaic to form I. Sum the CFA positions that land in the same
  sky cell; that is a sum of measurements, not an interpolation.

## Open questions

- Bucket thresholds are unset — derive from the data, not by guess. (The
  meteor-detector session on 2026-08-13 is the cautionary tale: a threshold
  guessed from three frames scored 1/38 against real ground truth.)
- Does re-grading against the sum need the sum to be *complete*, or is a
  partial A-sum enough to bootstrap? Probably partial — test it.
- Interaction with outlier rejection: bucket weighting and per-cell rejection
  must not double-count the same contaminant.
