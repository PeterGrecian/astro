# Standing plate solve → per-night calibration → undistorted deep deliverable

**Status: DESIGN 2026-07-07.** Prompted by repeatedly eyeballing Altair wrong
(the field shifts night-to-night; no ground-truth pixel↔sky) and the goal that
**one deliverable is undistorted** — which the detrans-deep stack already is.

## The key insight: detrans-deep IS the undistort deliverable

`bin/detrans-sweep` (deep mode) already: **undistort each frame (k1,k2) → shift
by −v·(t−t0) to cancel sidereal drift → stack.** So undistortion is already the
first step of the deep deliverable. BUT it uses **hand-fit constants from
camera.json** (k1=−0.636, k2=+0.311, v=0.040 px/s — from the 2026-06-21
star-trail work, on binned data). We know these are stale: the detrans velocity
measured 68% wrong + 7° off from Altair (worklog 2026-07-05); distortion never
re-fit on full-res in-focus.

So we do NOT build a new undistort renderer. **The standing plate solve's job is
to FEED detrans-deep correct distortion + velocity + pole/roll, per night,
automatically** — replacing the stale hand constants. The deliverable already
exists; the solve makes it *correct*.

## Two coupled pieces

### 1. `astro-solve` (NEW, standing) — per-night plate solve
Runs on the NFS host (puppy) after stage-3, per camera per night:
- Pick the **clearest frame** (highest star count — reuse the sensitivity/gating
  already computed; a cloudy night has few stars → skip/flag).
- Detect stars (existing `detect`/`cands`), apply the master hot-mask (step 0).
- `solve-field --tweak-order 3 --pixel-error 1` → **SIP-distortion WCS** (engine
  + Tycho-2 indexes already installed on puppy; `bin/solve-detections` is the
  starcam-oriented core to generalise).
- **Distil** the WCS → the numbers detrans-deep consumes:
  - radial **k1, k2** (fit the SIP to the rho-normalised radial model, or carry
    SIP directly if detrans-deep is extended to accept it),
  - **pole / scale / roll** → the true sidereal **v** (px/s) + direction,
  - RA/Dec centre, N stars matched, residual (quality).
- Ends the eyeballing: every clear night gets a real pixel↔sky map + star IDs.

### 2. detrans-deep (EXISTS, `bin/detrans-sweep`) — consumes the calibration
Reads the per-night calibration if present; produces the undistorted, registered,
stacked deep image (the deliverable). No new renderer needed.

## Calibration flow: per-night file (DECIDED)

`astro-solve` writes **`<night>/<camera>/calibration.json`**:
```
{ solved: true, utc, frame, n_stars, residual_px,
  wcs: {...}, ra_dec_centre, roll_deg, scale_arcsec_px,
  k1, k2, rho_norm, centre_px,
  detrans_v_px_s, detrans_angle_deg,
  star_ids: [{name, x, y, mag}, ...] }
```
- **detrans-deep reads calibration.json if present, else falls back to
  camera.json** (the stable default). Per-night tracks any drift/refocus (incl.
  the focus-dither nights); camera.json stays the versioned baseline.
- Mirrors the hot-mask two-tier pattern (per-night refinement + stable default).
- `solved: false` (cloudy/too-few-stars) → detrans-deep uses camera.json; the
  night is flagged, not broken.

## Why this fixes the recurring problems
- **Altair eyeballing** (bitten 3× — 07-05/06/07): gone; the solve gives star IDs
  + WCS every clear night.
- **Stale k1/k2 + 68%-wrong v**: replaced by per-night fitted values → the
  undistorted deep stack stops trailing.
- **The quests** (M51/Algol/Polaris/planets): all need pixel↔sky; this is their
  shared foundation (see `design/zenith-quests.md`, which lists the standing
  plate solve as the pending dependency).

## Build order
1. Generalise `solve-detections` → per-camera per-night solve (full-res v3w,
   astrocam; scale windows per camera; master hot-mask; clearest-frame pick).
2. Add the SIP→(k1,k2,v,pole,roll) distillation → write `calibration.json`.
3. Wire detrans-deep to read `calibration.json` (fallback camera.json).
4. Make it standing: hook into astro-process (stage 3) per night, or a timer.
5. Validate: the undistorted deep stack's star trails go straight + registered;
   residual < 1 px.

## Deps present
`solve-field` + Tycho-2 indexes on puppy; `bin/{solve-detections,wcs-from-anchors,
fit-distortion-*,plot-distortion,orient-check}`; `astro.process.detect`; the
master hot-mask + `load_master`. Mostly assembly + the distillation glue.
