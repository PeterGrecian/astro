# astro — TODO

~~sun-net: 5-stop gel bloom; v1 pointing/distortion fit from moon+sun threads;
v3w day-JPEG<->night-FITS offset calibration~~ — **ABANDONED 2026-07-06.** The
whole moon/sun/v1 anchoring line is retired (superseded by Altair star-ID; not
needed for the quests). v1 capture stopped, eclipticam night-only, deliverables
removed. See `design/retire-moon-marking-v1.md`.

Live work list. Move items to DECISIONS.md once they crystallise into
load-bearing choices; delete done items (per the
[delete-done feedback memory](file:///home/peter/.claude/projects/-home-peter/memory/feedback_todos_delete_done.md)).

## Pipeline: derot + sensitivity (branch pipeline-derot-sensitivity, 2026-07-02)

Banked this session (branch `pipeline-derot-sensitivity`, needs merge + a
production night test):
- [x] **Hot-pixel single-channel detect** — `astro.process.badpix.
  single_channel_hot()` (raw-mosaic spike, the tiny-tetris ones), OR'd into
  `nightly-cam`'s badpixel.fits. `derot_stack` already applies the mask.
- [x] **`bin/derot-select`** — sweeps derot windows, scores by registered
  source count, emits best as derot.{fits.fz,jpg} + derot-scores.csv +
  derot-info.json. Validated (454-495 sources/20-frame window).
- [x] **`bin/sensitivity-plot`** — frequency-vs-magnitude GRAPH deliverable
  (not just summary numbers). Plate-solved field → log-N vs V mag, absolute
  axis anchored on brightest named star, TURNOVER (limiting mag) marked,
  NAMED stars annotated at their catalog mags. Emits sensitivity.png +
  sensitivity.json. Validated: astrocam 2026-07-01 found Polaris+Yildun,
  limiting V≈6.8, faintest V≈8.3, 932 stars.
  - [ ] ENHANCE: overlay the CATALOG line (Tycho-2 expected counts in the
    field) alongside detected → completeness reads as detected/catalog
    directly, and the gap past the turnover shows where we start missing
    stars. Needs the Vizier query working (pairs with the off-pole-patch
    fix in the Sensitivity item below — do them together).
- [x] **summary.json derot block** — n_sources/limiting_mag/best_window/k1/k2
  documented; derot-select + sensitivity-plot emit JSON sidecars to populate.
- [ ] **WIRE IN**: publish-night-cam currently runs nightly-cam --no-derot.
  Replace with: fit-pole per night (or use solved pole) → derot-select →
  fold derot-info.json into summary. Needs a reliable per-night pole (the
  camera moved; pole_prior is stale — see solved WCS below). Then publish
  derot.jpg as a deliverable. TEST on a production night before merge.
- [ ] k1/k2 remap path in derot-select is slow (full per-frame remap);
  optimise (precompute combined map) before enabling for full nights.

## Astrocam orientation lock — near-pole outward (2026-07-02)

Program: solve orientation where distortion is ~zero, then work outward.
Started 2026-07-02 on the 2026-07-01 night; near-pole WCS solved by hand
(see memory `project-astrocam-wcs-2026-07-01`). Steps:

- [x] **Near-pole local solution.** Pole + scale + roll from Kochab+Pherkad
      (2-star similarity fit, resid 4px). Pole (1177,510)bin, scale
      0.0419 deg/binpx, roll −149.5°. Camera had MOVED ~20° from the stale
      prior; edge-arc pole was distortion-biased ~3°.
- [ ] **Refine roll from the near-pole trio** (Yildun/2UMi/HD66368 region,
      ~3.4° out, ~120° apart, mag 4.3–5.2) — a 120° baseline pins roll far
      tighter than the 8° Kochab–Pherkad pair. Polaris currently lands
      "not quite" right → trio fit should fix it.
- [x] **Derot central region → plate-solve — DONE 2026-07-02.** SOLVED via
      astrometry.net (Tycho-2 idx 19, 17 stars, log-odds 47). Recipe that
      worked (peter's steer): `derot-windows --window 40` (SHORT ~6-min
      windows) + FRAME-CENTER crop (optical axis 820,616 binned, min
      distortion — NOT the pole) → 226 clean point sources → solve-field on
      PIP. Authoritative: scale 0.04422 deg/binpx (0.02211 full-res), pole
      (1176,503) — hand-fit within 0.25°. WCS at pip:~/tmp/psf-splay/
      solve-window.wcs. See [[project-astrocam-wcs-2026-07-01]]. Whole-frame
      max-stack would NOT solve (arcs). NEXT (below): write scale/pole into
      camera.json; extend outward (tile derot + k1/k2) for the full frame.
- [ ] **Derot central region → plate-solve** (superseded — see DONE above).
      Max-stack won't solve (stars are arcs). Derot to point sources, then
      solve-field (on PIP — Tycho-2 indices 10-19 there; NOT on muppet).
      PROGRESS 2026-07-02: PROVED the method — binned-space derot about a
      grid-searched pole registered **230 sources (129 within 20°)**, sharp
      near pole. Residual radial smear (arcs grow with radius) is **LENS
      DISTORTION (k1,k2), NOT omega** — omega is PINNED (physics, 1e-6);
      derot-stack's own comment says "mini-arcs until lens distortion is
      fitted". The REAL tooling now RUNS on prepped astrocam data:
      - PREP DONE (reusable): `muppet:~/tmp/psf-work/fitpole-binned/` =
        872 binned `.fits.fz` with EPOCH_MS + candidates.csv (via
        `prep_binned.py` + `find-candidates --grid 80`).
      - `fit-pole` → pole ~(1204,475); `fit-geometry` → pole (1194,482)
        k1=-0.081 k2=0.021 (found real distortion). `derot-patches` applies
        the k1/k2 model.
      BLOCKER: fit landscape is FLAT and derot-patches sharpness ~1.0× —
      **candidate quality**. find-candidates picked saturated FOREGROUND/glow
      cells (houses, bottom of frame), not clean stars, so the fit scores on
      junk. NEXT: mask foreground+sky (occlusion) so candidates are real
      stars, THEN run the pipeline-night bootstrap (iterate fit-pole ↔
      fit-geometry, re-find candidates each round) to converge. Then derot →
      plate-solve. Scratch: `muppet:~/tmp/psf-work/`.
      **USE THE PROVEN PIPELINE** — the starcam v1 derots
      (petergrecian.co.uk/starcam/night/2026-05-27, "pole spread 146px") come
      from `bin/pipeline-night`, which is the known-good recipe:
      (A) bin each hour to `HHb/` (2×2 binned); (E) per-hour bootstrap
      `fit-pole` (3D: pole_x,pole_y,omega) → `fit-geometry` → `derot-patches`
      → `find-candidates`, darkest hour first, converged pole seeds the next
      hour; result `<HHb>/final/derot.fits.fz`, combined by `derot-night`.
      Invoke: `pipeline-night <night-dir> --pole-x 1171 --pole-y 506`
      (BINNED-px seed — starcam's own pole_prior is [910,40] binned, note
      warns "NOT full-res pixels", exactly the trap below).
      PRINCIPLE (peter): derot works on EITHER binned OR interpolated
      (demosaiced) input — the only hard rule is NOT mosaic (never
      geometrically transform the raw CFA) AND the geometry (pole/omega) must
      be right. Binned isn't required, just convenient; interpolated is
      equally valid and gives more resolution for the solve. My error was
      hand-rolling a derot with a WRONG-geometry pole (full-res ×2 of a
      binned pole → concentric arcs, star 1hr apart missed 675px), NOT the
      demosaic. The pipeline uses binned coords by convention — match
      whatever geometry the input is in.
      PAYOFF (virtuous loop, work CENTER-OUT): fit-pole fine-tunes the pole →
      derot registers faint arcs into POINT sources (esp. bright stars that
      were saturated/arced) → more stars identified → tighter pole. Start
      near the pole (low distortion, already anchored), extend outward ring
      by ring, each ring tightening the fit for the next → rich point-source
      field → plate solve. `pipeline-night` (legacy-delete list, DECISIONS
      2026-06-16) is the working reference. Hot-mask:
      `muppet:~/tmp/psf-work/hotmask-fullres.npy`.
- [~] **Sensitivity / completeness stats** (STARTED 2026-07-02, working).
      Frequency-vs-magnitude on the plate-solved frame-center 6-min window:
      solve-field's source extractor (`.axy`) gives 932 detections with FLUX
      → instrumental mag. **log-N vs mag is a clean completeness curve: rises
      ~Euclidean then TURNS OVER at +5.0 mag below the brightest** (peak 214/
      bin → cliff to 1). ANCHORED: the brightest detection IS Polaris
      (flux 6138, pole-dist 0.8°, V=1.98) — so +5 mag → **limiting mag
      V≈6.8-7.0 (naked-eye), faintest detection V≈8.3**. A 6-min window
      reaches ~V7. Reusable YARDSTICK — turnover rises as we improve (longer
      windows, distortion corr, deeper).
      Caveat: Polaris may be slightly saturated (brightest; ratio to 2nd
      only 1.17 → probably OK) → ±0.3 mag on absolute ZP; verify with an
      unsaturated calibrator. RELATIVE +5 mag depth is solid.
      Scripts: pip `~/tmp/psf-splay/` (loglogN from .axy FLUX; Polaris anchor
      inline). Plot: `~/tmp/psf-splay/loglogN.png`.
      Absolute-via-catalog (Tycho-2 ZP) BLOCKED: 40° near-pole field breaks
      Vizier cone search (row-cap → global stars). FIX: off-pole patch.
      astroquery installed. (Polaris anchor sidesteps this for now.)
- [ ] **Pull faintest stars** using the solved WCS; **estimate magnitudes**
      (calibrate flux against the identified Kochab/Pherkad/UMi stars).
- [ ] **Work outward, fit the plate** — extend from near-pole to the full
      frame, fitting distortion (k1/k2) as radius grows. Ties into
      "Barrel-distortion correction" below.
- [ ] **Write solved WCS into `astrocam/camera.json`** (pole, plate_scale)
      once confirmed on a clean night with a wide anchor — currently a
      manual result only.
- [ ] **Deliverables** — full "final" astrocam derot/orientation products;
      then **backfill** and **archive to Glacier**.

## Now

- [ ] **NEXT BIG: v3w orientation lock via STAR-ID (not moon).** Lock camera
      pointing from identified stars — Altair/Aquila on v3w, Deneb+Polaris on
      astrocam: known position + known time → absolute WCS + plate solve. The
      moon/sun-anchor approach here is **ABANDONED 2026-07-06** (hand-marking
      tedious; stars are direct). Make the plate-solve a standing per-night tool
      (foundation for the quests: M51/Algol/Polaris + limiting mag → Neptune).
      See memory `project-v3w-star-id-moon-anchor`, `design/zenith-quests.md`.
- [ ] **Verify astrocam→muppet night write** (switched 2026-06-28). astrocam
      writes ~11 GB/night over NFS to muppet via a USB2-capped, ~74 ms link.
      Day-probe write works; confirm a full night didn't stutter capture.
- [ ] **Relocate muppet's ASIX ethernet (+ bigdisk) to a USB3/TB4 bus.**
      Currently on a USB2 port → GbE capped to ~280 Mbps. An empty USB3 bus
      sits idle (no dock needed). Matters more now astrocam writes there.
      (Details in ansible `host_vars/muppet.yml`.)
- [ ] **Land the host-shuffle ansible commits.** The muppet network +
      astrocam-export reconciliation sit on branch `monitor-smart-probe`
      (an unrelated SMART-probe feature), not main — cherry-pick or merge.

- [ ] **Migrate eclipticam capture writers to canonical layout.**
      Today `eclipticam/capture.py` (v1) and `eclipticam/v3w_uploader.py`
      (v3w) still write `~/eclipticam-frames/night/<date>/<v1|v3w>/HH/...`
      with `<epoch_ms>.fits.fz` / `NNNN.jpg` basenames. Target is
      `~/eclipticam-frames/YYYY/MM/DD/eclipticam-<v1|v3w>/{day,night}/HH/HH-MM-SS.fits.fz`.
      Once migrated, flip both `eclipticam-v{1,3w}/camera.json` to
      `night_layout: "canonical"` and rsync legacy data into the
      new tree (or accept legacy paths via the `percam` reader for
      the backlog).
      WIP: the v3w_uploader half (canonical `_dst_for` + drops
      `_drain_brightness`) is in `git stash@{0}` ("eclipticam
      v3w_uploader -> canonical layout, paused 2026-06-20") — pop it
      when resuming. v1 capture.py writers not yet done; do both
      together so the layout flip is consistent.
- [ ] **Retire v3w uploader's brightness-CSV drain.** Streaming
      already writes canonical brightness.csv direct to NFS;
      `_drain_brightness()` accumulates a redundant legacy copy.
      (Done in the stashed WIP above — lands with the canonical flip.)
- [ ] **Delete legacy starcam pipeline** (per DECISIONS.md 2026-06-16).
- [ ] **Re-derive astrocam pole/orientation from a clear night** — the
      camera fell during a previous night and was refit by hand
      (2026-06-14). Pointing may have shifted.
- [ ] **Clear up the stale `/home/peter/astro-unify/` clone on puppy.**
      A whole duplicate repo (`unify-cameras` @ ee9a205), clean tree,
      now unused — puppy runs from `/home/peter/astro` on `main`. The
      dead `publish-*` unit files + repo run.sh that referenced its path
      were already removed (2026-06-20); the clone itself remains.
      Delete it once nothing on puppy still points at `astro-unify/`.

## Four-stage migration (per DECISIONS.md 2026-06-16)

Stage 1 (`astro-state`) and stage 3 (`astro-process`) landed 2026-06-16;
old publish-* timers retired. Processing hosts settled 2026-06-28:
**eclipticam** processes on its own Pi (local SSD, self-sufficient);
**astrocam** processes on **muppet** (captures→muppet NFS); **puppy** =
skycam only. (Not the Pi for astrocam — its 1600-frame nights want the
laptop.) Remaining:

1. [ ] **`bin/astro-capture` daemon.** Generic `picamera2` loop driven
      by `camera.json` modes (see `design/capture-unification.md`).
      Migrate astrocam first (no production publish to disturb), then
      eclipticam v3w, then v1. Each camera's existing daemon stays
      running until the new one shows a clean week.
      NB: astrocam/capture.py (~421 lines) already ~90% duplicates
      astro/capture/streaming.py — the brightness.csv writer was
      hand-ported into it 2026-06-20, so the duplication is already
      causing copy-drift. astrocam specifics to fold in: cover servo,
      coadd-in-RAM, starfind tiles.
2. [ ] **`bin/astro-storage` timer.** Weekly squash / cold-archive /
      retention. Inputs: state record (disk pressure flag), per-night
      age. Outputs: state-record updates + log of what moved.

Cross-cutting:
- [ ] **`host.json` per Pi/NFS host** — cameras on this host,
      cross-camera rules. Schema in `design/capture-unification.md`.
      Today the per-host camera lists are duplicated in env files at
      `services/astro-<stage>.env.<hostname>`; host.json will replace
      them.
- [ ] **Migrate to canonical storage layout** (per DECISIONS.md
      2026-06-16; full plan in `design/storage-layout.md`). Per night,
      per camera: rsync from `~/<camera>-frames/{day,night}/<date>/...`
      into `~/astro-frames/YYYY/MM/DD/<camera>/{day,night}/HH/...`.
      Backfill `brightness.csv` from frame headers where missing.
      `astro.frames` keeps a legacy reader until migration completes.

## Capture-side improvements

- [ ] **astrocam → ramdisk + async workers.** Measured 11.73 s mean
      cadence (8 × 1.2 s coadd + 2.1 s FITS write + starfind) at 82%
      duty cycle. Move writes to `/dev/shm`, push bin / starfind /
      FITS encode / badpix off the capture loop. Target <200 ms
      per-frame overhead so we hit the camera's natural ~9.6 s cadence.
      Use the `super/bin/` async-file-transfer queue pattern.
- [ ] **eclipticam-v1 as a dedicated sun camera** — fixed filter, day
      mode only. Capture schema in `design/capture-unification.md`
      already covers a `sun` mode.
- [ ] **Lighten astrocam's nightly sweep render.** astrocam's all-night
      ~1600 frames → 351 sweep windows. astrocam now captures→muppet (NFS)
      and processes on **muppet** (2026-06-28; puppy=skycam only). muppet
      is 8c/7.5G so it copes, but the cost recurs nightly. Mono is now
      dropped (2026-06-28), which helps. Further options: coarser
      `--step-min`, fewer sweep variants for astrocam. Not urgent.

## Deliverables (website)

- [ ] **Tune the diff-sweep trail line-filter, then default it on.**
      `bin/diff-sweep --line-filter` (built 2026-06-30, flag-gated, default
      OFF) extracts star trails and suppresses the noise dots + non-linear
      cloud via a per-pixel oriented open along the ANALYTIC trail direction
      (`trail_angle_field`, from k1,k2 + detrans angle). Big bandwidth win
      (~26× smaller on a real 06-24 frame) but currently OVER-SUPPRESSES in
      the pipeline — the fixed threshold runs on the raw max−mean float, wrong
      scale. Fixes needed before defaulting on for eclipticam-v3w:
      - **noise-relative threshold** (per-frame, e.g. k·σ of the diff), not
        the current absolute `thresh`.
      - mask/handle the foreground (trees, rooftops) so its edges don't pass.
      - **WRITE A SPLAY TUNING PLUGIN** for this — interactive parameter sweep
        (threshold, line-L, nang) on real frames beats blind guessing. splay
        has the app system (`PARAMS`, live tuning, save-to-sidecar); model on
        `~/splay/apps/distortion.py` (same k1/k2 domain). 
      See `design/trail-line-filter.md`; examples in `~/tmp/linefilter-test/`.
- [ ] **Per-day calendar view for eclipticam** on the website, mirroring
      the starcam calendar. Each day shows the colour sweep MP4 (story
      of the night) and the brightness curve. The skycam calendar is
      the model — extract as a shared component
      (`design/repo-boundaries-and-reuse.md`).
- [ ] **Dawn-to-dusk derot animation** — start with a 10-min window
      derot stack centred on the darkest part of the night; feather
      the window width smoothly out to full-night and back; move the
      window start from dusk to dawn. ~60 s video at 60 fps. Probably
      needs barrel-distortion correction more than precise pole
      finding. Immediate sub-problems (from the 06-19 capture, which
      had some very good passages):
      - Local lens-distortion fixes to derot/detrans (per-tile, not
        global) — bad frames currently clobber the derot/detrans.
      - Frame selection: use all frames where brightness < 10 stops
        above pedestal.
      - Decide how to handle gaps in the animation — the raw
        playthrough tolerates them but derot/detrans does not.
- [ ] **Astro experiments page** lists the menu under
      `s3://.../<camera>/nights/<night>/experiments/` so each
      experiment is browsable independently of the multi-source
      player. First experiment to run: `mci-colour` on a clean night.
- [ ] **Web player bugs** (observed in skycam advanced player, applies
      equally to astro since they share `render_skycam_player`):
      - `H` for help doesn't seem to fire; help should be a HUD overlay.
      - Image is too big; can't see the controls and the image at the
        same time on smaller screens.
      - Fullscreen should be a button, not only a keyboard shortcut.

## Pipeline foundations

- [ ] **Bin vs interp (demosaic) — resolve per PSF.** Decided 2026-07-02:
      NEVER geometrically transform the raw Bayer mosaic (cross-channel
      interpolation → colour moiré). Choose bin vs demosaic by the PSF
      (matched filter): bin TO the resolution the PSF actually supports —
      seeing/atmospherics-limited — don't interp beyond what we can resolve.
      astrocam PSF is near-point (Polaris ~1.4px, undersampled → bin-friendly);
      v3w cross-trail ~2.5px full-res; the open question per camera is
      bin depth = PSF FWHM (both bin and demosaic avoid moiré).
      detrans already binned
      via fraction-of-width v. Revisit for the final astrocam res choice.
- [ ] **Barrel-distortion correction** as a published `bin/undistort-frame`
      step before derot for the whole-frame deliverable. `bin/fit-k1`
      already sweeps k1 and scores derot peakiness; productionise.
- [ ] **Hot-pixel mask v2.** Two independent tests, both from 2026-07-02
      near-pole work (automated star-finding kept returning hot pixels).
      **Detect on the RAW MOSAIC, before demosaic** — verified 2026-07-02:
      each hot pixel is a clean SINGLE-photosite spike vs its same-colour
      neighbours (e.g. +5244 amid ±20 floor); trivial to find. After
      demosaic they BLOOM into shape artifacts that are much harder to
      distinguish from real features — green → diagonal (2 G photosites/tile
      on a diagonal lattice), red/blue → L/plus (bilinear spreads the sparse
      R/B photosite to orthogonal neighbours). So mask pre-demosaic and the
      bloom never happens. **Fix at BOTH levels** (peter, "tiny tetris"):
      (a) RAW — single-photosite spike, replace with same-colour neighbour
      median before demosaic; (b) INTERPOLATED — for already-demosaiced
      products (deliverables, cached stacks) the bloom is a KNOWN per-channel
      template (green=diagonal, R/B=L/plus) anchored at badpixel-mask
      locations, so template-match + repair the tetris footprint there too.
      (1) **single-channel test** — real star is coherent across ALL Bayer
      channels (R,G,G,B) at the same sub-pixel; a hot pixel is a single
      spike in ONE channel. (2) **motion test** from the derot/max stack —
      real stars trace arcs, hot pixels stay pixel-fixed. More selective
      than thresholding the raw sum.
- [ ] **Dark master per (sensor, gain, exposure)** — capture procedure
      + apply step. Hook into `astro.process.badpix` or a new
      `astro.process.dark`.
- [ ] **Cloud / sky-quality flag per frame** beyond the existing
      darkest-band gating. Std-dev signal, mean/median ratio,
      centre-vs-edge.
- [ ] **Day-mode sky-mask process** (deferred until rain sensor is
      installed). Daily noon cycle: rain check → cover open → grab
      frames → chromakey + brightness key → cover closed → mask
      written to `~/astro/calib/sky-mask-<camera>-<YYYY-MM-DD>.fits.fz`.
      Pre-reqs: rain sensor on the camera Pi; `bin/auto-sky-mask`
      needs chromakey added (currently brightness-threshold only).
- [ ] **FITS-level frame interpolation** for missing / headlight-
      rejected frames. JPEG-level interpolation (mci on the sweep
      mp4) is cosmetic; FITS-level fixes propagate to every
      downstream operation. Defer until we have a concrete case.

## Cold archive (starcam)

- [ ] **Squashed-vs-raw scientific equivalence experiment** — three
      ground-truth nights identified in `COLD_STORAGE.md`
      (2026-05-23 darkest, 2026-05-24 bright reference, 2026-06-04).
      Define acceptance delta for derot stacks, brightness curves,
      detection counts. Not on the critical path; do when there's
      slack.
- [ ] **Finish per-night cold archival** — see `whereisallthedata.csv`
      for the inventory across hosts and tiers.

## Parked

- **Catalog match & multi-night stacking** — parked exploration, now
  in `design/catalog-match-parked.md` (Gaia WCS fit resume points,
  `derot-week` deferral).

