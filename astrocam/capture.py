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
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils.detection import DAOStarFinder
from picamera2 import Picamera2

HOME = Path.home()
HERE = Path(__file__).resolve().parent
FRAMES = HOME / "astrocam-frames"
STATE_DIR = Path("/var/lib/astrocam")
STATE_FILE = STATE_DIR / "state.json"
OCCLUSION_FILE = HERE / "occlusion.json"

# IMX219 max exposure is ~11.76 s. 10 s gives headroom.
NIGHT_EXPOSURE_US = 10_000_000
NIGHT_GAIN = 1.0
# Day mode: short exposure so the cover-closed scene doesn't saturate
# the loop. Cheap mean check only — we don't save day frames.
DAY_EXPOSURE_US = 100_000
DAY_GAIN = 1.0

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

# Per-tile star detection
STARFIND_INTERVAL_S = 300
STARFIND_FWHM = 2.5
STARFIND_THRESHOLD_SIGMA = 5.0
# Edge-guard: reject detections within this many pixels of any tile
# boundary in the half-res grey image. Tile-boundary artefacts dominated
# the first night's results.
STARFIND_EDGE_GUARD_PX = 5
# Persistence filter: a candidate present at the same (x, y) +/- this many
# pixels in two consecutive starfind runs is a hot pixel, not a star. Real
# stars rotate around the local pole and move noticeably in 5 min.
PERSISTENCE_TOL_PX = 1.5


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


def apply_controls(cam, mode):
    if mode == "night":
        exp, gain = NIGHT_EXPOSURE_US, NIGHT_GAIN
    else:
        exp, gain = DAY_EXPOSURE_US, DAY_GAIN
    cam.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "AnalogueGain": gain,
        "FrameDurationLimits": (exp, exp),
        "ExposureTime": exp,
    })


def write_fits(bayer, out_path, exposure_us, gain):
    hdu = fits.CompImageHDU(data=bayer, compression_type="RICE_1")
    hdu.header["EXPTIME"] = exposure_us / 1e6
    hdu.header["GAIN"] = gain
    hdu.header["BAYERPAT"] = "BGGR"  # SBGGR10 sensor pattern
    hdu.header["DATE-OBS"] = utcnow().isoformat()
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


def starfind_tiles(bayer, sky_tiles, n_cols, n_rows, prev_cands):
    """Per-tile DAOStarFinder on a 2x2-binned grey proxy of the Bayer image.
    Applies edge-guard and persistence filters. Returns list of dicts.
    Coordinates are in the half-res grey image; multiply by 2 for Bayer."""
    H, W = bayer.shape
    grey = (
        bayer[0::2, 0::2].astype(np.float32)
        + bayer[0::2, 1::2]
        + bayer[1::2, 0::2]
        + bayer[1::2, 1::2]
    ) * 0.25
    gH, gW = grey.shape
    tile_w = gW / n_cols
    tile_h = gH / n_rows
    raw_out = []
    for c, r, label in sky_tiles:
        x0 = int(round(c * tile_w))
        x1 = int(round((c + 1) * tile_w))
        y0 = int(round(r * tile_h))
        y1 = int(round((r + 1) * tile_h))
        sub = grey[y0:y1, x0:x1]
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
            xs = float(s["x_centroid"])
            ys = float(s["y_centroid"])
            # Edge guard: drop anything within STARFIND_EDGE_GUARD_PX of
            # the tile boundary. Tile-edge artefacts produced 100% of the
            # detections in the first night's data.
            if (xs < STARFIND_EDGE_GUARD_PX
                    or ys < STARFIND_EDGE_GUARD_PX
                    or xs > sw - STARFIND_EDGE_GUARD_PX
                    or ys > sh - STARFIND_EDGE_GUARD_PX):
                continue
            raw_out.append({
                "tile": label,
                "x": xs + x0,
                "y": ys + y0,
                "flux": float(s["flux"]),
            })

    # Persistence filter: drop candidates that appear at (almost) the
    # same position in the previous starfind run. Real stars move several
    # pixels in 5 min; hot/warm pixels do not. Compares against prev_cands
    # (list of dicts) regardless of tile.
    if not prev_cands:
        return raw_out
    prev_xy = [(p["x"], p["y"]) for p in prev_cands]
    kept = []
    for s in raw_out:
        sx, sy = s["x"], s["y"]
        stuck = any(abs(sx - px) <= PERSISTENCE_TOL_PX
                    and abs(sy - py) <= PERSISTENCE_TOL_PX
                    for px, py in prev_xy)
        if not stuck:
            kept.append(s)
    return kept


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
    apply_controls(cam, mode)
    cam.start()
    print(f"camera started in {mode} mode", flush=True)

    last_starfind = 0.0
    prev_cands = []

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
                day_dir = FRAMES / now.strftime("%Y-%m-%d")
                day_dir.mkdir(parents=True, exist_ok=True)
                hhmmss = now.strftime("%H%M%S")
                fits_path = day_dir / f"{hhmmss}.fits.fz"
                write_fits(bayer, fits_path, NIGHT_EXPOSURE_US, NIGHT_GAIN)

                if (now_mono - last_starfind) >= STARFIND_INTERVAL_S:
                    cands = starfind_tiles(
                        bayer, sky_tiles, n_cols, n_rows, prev_cands
                    )
                    cand_path = day_dir / f"{hhmmss}.cands.json"
                    cand_path.write_text(json.dumps({
                        "frame": fits_path.name,
                        "utc": now.isoformat(),
                        "n": len(cands),
                        "stars": cands,
                    }))
                    print(f"starfind {hhmmss} mean={frame_mean:.1f} "
                          f"-> {len(cands)} candidates "
                          f"(prev_cache={len(prev_cands)})", flush=True)
                    prev_cands = cands
                    last_starfind = now_mono

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
                    apply_controls(cam, mode)
                    last_cover_flip = now_mono
                    consec_dark = 0
                elif mode == "night" and consec_bright >= COVER_HYST_FRAMES:
                    print(f"mode night->day (mean={frame_mean:.1f})", flush=True)
                    cover("closed")
                    mode = "day"
                    apply_controls(cam, mode)
                    last_cover_flip = now_mono
                    consec_bright = 0

            save_state({"mode": mode, "frame_mean": frame_mean})
    finally:
        cam.stop()


if __name__ == "__main__":
    main()
