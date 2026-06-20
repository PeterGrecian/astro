#!/usr/bin/env python3
"""astrocam long-running capture loop, picamera2 streaming.

Like starcam: a single Picamera2 video pipeline runs continuously with
double-buffered raw frames. Each iteration pulls the most recent completed
frame via capture_request() while the next is already exposing.

Day mode: short auto-ish exposure (gain 1.0, 100ms) for cheap mean check.
Night mode: 10s exposure (sensor max for IMX219 is ~11.76s), gain 1.0,
  raw Bayer -> CompImageHDU (.fits.fz) every frame.

Mode is driven by frame.mean() of the Bayer image, with hysteresis +
lockout, exactly like starcam. Cover open/close happens on the flip.

DAOStarFinder runs every STARFIND_INTERVAL_S over the unoccluded tiles,
with edge-guard and persistence filters to suppress hot pixels and
tile-boundary artefacts.

Layout: ~/astrocam-frames/YYYY-MM-DD/HHMMSS.fits.fz
State:  /var/lib/astrocam/state.json
"""
import json
import math
import signal
import subprocess
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.utils.exceptions import AstropyUserWarning
from photutils.centroids import centroid_2dg
from photutils.detection import DAOStarFinder

# Shared noon-rollover helper used by all cameras.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from astro.nightdir import night_of  # noqa: E402
from astro.brightness_log import BrightnessRow, append as append_brightness  # noqa: E402
from picamera2 import Picamera2

# Gaussian fits on non-star noise candidates produce a flood of these.
# We only refine bright candidates so the warning is irrelevant in practice.
warnings.filterwarnings("ignore", message="The fit may not have converged.*")
warnings.filterwarnings("ignore", category=AstropyUserWarning, message="Sources were found.*")

HOME = Path.home()
HERE = Path(__file__).resolve().parent
FRAMES = HOME / "astrocam-frames"
STATE_DIR = Path("/var/lib/astrocam")
STATE_FILE = STATE_DIR / "state.json"
OCCLUSION_FILE = HERE / "occlusion.json"

# IMX219 in video-config mode caps ExposureTime at 1.238765 s — libcamera
# silently clamps anything larger. The 11.76 s ceiling exists only in the
# still configuration (which loses streaming/double-buffering). 1.2 s is
# the practical max here, and it works fine for a zenith-pole camera:
# sub-pixel star trails are guaranteed, and we get ~10x more frames per
# 20-min window (~1000 instead of ~100), more than recovering the per-frame
# SNR loss via stacking depth and giving denser motion samples for the
# per-patch pole fit.
#
# Same exposure/gain in both day and night so the frame.mean() thresholds
# below are coherent across the cover transitions (starcam does the same).
# Day mode just discards the raw and doesn't write FITS.
EXPOSURE_US = 1_200_000
GAIN = 4.0

# Co-add N consecutive raw frames in RAM, emit one summed FITS per group.
# 8 frames * 1.2s = 9.6s integration per output, ~6 outputs/min vs ~50.
# Sum stays in uint16 (max 8 * 1023 = 8184 << 65535) so no widening.
COADD_N = 8

# Sensor pedestal (black level) for "stops above pedestal" in brightness.csv.
# Keep in sync with astrocam/camera.json "pedestal".
PEDESTAL = 519.0

RESOLUTION = (3280, 2464)
RAW_FORMAT = "SBGGR10"  # IMX219 native, confirmed from rpicam-still

# Mode thresholds on Bayer frame.mean(). 10-bit data 0..1023.
# These were eclipticam-style luminance numbers; we want raw means.
# 10s @ gain 1 dark sky should be ~30-60. Twilight 200-500. Saturated 900+.
# Tuned from first observation 2026-06-09: dark cover-closed mean was ~3,
# evening twilight at the open cover was ~30-100.
COVER_DARK_MEAN = 80.0    # frame.mean <= this for N → open cover
COVER_BRIGHT_MEAN = 250.0  # frame.mean >= this for N → close cover
COVER_HYST_FRAMES = 5
COVER_LOCKOUT_S = 300

# Per-tile star detection. Run on every co-add so each ~10s emit produces
# a candidate epoch — 120 epochs per 20-min derot window, plenty for the
# per-patch pole fit.
STARFIND_INTERVAL_S = 0
STARFIND_FWHM = 2.5
STARFIND_THRESHOLD_SIGMA = 5.0
# Edge guard: reject detections within this many half-res pixels of any
# tile boundary. Tile-boundary artefacts produced 100% of detections in
# the first night's data.
STARFIND_EDGE_GUARD_PX = 5
# 2D Gaussian centroid refinement: extract a (2*REFINE_HALF+1)^2 window
# around each DAOStarFinder peak and refit. Sub-0.1 px centroids.
# Only refine candidates with DAO flux >= REFINE_FLUX_MIN — fitting non-stars
# is slow (LM non-convergence) and useless. Real stars at our co-add depth
# come out at flux ~100+; noise candidates are typically < 50.
REFINE_HALF = 5
REFINE_FLUX_MIN = 80.0
# Persistence is handled downstream in the pole-fit stage (a hot pixel
# contributes no rotation signal and self-downweights). Filtering it at
# capture time risks killing real stars at the pole tile (H6), which move
# sub-pixel between adjacent epochs.


def utcnow():
    return datetime.now(timezone.utc)


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def cover(position):
    subprocess.run([sys.executable, str(HERE / "cover.py"), position], check=True)


def make_camera():
    cam = Picamera2()
    cfg = cam.create_video_configuration(
        raw={"size": RESOLUTION, "format": RAW_FORMAT},
        main={"size": (640, 480), "format": "RGB888"},
        buffer_count=4,
    )
    cam.configure(cfg)
    return cam


def apply_controls(cam):
    cam.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "AnalogueGain": GAIN,
        "FrameDurationLimits": (EXPOSURE_US, EXPOSURE_US),
        "ExposureTime": EXPOSURE_US,
    })


def write_fits(coadd, out_path, exposure_us, gain, n_coadd, t_start, t_end):
    hdu = fits.CompImageHDU(data=coadd, compression_type="RICE_1")
    hdu.header["EXPTIME"] = exposure_us / 1e6 * n_coadd  # total integration
    hdu.header["GAIN"] = gain
    hdu.header["NCOADD"] = n_coadd
    hdu.header["FRAMEEXP"] = exposure_us / 1e6  # single-frame exposure
    hdu.header["BAYERPAT"] = "BGGR"
    hdu.header["DATE-OBS"] = t_start.isoformat()
    hdu.header["DATE-END"] = t_end.isoformat()
    hdu.header["CAMERA"] = "imx219"
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(out_path, overwrite=True)


def load_sky_tiles():
    occ = json.loads(OCCLUSION_FILE.read_text())
    cols, rows = occ["grid"]["cols"], occ["grid"]["rows"]
    col_labels, row_labels = occ["grid"]["col_labels"], occ["grid"]["row_labels"]
    trees = set(occ["trees"])
    sky = [(c, r, f"{col_labels[c]}{row_labels[r]}")
           for c in range(cols) for r in range(rows)
           if f"{col_labels[c]}{row_labels[r]}" not in trees]
    return sky, cols, rows


def starfind_tiles(bayer, sky_tiles, n_cols, n_rows):
    """Two-stage detection:
      - DAOStarFinder on the half-res 2x2 Bayer-sum grey (fast detection).
      - Gaussian centroid refinement on the FULL-res debayered grey window
        around each bright detection (sub-0.1 px precision).
    Returned x,y are in the full-res (Bayer) pixel grid."""
    # Half-res grey for detection. Same as the original cheap-and-fast path.
    grey_half = (
        bayer[0::2, 0::2].astype(np.float32)
        + bayer[0::2, 1::2]
        + bayer[1::2, 0::2]
        + bayer[1::2, 1::2]
    ) * 0.25
    hH, hW = grey_half.shape

    # Full-res debayer is only needed for windows around bright candidates.
    # Defer the cv2.cvtColor cost until we know there's something to refine.
    grey_full = None

    tile_w = hW / n_cols
    tile_h = hH / n_rows
    out = []
    for c, r, label in sky_tiles:
        x0 = int(round(c * tile_w))
        x1 = int(round((c + 1) * tile_w))
        y0 = int(round(r * tile_h))
        y1 = int(round((r + 1) * tile_h))
        sub = grey_half[y0:y1, x0:x1]
        if sub.size == 0:
            continue
        mean, median, std = sigma_clipped_stats(sub, sigma=3.0)
        if std <= 0:
            continue
        finder = DAOStarFinder(
            fwhm=STARFIND_FWHM, threshold=STARFIND_THRESHOLD_SIGMA * std
        )
        sources = finder(sub - median)
        if sources is None:
            continue
        sh, sw = sub.shape
        for s in sources:
            xs = float(s["x_centroid"])  # half-res tile coords
            ys = float(s["y_centroid"])
            if (xs < STARFIND_EDGE_GUARD_PX
                    or ys < STARFIND_EDGE_GUARD_PX
                    or xs > sw - STARFIND_EDGE_GUARD_PX
                    or ys > sh - STARFIND_EDGE_GUARD_PX):
                continue
            flux = float(s["flux"])
            # Half-res frame coords -> full-res (Bayer) frame coords by *2.
            xf = (xs + x0) * 2.0
            yf = (ys + y0) * 2.0
            if flux < REFINE_FLUX_MIN:
                out.append({
                    "tile": label, "x": xf, "y": yf,
                    "flux": flux, "refined": False,
                })
                continue
            if grey_full is None:
                grey_full = cv2.cvtColor(
                    bayer.astype(np.uint16), cv2.COLOR_BAYER_BG2GRAY
                ).astype(np.float32)
            gfH, gfW = grey_full.shape
            ix, iy = int(round(xf)), int(round(yf))
            wx0 = max(0, ix - REFINE_HALF)
            wx1 = min(gfW, ix + REFINE_HALF + 1)
            wy0 = max(0, iy - REFINE_HALF)
            wy1 = min(gfH, iy + REFINE_HALF + 1)
            window = grey_full[wy0:wy1, wx0:wx1] - median
            try:
                rx, ry = centroid_2dg(window)
            except Exception:
                rx, ry = xf - wx0, yf - wy0
            if not (np.isfinite(rx) and np.isfinite(ry)):
                rx, ry = xf - wx0, yf - wy0
            out.append({
                "tile": label,
                "x": float(rx + wx0),
                "y": float(ry + wy0),
                "flux": flux,
                "refined": True,
            })
    return out


_stop = False


def _on_term(signum, frame):
    global _stop
    _stop = True


def main():
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)
    sky_tiles, n_cols, n_rows = load_sky_tiles()
    print(f"astrocam: {len(sky_tiles)} sky tiles ({n_cols}x{n_rows} grid)", flush=True)

    state = load_state()
    mode = state.get("mode", "day")
    consec_dark = 0
    consec_bright = 0
    last_cover_flip = 0.0

    cover("open" if mode == "night" else "closed")

    cam = make_camera()
    apply_controls(cam)
    cam.start()
    print(f"camera started in {mode} mode", flush=True)

    last_starfind = 0.0
    coadd_buf = None
    coadd_count = 0
    coadd_t_start = None

    try:
        while not _stop:
            req = cam.capture_request()
            try:
                bayer = req.make_array("raw").view(np.uint16)
            finally:
                req.release()
            now = utcnow()
            now_mono = time.monotonic()
            frame_mean = float(bayer.mean())

            if mode == "night":
                # Accumulate into uint16 buffer (max 8 * 1023 = 8184).
                if coadd_buf is None:
                    coadd_buf = bayer.copy()
                    coadd_count = 1
                    coadd_t_start = now
                else:
                    coadd_buf += bayer
                    coadd_count += 1

                if coadd_count >= COADD_N:
                    # Noon-rollover night-of date: (utc - 12h).date().
                    # Keeps one observing session (evening + morning hours)
                    # under a single date dir — matches eclipticam.
                    out_dir = (FRAMES / night_of(now)
                               / now.strftime("%H"))
                    out_dir.mkdir(parents=True, exist_ok=True)
                    mmss = now.strftime("%M%S")
                    fits_path = out_dir / f"{mmss}.fits.fz"
                    write_fits(
                        coadd_buf, fits_path, EXPOSURE_US, GAIN,
                        coadd_count, coadd_t_start, now,
                    )

                    # Brightness sidecar for stage 1 (astro-state) and the
                    # brightness plot — one row per landed FITS, on the coadd.
                    # Mirrors eclipticam-v3w's streaming writer. NFS hiccup
                    # must not stop capture; astro-state falls back to
                    # sun-altitude until rows resume.
                    coadd_mean = float(coadd_buf.mean())
                    exptime_s = EXPOSURE_US / 1e6 * coadd_count
                    per_s = (coadd_mean / (exptime_s * GAIN)
                             if exptime_s * GAIN > 0 else coadd_mean)
                    stops = (math.log2(coadd_mean / PEDESTAL)
                             if coadd_mean > 0 and PEDESTAL > 0 else float("nan"))
                    try:
                        append_brightness(FRAMES, "astrocam", BrightnessRow(
                            utc_iso=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            epoch_ms=int(now.timestamp() * 1000),
                            mode="night",
                            exptime_s=exptime_s,
                            gain=GAIN,
                            mean=coadd_mean,
                            per_s=per_s,
                            stops_above_pedestal=stops,
                        ))
                    except OSError as e:
                        print(f"brightness.csv append failed: {e}", flush=True)

                    if (now_mono - last_starfind) >= STARFIND_INTERVAL_S:
                        cands = starfind_tiles(
                            coadd_buf, sky_tiles, n_cols, n_rows
                        )
                        # Sidecar cands JSON in a sibling cands/ dir so
                        # HH/ listings stay clean. Filename matches the
                        # FITS basename (no .cands.json suffix needed).
                        cands_dir = out_dir / "cands"
                        cands_dir.mkdir(parents=True, exist_ok=True)
                        cand_path = cands_dir / f"{mmss}.json"
                        cand_path.write_text(json.dumps({
                            "frame": fits_path.name,
                            "utc": now.isoformat(),
                            "n_coadd": coadd_count,
                            "n": len(cands),
                            "stars": cands,
                        }))
                        print(f"starfind {now:%H%M%S} mean={frame_mean:.1f} "
                              f"-> {len(cands)} candidates", flush=True)
                        last_starfind = now_mono

                    coadd_buf = None
                    coadd_count = 0
                    coadd_t_start = None

            # Cover state machine — frame.mean drives both directions.
            lockout = (now_mono - last_cover_flip) < COVER_LOCKOUT_S
            if frame_mean <= COVER_DARK_MEAN:
                consec_dark += 1
                consec_bright = 0
            elif frame_mean >= COVER_BRIGHT_MEAN:
                consec_bright += 1
                consec_dark = 0
            else:
                consec_dark = 0
                consec_bright = 0

            if not lockout:
                if mode == "day" and consec_dark >= COVER_HYST_FRAMES:
                    print(f"mode day->night (mean={frame_mean:.1f})", flush=True)
                    cover("open")
                    mode = "night"
                    apply_controls(cam)
                    last_cover_flip = now_mono
                    consec_dark = 0
                elif mode == "night" and consec_bright >= COVER_HYST_FRAMES:
                    print(f"mode night->day (mean={frame_mean:.1f})", flush=True)
                    cover("closed")
                    mode = "day"
                    apply_controls(cam)
                    last_cover_flip = now_mono
                    consec_bright = 0

            save_state({"mode": mode, "frame_mean": frame_mean})
    finally:
        cam.stop()


if __name__ == "__main__":
    main()
