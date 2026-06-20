20/6 return to anim.  The capture 19/6 had some very good passages so I'm thinking we need to do some local lens distortion fixes to derot/detrans.  we should use all frames where brightness < 10 stops above pedistal and work out what to do about gaps in the animation.  it's all right for initial night playthrough but the bad frames clobber derot/detrans


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
2026-06-16 — see CLAUDE.md status section. Remaining:

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
- [ ] **Deploy `astro-state.service` and `astro-process.service`** on
      eclipticam, astrocam, and (for any camera with
      `processing.host != "self"`) puppy/muppet. Copy the matching
      `services/astro-<stage>.env.<hostname>` to
      `/etc/default/astro-<stage>`. Disable the old
      `publish-{astrocam,eclipticam}.timer` on the same hosts at
      enable-time (stage 3 supersedes them).
- [ ] **Retire `publish-{astrocam,eclipticam}.{timer,service}` and
      their `-run.sh` wrappers** once stage 3 has run cleanly for a
      week. Today's deliverables flow doesn't change — stage 3
      shells the same `bin/publish-night-cam` — only the trigger
      moves from cron-like to event-driven.
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
- [ ] **astrocam → `astro.capture.streaming`.** First user of the
      shared module beyond eclipticam v3w. Template:
      `eclipticam/v3w_night_daemon.py`. Will reveal what's accidentally
      specific to v3w. Plan: `design/capture-unification.md`.
- [ ] **Move processing to the eclipticam Pi** as much as possible
      (brightness, binning, 10-min window accumulation) so puppy only
      stores derived products.
- [ ] **eclipticam-v1 as a dedicated sun camera** — fixed filter, day
      mode only. Capture schema in `design/capture-unification.md`
      already covers a `sun` mode.

## Deliverables (website)

- [ ] **Per-day calendar view for eclipticam** on the website, mirroring
      the starcam calendar. Each day shows the colour sweep MP4 (story
      of the night) and the brightness curve. The skycam calendar is
      the model — extract as a shared component
      (`design/repo-boundaries-and-reuse.md`).
- [ ] **Backfill existing eclipticam nights** through the unified
      pipeline so the calendar has history.
- [ ] **Dawn-to-dusk derot animation** — start with a 10-min window
      derot stack centred on the darkest part of the night; feather
      the window width smoothly out to full-night and back; move the
      window start from dusk to dawn. ~60 s video at 60 fps. Probably
      needs barrel-distortion correction more than precise pole
      finding.
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

## Multi-night / catalog (parked)

The Gaia catalog-match exploration is parked — full design and what
worked / didn't is in `TODO_fit.MD` (deleted on 2026-06-16; available
in git history at commit before the legacy-pipeline deletion). Resume
points if revived:

1. Multi-anchor WCS fit (Polaris + 3–4 Big Dipper stars) to constrain
   (pole_x, pole_y, plate_scale, rotation, k1, k2) jointly.
2. Per-tile WCS instead of global — local distortion is small.
3. Visual side-by-side confirmation of identifications before
   committing to a model.

Multi-night stacking (`derot-week`) deferred until per-night pipeline
matures. Notes: `design/per-tile-effective-pole.md`,
`design/tracking-is-iterated-derot.md`, `design/zonal-derot-strategy.md`.

## Targets

- **Neptune (mag +7.8), Nov 2026.** Late Sep / early Oct opposition;
  observable through November. Estimated ~28 h of derotated stacking
  (~4 dark nights × ~7 h) for 5–6× current single-hour SNR. Needs
  sharp per-night `final/derot.fits.fz` and a planet-aware motion
  model (Neptune drifts ~1 arcmin/day vs. sidereal). Camera also
  needs to survive winter (warm + dry; cover working).
- **Uranus (mag +5.6), Nov 2026 opposition.** Should appear in
  per-night derot already; blink-comparator diff vs. previous night
  should be unmistakable.
- **Wandering-star (planet) blink discriminator** — subtract two
  per-night derot.fits.fz at identical pole + distortion. Stars
  cancel; planets / asteroids / comets leave a ±star signature at
  tonight's and yesterday's pixel. Sketch: `derot-diff <A> <B>` →
  `<B>/diff-vs-<A>.fits.fz`.

## Repo housekeeping

- [ ] Periodically review the boundary between this repo,
      `Berrylands/gardencam` (Pi capture, gradually emptying as
      `astro.capture` absorbs daemons), and `super/services`
      (async file transfer queue). The `pilib` / `piservices`
      focused-Pi repo idea is still open.
- [ ] Decide whether `astrocam-capture.service` moves out of `astro/`
      into ansible once `astro.capture` takes over.
