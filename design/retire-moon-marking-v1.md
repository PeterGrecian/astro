# Retire moon/sun-net hand-marking + v1-day anchoring

**Status: PLAN (2026-07-05). Not yet executed — document first, tidy later.**

## Why

The moon-net (and sun-net) hand-marking + the v1↔v3w transform were
**scaffolding to get the first astrometric anchor on v3w**, which has no
celestial pole in frame. That worked — but hand-marking splay probes each night
proved practically tedious, and the v1 day-frame path was fiddly.

**2026-07-05 it became unnecessary: Altair was identified directly in v3w night
frames, and automatic predict-and-confirm then finds more stars from a local
plate fit.** So v3w now bootstraps its own astrometry from stars — no moon
anchor, no v1, no hand-marking. See memory `project-v3w-star-id-moon-anchor`.

v1 day-frame capture itself is also slated for retirement (see below).

## Tiered retirement (retire inside-out; keep genuine deliverables)

### Tier 1 — hand-marking + v1 anchor scaffolding (RETIRE, clearly superseded)
- `bin/mark-moon-net` — splay-probe → thread hand-marking. The tedious bit.
- `bin/fit-v1-v3w` — the v1↔v3w affine/warp fit.
- `eclipticam-v1/v1_to_v3w.json` — the stored v1→v3w transform.
- `eclipticam-v1/moon-net.json`, `eclipticam-v1/sun-net.json` — v1 day-frame nets.
- `moon-overlay --v1-fov / --v1-sun` flags + the v1-FOV-box / sun-trail overlay
  code (keep `moon-overlay` itself if Tier 2 keeps the v3w net display).
- `publish-night-cam` L413: the `[[ "$CAMERA" == eclipticam-v3w ]] && --v1-sun`
  hook.
- Design docs now historical: `design/pole-from-sun-moon.md`,
  `design/moon-net-workflow.md`, `design/v1-night-hdr.md` — mark superseded (or
  move to a historical note), don't necessarily delete (they record the method).

### Tier 2 — v3w moon-net DISPLAY (DECISION PENDING)
The `moon-net.png` website deliverable (v3w reference-stack + moon threads,
published by `moon-overlay --publish` in `publish-night-cam` L404-414, indexed
by `build-calendar-index`). Altair/star-ID supersedes the moon as the *anchor*,
but the moon-net **image** may still be wanted as a display/wow.
- IF retiring: unwire the `moon-overlay --publish` hook in `publish-night-cam`,
  drop the moon-net.png reference in `build-calendar-index` + the website
  (mywebsite reads `<cam>/moon-net.png`), and stop publishing
  `eclipticam-v3w/moon-net.json`.
- IF keeping: leave as-is; it's independent of the marking/v1 scaffolding.
- **Peter to decide.** Default: KEEP the display, retire only Tier 1.

### Tier 3 — moon CROPS / montage / tracking (KEEP — real v3w deliverables)
These are NOT scaffolding — they're science/pretty deliverables, independent of
hand-marking:
- `bin/moon-extract` — night moon crops (montage/HDR). Wired in
  `publish-night-cam` L235-238. KEEP.
- `bin/moon-crops` — verification crops (pointing check). KEEP (or demote).
- `bin/moon-track` — AUTO moon tracking (not hand-marking). KEEP.
- `bin/moon-deliver` — nightly moon montage delivery. KEEP.
- `design/moon-capture.md`, `design/moon-daily-delivery.md` — keep.

## v1 day-frame retirement (separate but related)
v1 day capture is slated to stop. Touch points:
- `services/astro-state.env.eclipticam` + `astro-process.env.{eclipticam,puppy}`:
  `CAMERAS="--camera eclipticam-v1 --camera eclipticam-v3w ..."` → drop v1.
- `eclipticam/capture.py` day path captures both cams (CAM_V1) → remove v1.
- Keep `eclipticam-v1/` config dir + historical data (don't delete data);
  just stop capturing/processing v1 going forward.
- `astro/dispatch.py run_day_moon_tracking` (moon-track WIP, never wired) →
  delete the stub; day-frame moon tracking is moot once v1 day is retired.

## Ordered execution (when ready)
1. **Unwire production hooks first** (so nothing errors mid-retirement):
   `publish-night-cam` v1-sun flag; (Tier 2 if chosen) the moon-overlay publish
   + calendar-index + website; `dispatch.py` day-moon stub.
2. **Drop v1 from the capture/process env-files** + capture.py day path.
3. **Remove Tier 1 tools + configs.** `git rm bin/mark-moon-net bin/fit-v1-v3w
   eclipticam-v1/{moon,sun}-net.json eclipticam-v1/v1_to_v3w.json`; strip the
   `--v1-fov/--v1-sun` code from `moon-overlay`.
4. **Mark superseded design docs.**
5. **Deploy**: env-files via ansible to eclipticam; `publish-night-cam` reaches
   puppy via git; website via mywebsite deploy (if Tier 2).
6. **Verify** a night publishes cleanly with the moon/v1 hooks gone.

## Notes
- Historical DATA under `eclipticam-v1/night/...` and the marked nets are kept
  (never `rm` data — trash if anything; but these configs are tiny, keep them).
- The Altair-based star-ID pipeline that REPLACES this is not yet a production
  tool — retire the scaffolding only once the star-ID path is wired into
  `publish-night-cam` (or at least reliably run), so v3w isn't left with NO
  astrometry between the two.
