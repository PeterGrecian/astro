# All-time accumulation by quality buckets, recursively refined

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
- **Output location: `/mnt/bigstore/astro-data/<instrument>/accumulator/`** —
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

| Camera | Layout |
|---|---|
| astrocam | `astrocam-frames/YYYY/MM/DD/` |
| eclipticam | `eclipticam-frames/night/YYYY-MM-DD/v3w/` |
| starcam | `starcam-frames/night/YYYY-MM-DD/`, hour dirs **either** raw `HH`+`HHb` **or** squashed `HH-sum8`+`HHb-sum2` |
| eos / canon | `eos-frames/YYYY-MM-DD/`, `canon-frames/YYYY-MM-DD/` (plus `eos-frames-live/` = live preview JPEGs, low value, probably skip) |

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

## Open questions

- Bucket thresholds are unset — derive from the data, not by guess. (The
  meteor-detector session on 2026-08-13 is the cautionary tale: a threshold
  guessed from three frames scored 1/38 against real ground truth.)
- Does re-grading against the sum need the sum to be *complete*, or is a
  partial A-sum enough to bootstrap? Probably partial — test it.
- Interaction with outlier rejection: bucket weighting and per-cell rejection
  must not double-count the same contaminant.
