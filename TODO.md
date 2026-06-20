# astro — TODO

Live work list. Move items to DECISIONS.md once they crystallise into
load-bearing choices; delete done items (per the
[delete-done feedback memory](file:///home/peter/.claude/projects/-home-peter/memory/feedback_todos_delete_done.md)).

## Now

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

Stage 1 (`astro-state`) and stage 3 (`astro-process`) landed
2026-06-16 and are now deployed + enabled on both the eclipticam and
astrocam Pis (2026-06-20); the old publish-* timers are retired.
Remaining:

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

## Deliverables (website)

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

- [ ] **Barrel-distortion correction** as a published `bin/undistort-frame`
      step before derot for the whole-frame deliverable. `bin/fit-k1`
      already sweeps k1 and scores derot peakiness; productionise.
- [ ] **Hot-pixel mask v2** from the derot stack — real stars are
      points, hot pixels trace arcs. More selective than thresholding
      the raw sum.
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

