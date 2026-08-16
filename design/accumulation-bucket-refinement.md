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

### The eclipticam (transit-band) buffer — sizing the other shape

Peter, 2026-08-13: *"the sample buffer for eclipticam needs to be the height of
the frame × subpixels² × width × duration factor — probably 4 in mid winter."*

That is the right decomposition for the **transit-band** buffer, and it differs
from the polar buffer because the sky *translates* through this field rather
than rotating within it. Working it with real numbers (v3w, 4608×2592, full-res
plate scale **102°/4608 = 0.02214 °/px**, vertical field **57.4°**):

**The duration factor, checked against the site's actual winter:**

| Coverage | RA swept | × frame width |
|---|---|---|
| One midwinter night, astronomical dark (12.0 h) | 102° + 180° = 282° | **2.76** |
| One night to nautical twilight (10.6 h) | 261° | 2.56 |
| **Full 360° RA circle (all seasons)** | 360° | **3.53** |
| **Peter's factor 4** | 408° | **4.0 — the circle + 13% margin** |

So **4 is sound as a maximum**, and the reason is better than "a long winter
night": at 3.53 the buffer spans the **entire RA circle**, so it *wraps* rather
than growing — one night's 2.76 is a subset of a structure that is complete at
~3.53. **Size for the circle, not for a night.** (Midsummer is the degenerate
case: at 51.39°N there is **no astronomical darkness at all** in June, so the
winter night is genuinely the sizing case for a single session.)

**Buffer sizes**, `H × subpix² × W × duration`, int32:

| Subpixels | Duration | Cells | int32 |
|---|---|---|---|
| 1 | 1 | 1.19e7 | 0.05 GB |
| 1 | 4 | 4.78e7 | 0.19 GB |
| 2 | 4 | 1.91e8 | **0.76 GB** |
| 3 | 4 | 4.30e8 | 1.72 GB |

With the deep-I + shallow-chroma scheme (31%), the 2× subpixel full-circle
buffer is **~0.24 GB** — comfortably RAM-resident on muppet. Even 3× subpixel
fits.

**Two cautions on the arithmetic:**

- **`subpix²` is right only if sub-pixel resolution is wanted in BOTH axes.**
  STATE's sub-pixel analysis says the two axes are not symmetric: along-drift
  super-resolution is nearly free (a continuous pixel-phase sweep, centroids
  ~0.1 px) while cross-drift is deblend-limited (~FWHM/√SNR). So `subpix_x²`
  may be justified where `subpix_y²` is not — an asymmetric grid (fine in RA,
  coarse in Dec) buys most of the resolution for half the memory.
- **Watch the plate scale.** `camera.json` records `plate_scale_deg_px: 0.0443`,
  which is the **half-res capture mode** value; full-res is 0.02214. Sizing off
  the wrong one is a factor-of-2 error in each axis — 4× in the buffer.

### What the map IS: a projection onto the sphere, and its extent is a circle

Peter, 2026-08-13, correcting the framing below: *"we don't store in polar
coordinates, but a projection onto the celestial sphere — a map. Because the
earth rotates so does the image so the maximum extent of the map is a circle"*
— and, on sizing: *"if it was night 24 hours"*.

**Two corrections to the section that follows.**

1. **Storage is a projection onto the sphere, not a polar-coordinate array.**
   (r, θ) is a *shift mechanism* — the fact that sidereal rotation is cheap in
   pole-centred coordinates. It is not the storage model. The map is a
   projection of the celestial sphere; the ring analysis below applies to how
   that projection is *sampled and shifted*, not to what the map is.

2. **The map's maximum extent is set by the 24-hour sweep.** The camera is
   fixed; the Earth rotates; so over a full 360° the field sweeps a **pole-
   centred annulus** bounded by the min and max angular distance from the NCP
   that the field reaches. Size for the hypothetical 24-hour night — that is
   the season-independent bound, and it is a *circle* (or annulus), never a
   rectangle.

**Computed per camera** (half-diagonal of the field about its centre's
angular distance from the NCP, then clipped by the horizon — nothing beyond
128.6° from the NCP ever rises at 51.39°N):

| Camera | Field centre from NCP | Swept region | Area |
|---|---|---|---|
| **astrocam** (near the pole) | ~0° | **DISC**, r = 0 … 37.8° | **4,328 sq°** |
| **eclipticam** (wide, ecliptic) | ~88.6° | **ANNULUS**, r = 30.1 … 128.6° | **30,715 sq°** |
| canon | **unsolved** (`pole_prior_xy` null) | cannot be computed yet | — |

So the two cameras' maps are **different shapes**, which is the real reason
they need separate handling:

- **astrocam's map is a disc containing the pole.** Every part of it is covered
  at every rotation phase, so depth accrues uniformly and the sidereal shift is
  a rotation about the disc's own centre.
- **eclipticam's map is a pole-centred annulus**, 98.5° wide in radius and
  clipped at the bottom by the horizon. It is "fairly rectangular" only
  *locally* — unrolled in (radius, angle) it is a band, which is why the
  H × subpix² × W × duration decomposition works for it. Globally it is an
  annulus that wraps in angle.
- **The annulus wraps.** That is the same result the duration-factor analysis
  reached from the other direction: at 3.53× frame width the buffer spans the
  full RA circle and closes on itself. A 24-hour night makes this exact rather
  than approximate.

**eclipticam's map is ~7× the sky area of astrocam's** (30,715 vs 4,328 sq°),
which dominates any per-camera memory comparison and is why its buffer sizing
was the harder question.

**Epochs enlarge the extent — size for the UNION.** Peter: *"the epochs have
different orientations so the max extent will be larger."* Correct, and it is
not a small correction. An epoch boundary is by definition a camera, lens or
mounting change, so each epoch has **both a different field size and a
different aim**. astrocam's own two epochs:

| Epoch | Sensor | FOV | Half-diagonal |
|---|---|---|---|
| 1 (`av2`) | imx219, 3280×2464 @ 0.0190 °/px | 62.3° × 46.8° | **39.0°** |
| 2 (`av3s`) | imx708, 4608×2592 @ 0.0207 °/px | 95.4° × 53.7° | **54.7°** |

The swept radius grows **40%** from the sensor/lens change *alone*, before any
re-aim:

| Extent | Area |
|---|---|
| epoch 1 disc, r ≤ 39.0° | 4,597 sq° |
| epoch 2 disc, r ≤ 54.7° | 8,707 sq° |
| **union** | **8,707 sq° — 89% larger than epoch 1** |
| union if epoch 2 is also re-aimed 10° | 11,812 sq° — **157% larger** |

So:

- **The map's extent is `min(inner radii) … max(outer radii)` over all epochs**,
  not any single epoch's sweep. Sizing from the current epoch alone
  under-allocates, and sizing from the *first* epoch badly under-allocates.
- **This does not license co-adding across epochs in sensor space** — that
  prohibition stands. The union governs the *sphere-side* extent, which is
  where epochs are combined; each epoch still accumulates through its own field
  and projection.
- **A new epoch can enlarge the map.** The structure must be growable in radius
  (or allocated with headroom), because a future camera swap with a wider lens
  extends the outer radius. Recording each epoch's contributing annulus in the
  map's metadata makes this checkable rather than surprising.
- **canon cannot be included yet** — `pole_prior_xy` is null, so neither its
  annulus nor its contribution to the union is computable.

**Instruments probably NEST rather than merely overlap.** Peter: *"eos is
probably a subset of astrocam v3s and so on."* The angular sizes support this —
EOS 2000D field from its APS-C sensor (22.3 × 14.9 mm) at plausible focal
lengths, against astrocam v3s's half-diagonal of 54.7°:

| Lens | EOS FOV | EOS half-diagonal | Inside astrocam v3s? |
|---|---|---|---|
| 18 mm | 63.6° × 45.0° | 38.9° | **yes** |
| 24 mm | 49.8° × 34.5° | 30.3° | yes |
| 35 mm | 35.3° × 24.0° | 21.4° | yes, comfortably |
| 50 mm | 25.1° × 16.9° | 15.2° | yes, a small fraction |

So even at its widest the EOS sweeps a **sub-annulus** of astrocam's. If that
holds, the estate's maps form a **containment hierarchy** — a wide shallow
instrument enclosing narrower deeper ones — which is a strong structural
property worth exploiting:

- **The enclosing map supplies the reference for the enclosed one.** astrocam's
  deep wide map is exactly the reference frame against which canon's unsolved
  `plate_scale`/`pole_prior_xy` can be fitted — the bootstrap's step 5 across
  *instruments* rather than within one.
- **A common sky grid can be shared.** Nested instruments can accumulate onto
  the same projection at different resolutions, making cross-instrument
  combination a resampling between levels rather than an arbitrary reprojection.
- **Multi-camera coincidence is bounded by the intersection**, which for nested
  fields is the *whole* of the inner field — the best case for the transient
  triangulation goal.

**Unverified, and it matters:** containment needs the fields to be *co-pointed*,
not merely smaller. The table shows angular size only. canon's aim is unsolved,
and the one empirical check available today — the 21:20:58 astrocam meteor
against its two simultaneous canon frames — found **no counterpart**, which is
weak evidence *against* full containment at that moment. Treat nesting as a
promising hypothesis to test once canon is solved, not as an established fact.

### Storage per instrument: polar for eclipticam, sparse rows for astrocam

Peter, 2026-08-13: *"polar coordinates will be efficient for eclipticam.
astrocam can use sparse rows. Each row has an x_start value and an x_extent."*

**This is the right split, and it is the opposite of what the section below
assumed.** The deciding property is simple:

> **astrocam CONTAINS the pole; eclipticam does not** (its annulus starts at
> r = 30.1°). The sin r degeneracy that ruins a polar grid only exists where
> r → 0.

**eclipticam → polar (r, θ).** Its swept region is an annulus, and *an annulus
is a rectangle in polar coordinates*: r is a bounded row index (30.1 … 128.6°),
θ wraps 0–360°, and **every cell is real sky — no sparseness at all**. Better,
the sidereal rotation is `+15.041069°/h in θ, identical for every row` — rows
independent, wrapping naturally. (Not an integer index shift — see "the shift is
not an integer anyway" below, and the withdrawn quantisation.)

The cell-area variation that made polar unattractive for a disc is **mild
here**, because the annulus never approaches the pole:

| r | ring circumference | rel. cell area |
|---|---|---|
| 30.1° | 180.5° | 0.50 |
| 90° | 360.0° | 1.00 |
| 128.6° | 281.3° | 0.78 |

Max/min ratio across the whole annulus is only **1.99×** — handled by the
per-cell count planes, no ragged rings needed.

**CORRECTION — the "straight shift" claim above is too strong.** Peter,
2026-08-13: *"I think eclipticam is not uniform or horizontal enough for a
straight shift."* Right, and it separates into two claims that land differently:

- **The sky's MOTION is genuinely uniform in (r, θ).** A star at fixed dec has
  fixed r and its RA advances at the sidereal rate, so *r constant,
  θ += 15.041069°/h* holds for every star regardless of where the camera points.
  That part stands. **Use the sidereal rate, never 15.000°** — the solar figure
  is wrong by 1.55 px/hour at astrocam's rim.
- **But the frame is nowhere near "horizontal" in this grid.** eclipticam's
  field spans **r = 30.1° at its corners to 88.6° at its centre — ~58° of
  radius within a single frame.** A row of sensor pixels crosses many rows of
  the map. The image→(r, θ) transform is strongly curved across a 102° field
  (projection + lens distortion), so a frame is a curved quadrilateral laid
  across the annulus, not a horizontal strip.

**And the shift is not an integer anyway.** At the full-res cell size
(0.02214°), a **59.9 s exposure advances θ by 0.2496° = 11.28 cells**. Not a
whole number — so sub-cell placement is required *per frame* whatever the
storage scheme. `np.roll` was wrong.

**What this changes, and what it does not:**

- ✗ **Not** "one integer index shift, `np.roll` on axis 1." That was wrong.
- ✓ Still true that the annulus is **dense** in (r, θ) — no corner waste, which
  was the original reason to prefer polar here, and it survives intact.
- ✓ Still true that cell-area variation is a mild **1.99×** (vs unbounded for a
  pole-containing disc).
- ✓ The uniform-θ grid **over-samples the annulus ends and under-samples
  r = 90°** by that same 1.99×, since a fixed angular θ step spans
  `ps·sin r` of actual sky.

**The real operation is therefore: project each frame through the stored vector
field onto (r, θ) with sub-cell (drizzle or Fourier-phase) placement.** The
rotation is absorbed into that projection as a θ offset rather than applied as a
separate shift step. This is what `hierarchical-vector-field.md` already
implies — *"identification and accumulation are two uses of one object"* — and
it means **no scheme gets a free shift**; the choice between polar and sparse
rows rests on density and cell uniformity, not on shift cost.

**astrocam → sparse rows.** Its swept region is a disc, which inscribes a square
and wastes the corners. Storing each row as `x_start` + `x_extent` allocates only
the chord inside the circle:

| | Cells |
|---|---|
| bounding square (3652²) | 1.33e7 |
| **sparse rows** | **1.05e7 — 78.5%, saves 21.5%** |
| index overhead (3652 rows × 2 × int32) | 0.029 MB — negligible |

**The trade to be explicit about** — restated after the correction below, since
the original version leaned on a "free shift" that does not exist:

- eclipticam's polar grid: **dense** (no corner waste), cell area varies a mild
  1.99×, cells degenerate nowhere (no r → 0).
- astrocam's sparse rows in a projected plane: **uniform cells**, 21.5% saved
  over the bounding square, at the cost of an explicit index.

**Neither gets a free shift.** Sub-cell placement is required per frame in both
(see the correction below: a 59.9 s exposure advances θ by 11.28 cells, not an
integer), so the rotation is absorbed into the per-frame projection through the
stored vector field rather than applied as a separate step. The choice between
the two schemes therefore rests on **density and cell uniformity**, not on shift
cost. If astrocam's projection proves expensive, the fallback remains polar with
the 24 × 2ⁿ ring quantisation described below, projecting to sparse rows only
for output.

**Both schemes want the same two things:** per-cell count planes (depth is not
inferable from geometry in either), and a self-describing header recording the
scheme, extent and epoch union.

### The polar cap is circular — sparseness, and how to grid it

**SUPERSEDED for astrocam by the section above** (sparse rows), but kept because
it (a) quantifies *why* a polar grid is wrong for a pole-containing disc, and
(b) the 24 × 2ⁿ ring quantisation remains the fallback if astrocam's per-frame
2-D resample proves too expensive.

Peter, 2026-08-13: *"eclipticam is a good example because it's fairly
rectangular. the pole is going to be more circular so we might need to do
something about the sparseness."* Correct, and the sparseness is **not uniform**
— it varies *within* the buffer, which is what makes it awkward.

**The problem.** In a naive (r, θ) grid every ring gets the same number of θ
cells, but a ring's circumference goes as sin r. So sky-area-per-cell shrinks
toward the pole:

| r (deg) | ring circumference | sky area per θ-cell (rel. to rim) |
|---|---|---|
| 1 | 6.3° | **0.022** |
| 10 | 62.5° | 0.222 |
| 30 | 180.0° | 0.640 |
| 51.4 (rim) | 281.3° | 1.000 |

At r = 1° each cell covers **45× less sky** than at the rim. The pole is
massively oversampled — cells there accumulate almost nothing each — while the
rim is undersampled. Depth per cell becomes a function of radius, which
corrupts exactly the comparison the map exists to make.

**Three griddings, counted (astrocam, 0.0207 °/px, cap radius 51.39°). The
cap's true information content is 7,757 sq° / (0.0207)² = 1.81e7 resolution
elements — that is the floor:**

| Scheme | Cells | vs floor |
|---|---|---|
| Naive (r, θ), θ-count set by the rim | 3.37e7 | +86% waste |
| Cartesian square over the disk | 2.47e7 | +36% waste |
| **Equal-area rings** (θ-count ∝ sin r) | **1.81e7** | **+0% — optimal** |

**But equal-area rings break the property polar coordinates were chosen for.**
With a different θ-count per ring, one global integer shift no longer serves the
whole buffer: a 15°/h rotation is 125.8 cells at r=10°, 362.3 at r=30°, 566.2 at
the rim — **fractional in nearly every ring**, so each would need resampling on
every shift. That trades the cheap-shift advantage for the memory saving.

**The fix — quantise ring θ-counts to 24 × 2ⁿ** (the HEALPix idea in its
simplest useful form). Rings still scale ~sin r, but because every count is a
multiple of 24 and 24 divides 360, a **15.000°** rotation is exactly n/24 cells
— an integer in every ring:

| Scheme | Cells | vs floor | Shift |
|---|---|---|---|
| **24 × 2ⁿ quantised rings** | **1.87e7** | **+4%** | integer for 15.000° only |

56% of the naive scheme's memory and within 4% of the theoretical optimum.

**WITHDRAWN 2026-08-16 — the integer-shift justification does not survive.**
The +4% was paid to keep the shift an integer, and that property is worth
nothing here, for two independent reasons:

1. **15.000°/h is the SOLAR rate; the sky turns at the SIDEREAL rate,
   15.041069°/h** (360° / 86164.0905 s). 24 divides 360 for the solar day, and
   the sidereal rate lands on no nice fraction of it. Rounding to the nearest
   cell against true sidereal time leaves ~0.1–0.2 px of residual at the rim
   (bounded, since each frame re-rounds against absolute time — it does not
   accumulate). **Implementing the literal "15°/h" would be a real bug worth
   +1.55 px/hour at the rim, +10.85 px over a 7 h night.**
2. **Sub-pixel is the whole point** (Peter, 2026-08-16: *"we are aiming for
   subpixel resolution so this is not important"*). Even the correct-rate
   rounding error, ~0.24 px at worst at the rim, is larger than the measured
   0.14 px single-frame astrometric precision — so an integer shift would
   quantise away the project's best measurement, position-dependently. And
   resampling error bakes in permanently.

**Drizzle already handles the fractional part** — it is the estate's stated
resampling strategy and fractional offsets are precisely what it is for. So the
integer shift buys cheapness for an operation that is not the bottleneck and
costs accuracy in the one dimension that matters.

**Consequence: prefer pure equal-area rings (θ-count ∝ sin r) at the 1.81e7
floor.** Drop the quantisation and take the 4%. This agrees with the
"Neither gets a free shift" finding above, reached independently on 2026-08-13
from the 11.28-cells-per-exposure measurement; the rate error is a second,
sharper reason for the same conclusion.

**Consequences:**

- **Store rings as a ragged structure** (offset table + flat array), not a 2-D
  array — a rectangular array is what forces the waste.
- **The count planes matter even more here.** With rings of differing θ-counts,
  per-cell depth is not inferable from geometry; it must be recorded.
- **This is why polar and transit buffers are separate code paths**, not just
  separate allocations: eclipticam's rectangular band has a uniform grid and a
  translation shift; the cap has ragged rings and a rotation shift.
- **Near the pole, rings collapse to n = 24 and below.** The innermost degree is
  a handful of cells; at some radius it is simpler to switch to a small
  Cartesian patch. Worth measuring where that crossover sits rather than
  carrying ragged rings all the way to r = 0.

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

## The bootstrap — locate Polaris, accumulate, store the field

Peter, 2026-08-13: *"there's a bootstrapping procedure. locate polaris, and
other bright stars and start accumulating and storing the transformation vector
field."*

This is the **missing assembly** `hierarchical-vector-field.md` names in its
Status section: *"proven in pieces, not yet assembled end-to-end … Missing: the
layered assembly (bright anchors → field → faint read-off → local catalogue) as
a standing loop."* The pieces exist (`solve-field` + Tycho-2 on puppy;
`bin/{solve-detections,fit-pole,fit-geometry,derot-patches,find-candidates}`;
`pipeline-night` as a known-good centre-out bootstrap). What follows is the loop.

**The new element Peter names is STORAGE:** the vector field is not re-derived
per night, it is an **accumulating artefact** that improves as frames arrive —
the same self-bootstrapping shape as the bucket refinement above, applied to
geometry instead of quality.

### The loop

1. **Seed on Polaris.** On astrocam the brightest detection *is* Polaris, and it
   sits where distortion is ~zero — the natural origin. This also fixes the
   polar buffer's centre, so the seed serves both the field and the map.
2. **Bright anchors → SIP field.** `solve-field --tweak-order 3` on the bright,
   catalogued stars gives `pixel → true sky direction` **with distortion**. The
   camera is fixed, so this field is **static per camera per epoch** — measured
   once, refined forever.
3. **Store it.** Persist the field beside the map:
   `<instrument>/map/field/` — versioned, with the epoch it belongs to and the
   nights that contributed. **This is the object the bootstrap builds.**
4. **Accumulate through the stored field.** The map co-adds by resampling
   through exactly this field — *"identification and accumulation are two uses
   of one object"*. No separate resampling map is ever built.
5. **Densify from the accumulation.** The deep map has far better SNR than any
   frame, so more (and fainter) anchors become solvable in it than in a single
   sub. Feed those back into the field; the field tightens; the resampling gets
   better; the map gets deeper. **Iterate.**

### Why this closes the calibration gap

Step 5 is the same recursion as the quality buckets, and it produces the
calibration the estate currently lacks:

- **canon `plate_scale_deg_px` and `pole_prior_xy` are both `null`** — unsolved,
  which is why canon's projection cannot yet be chosen. Registering canon frames
  against a deep map is precisely how they get solved.
- **astrocam's geometry is STALE from the imx219 era** (`plate_scale 0.0190`,
  `pole_prior_xy [1945,1823]` are epoch-1 values still sitting in live config
  while the notes say re-solve). The bootstrap re-derives them for epoch 2 from
  real imx708 sky.

### Known blockers, both on record

- **Occlusion masking is a prerequisite, not a refinement.** The 2026-07-02
  astrocam solve *stalled extending outward on candidate quality —
  foreground/glow cells*. Trees, gutter and skyglow generate false anchors that
  corrupt the field precisely where it is being extended. The occlusion map is
  also epoch-bounded and marked STALE for epoch 2.
- **Needs a clean bright-anchor solve on a real imx708 clear night.** Same
  prerequisite the accumulator has; not yet done.

### Order of work, revised

The bootstrap slots *before* bucketed accumulation, because accumulation
resamples through the field:

    scratch (plumbing, coarse buckets)   <-- bin/map-scratch, DONE first pass
      -> occlusion mask (epoch 2)
      -> bootstrap: Polaris seed -> bright anchors -> stored field
      -> coarse accumulation through the field
      -> recursive refinement (field AND buckets both tighten)

Note the coarse map is useful *before* the field is perfect: a rough field still
co-adds usefully at `[::8]`, and the resulting depth is what makes the next
round of anchors solvable. **Do not wait for a perfect field to start
accumulating** — that is the recursion, not a compromise.

## Stars vs planes, meteors and trees — statistically, not explicitly

Peter, 2026-08-13: *"we need to distinguish stars from planes, meteors, trees
etc. I'm hoping this might be achievable statistically rather than explicitly."*

**It is, and it is already the estate's stated principle** —
`accumulator-outlier-rejection.md`, from the RANSAC work: ***"no need to
classify; stars obey the rotation, everything else doesn't."*** That is the
whole discriminator. It needs **no model of what a plane or a tree is**, only a
model of what a star does, which is the one thing here that is known exactly:
sidereal rotation about the pole at 15.041069°/hour.

Two layers exist and are complementary:

1. **Per-cell temporal clipping** — after de-rotation each sphere cell holds a
   time series; a contaminant is a gross outlier in it. Running (median, MAD),
   clip beyond κ·MAD (κ≈3–5).
2. **RANSAC at the model-fit layer** — throws out whole bad *tracks* from the
   geometry fit rather than bad samples from a cell. Proven on real data
   (2026-07-03: TOL 0.10 px/s → 6 inliers incl. Altair, 5 outliers).

### But the three contaminants are NOT statistically alike

This is the part worth being explicit about, because one of them defeats layer 1:

| Contaminant | Sensor coords | Sphere coords | Killed by |
|---|---|---|---|
| **Meteor** | moves, 1 frame | 1 cell, 1 sample | per-cell clip (trivially — a single huge sample) |
| **Plane / satellite** | moves, few frames | a line of cells, few samples each | per-cell clip |
| **Tree / gutter** | **FIXED, every frame** | **smears to an ARC** | **NOT the per-cell clip — see below** |
| **Hot pixel** | fixed | smears to an arc | mask, then as tree |

**Trees invert the logic.** A meteor is rare and bright — obviously an outlier.
A tree is *persistent and stable in sensor coordinates*: it occupies the same
pixels all night, every night. At that sensor position the time series is
**boringly consistent**, so a naive temporal clip sees a stable value and
concludes it is real. **The clipper defends the tree.**

What separates it is the **frame in which it is stationary**:

- a **star** is fixed on the **sphere** and moves across the **sensor**;
- a **tree** is fixed on the **sensor** and therefore *moves* on the **sphere* —
  de-rotation smears it into an **arc** at constant radius from the pole.

So the statistic that catches trees is not "is this sample an outlier in its
cell" but **"is this cell's brightness correlated with sidereal phase?"** A tree
contributes to a given sphere cell only when the sky has rotated it there — its
samples cluster at a particular *time of night* and drift by ~4 minutes/day
across the year. A real star contributes at **all** sidereal phases. That is a
clean, purely statistical test requiring no tree model:

- **per-cell sidereal-phase distribution.** Star: uniform over the phases the
  cell was observable. Tree: concentrated, and systematically drifting with the
  sidereal day.
- **per-sensor-pixel persistence.** A pixel that is bright in *every* frame
  regardless of where the sky points is foreground by definition — this is the
  occlusion map, derivable from the data rather than drawn by hand.

Both fall out of statistics already being collected: the count planes record
*which* frames contributed to each cell, so the phase distribution is free.

### Consequences

- **The occlusion mask is derivable, not hand-drawn.** It is the set of sensor
  pixels whose brightness is uncorrelated with sidereal phase. This matters
  because occlusion masking is a **blocker** for the bootstrap (the 2026-07-02
  solve stalled on foreground/glow cells) — and it means the blocker can be
  cleared *by* a coarse accumulation rather than before one.
- **Order matters: mask in sensor space BEFORE co-adding**, because once
  de-rotated the tree is spread over an arc of cells and is far harder to
  attribute.
- **This is the same object as the meteor work**, from the other side: the
  transient detector wants what the accumulator rejects. Reject from the sum,
  emit to the transients table — one pass, two outputs.
- **It degrades gracefully.** Even without an explicit mask, a cell whose
  samples are phase-clustered can simply be *down-weighted*, which is a
  continuous statistical response rather than a binary classification.

## Relationship to detrans — the working precedent, and its two limits

Peter, 2026-08-13: *"we will start with astrocam. we have done detrans which is
related to this method but relies on modeling the mapping and the sampling is
naive."* Exactly right, and worth stating precisely because `bin/detrans-sweep`
is the **proven, working ancestor** of the map — the same idea (undo the sky's
motion, then co-add) at one-night scale.

**What detrans does:** undistort each frame, shift each by `-v·(t−t₀)` to cancel
a near-uniform translation, then max-stack a 10-min window so the per-frame 60 s
streaks overlap into one sharp high-SNR streak per star. It **works**, and its
output is on the public site today.

**Limit 1 — the mapping is MODELLED, not measured.** detrans uses a two-parameter
radial polynomial, `s = 1 + k1·rd² + k2·rd⁴` with `k1 = −0.636, k2 = +0.311`
fitted once (worklog 2026-06-21), plus a single global velocity `v = 0.040 px/s`
at a fixed 7.8° from horizontal. That is a *smooth analytic guess* at the true
transform, uniform across the frame and constant in time. The map instead
resamples through the **stored, measured vector field** — per-tile effective
poles, SIP distortion, refined by every night that contributes. The bootstrap
above is precisely the machinery for producing what detrans assumes.

**Limit 2 — the sampling is naive.** Both stages use `cv2.INTER_LINEAR`
(bilinear), applied twice: once in the undistort `remap`, once in the
`warpAffine` shift. `what-accumulation-buys.md` and STATE's accumulation theory
both warn against exactly this — *"naive interpolation on undersampled data
aliases"*. Two chained bilinear passes also smooth the PSF twice, which is
precisely the sub-pixel information the map exists to preserve. The map uses
**drizzle-style variable-pixel accumulation** (or Fourier-phase placement)
instead, and resamples **once**, at accumulation time.

**A third difference, implicit in Peter's framing:** detrans models the motion as
a *uniform translation*, valid only over a short window for a far-off-pole
camera. That assumption fails outright for astrocam, which contains the pole —
there the motion is a rotation, and no single velocity vector describes it. This
is why detrans was built for eclipticam-v3w and why **astrocam needs the map**
rather than an extension of detrans.

**So: start with astrocam** (Peter's call). It is the right first instrument
because:
- its map is a **disc** — the smallest extent of the three (4,328 sq° vs
  eclipticam's 30,715), so the buffers are small and iteration is fast;
- it contains the pole, so Polaris is *in frame* — the bootstrap's seed and the
  natural origin, with distortion ≈ 0 there;
- it has by far the **most data** (88,415 frames, 61 populated nights, both
  epochs) — the recursion has something to bite on;
- and detrans **cannot** serve it, so the map is not duplicating existing
  capability.

**Keep detrans.** It is the validation reference: for a window where both run,
the map's output should be at least as sharp. A method that cannot beat two
bilinear passes and a hand-fitted quartic is not yet earning its complexity.

## Open questions

- Bucket thresholds are unset — derive from the data, not by guess. (The
  meteor-detector session on 2026-08-13 is the cautionary tale: a threshold
  guessed from three frames scored 1/38 against real ground truth.)
- Does re-grading against the sum need the sum to be *complete*, or is a
  partial A-sum enough to bootstrap? Probably partial — test it.
- Interaction with outlier rejection: bucket weighting and per-cell rejection
  must not double-count the same contaminant.
