# Camera geometry reference — resolutions, flips, representations

**The single place to look up how pixels map between a camera's raw sensor and
its derived representations (mosaic / bin2 / interpolated / sweep).** Written
2026-07-06 after repeatedly re-deriving (and getting wrong) the sweep↔raw
transforms. Keep this current when capture/render geometry changes.

## The three cameras

| Camera | Sensor | Bayer | Raw resolution | Plate scale (deg/px) | rotate_180 |
|---|---|---|---|---|---|
| **eclipticam-v3w** | IMX708 | SRGGB10 (RGGB) | 4608 × 2592 | 0.0443* (see note) | **NO** — array-top = sky-top |
| **eclipticam-v1** | OV5647 | SGBRG10 | 2592 × 1944 | 0.0206 | (day cam; TBD) |
| **astrocam** | IMX219 | SBGGR10 (BGGR) | 3280 × 2464 | 0.019 (nom) / **0.0207 solved** | **YES** — sensor mounted inverted |

\* v3w plate_scale 0.0443 in camera.json is the OLD binned value; solved full-res
is ~0.0221 deg/px (0.02214 = 102°/4608). See project memory / distortion notes.

## Where the flip happens (the recurring gotcha)

- **`rotate_180`** (camera.json key — NOTE the spelling: `rotate_180`, not
  `rotation_180`). Read by the SWEEP RENDER (`bin/sum-sweep` → `render_asinh_*`
  `rotate_180=`). astrocam=true, v3w absent(false).
- **`rotation_180`** (StreamingConfig field, streaming.py) — applied at CAPTURE
  (`bayer[::-1,::-1]`) "to match rpicam-still --rotation 180". Two different
  names for related concepts — a real trap.
- **NET EFFECT:** for **astrocam**, the COLOUR-SWEEP frames are 180°-rotated
  relative to the RAW mosaic (sensor is physically inverted; rotate-before-JPEG).
  For **v3w**, no rotation — raw and rendered share orientation.

## Representations and their transforms

Per camera, the pipeline produces several representations. Coordinates map as:

### Raw mosaic (the sensor truth)
- Full resolution, raw Bayer CFA. The reference frame everything maps to.
- v3w 4608×2592 RGGB, v1 2592×1944 SGBRG, astrocam 3280×2464 BGGR.
- Filenames: v3w/v1 = `<epoch_ms>.fits.fz`; **astrocam = `NNNN.fits.fz` (index,
  time in DATE-OBS header, NOT epoch_ms)** — the `bin/detrans-sweep` DATE-OBS
  fallback (muppet) handles this.

### bin2 (2×2 sum-binned grey or RGB)
- `astro.process.bayer.bin2x2()` / `bin2x2_rgb()`. Half resolution.
- v3w 2304×1296, astrocam 1640×1232. De-mosaics (sums the RGGB/BGGR quad → grey,
  or → RGB). Used by the sweeps and for detection SNR.
- **PSF: ~2.8px** (v3w, measured) — binning widens the undersampled ~1px core.

### interpolated RGB (demosaic)
- OpenCV `cvtColor(BayerXX2RGB)`. Full resolution, colour.
- **PSF: ~2.1px** (v3w) — interpolation BLURS the undersampled point.
- For POINT sources, INTERP LOSES resolution vs the gain-corrected mosaic
  (which keeps the ~1px undersampled sharpness). Use interp for colour/geometry,
  gain-corrected mosaic for point PSF/astrometry. See memory.

### colour-sweep frame (the deliverable JPEG)
- `bin/sum-sweep`: sliding-window SUM of bin2-RGB frames → asinh JPEG →
  `rotate_180` if set. **= bin2 (÷2) THEN rotate_180.**
- astrocam sweep 1640×1232, RGB, **180°-rotated vs raw**.
- **sweep → raw (astrocam):** un-rotate then ×2:
  `raw = ( (swW-1-sx)*2 , (swH-1-sy)*2 )`  (swW,swH = 1640,1232).
  (Verified 2026-07-06 to ~50px on a bright pair — residual = crop/near-neighbour.)
- Sweep frames are **NOT derotated** — star streaks CURVE (the pole rotation).
  The trail = window_min frames stacked at successive positions.

## PSF / sampling (why the representation matters)
- All three sensors are **undersampled** (PSF < ~1px on the mosaic; a star's
  light lands ~one pixel, neighbours near zero). astrocam is the most extreme
  (single 9.6s frame = ~2px point; neighbours ~0%).
- **Streaks:** v3w 55s → ~13px single-frame streak. astrocam 9.6s → ~2px/frame
  (too short); **SUM ~5 frames → ~8-22px streak** (further from pole = longer),
  usable like v3w. See memory (astrocam-streaks-via-summing).
- Gain-corrected mosaic (scale R,B channels to G on the star patch = assume
  white) is the sharpest representation for white point sources.

## TODO / inconsistencies to fix
- Unify `rotate_180` vs `rotation_180` naming (capture vs render).
- v3w camera.json still records the OLD binned plate_scale/pedestal/k1k2 —
  recalibrate on full-res and update (flagged in resolution_notes).
- Record the exact sweep window_min/step_min per camera (frame_NNNNN ↔ time).
