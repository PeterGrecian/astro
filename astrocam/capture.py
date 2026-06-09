#!/usr/bin/env python3
"""astrocam long-running capture loop.

DAY mode (1-min tick):
  - cover closed
  - auto-exposure JPEG probe -> scene_luminance -> hysteresis to NIGHT
  - on DAY->NIGHT: open cover

NIGHT mode (10-s tick):
  - cover open
  - 10s @ gain 1 raw -> .fits.fz (SBGGR10, Rice). DNG discarded.
  - scene_luminance from the FITS feeds the NIGHT->DAY hysteresis
  - on NIGHT->DAY: close cover
  - DAOStarFinder over sky tiles every STARFIND_INTERVAL_S (~5 min)

Layout: ~/astrocam-frames/YYYY-MM-DD/HHMM.{jpg,fits.fz}
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
import rawpy
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from PIL import Image
from photutils.detection import DAOStarFinder

HOME = Path.home()
HERE = Path(__file__).resolve().parent
FRAMES = HOME / "astrocam-frames"
STATE_DIR = Path("/var/lib/astrocam")
STATE_FILE = STATE_DIR / "state.json"
OCCLUSION_FILE = HERE / "occlusion.json"

DAY_TICK_S = 60
NIGHT_TICK_S = 10
NIGHT_SHUTTER_US = 10_000_000
NIGHT_GAIN = 1.0
STARFIND_INTERVAL_S = 300

# Hysteresis on scene_luminance = mean_pixel / (shutter_us * gain).
# Reusing eclipticam's thresholds; recalibrate from first-night data.
LUMINANCE_NIGHT_ENTER = 0.0005
LUMINANCE_NIGHT_EXIT = 0.005
MODE_HOLD_TICKS = 3

# DAOStarFinder per tile
STARFIND_FWHM = 2.5
STARFIND_THRESHOLD_SIGMA = 5.0

_EXIF_EXPOSURE = 33434
_EXIF_ISO = 34855


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
    """Drive the SG90 cover. Reuses the same gpiozero path as cover.py."""
    subprocess.run([sys.executable, str(HERE / "cover.py"), position], check=True)


def scene_luminance_from_jpeg(path):
    try:
        ifd = Image.open(path).getexif().get_ifd(0x8769)
        shutter_us = float(ifd[_EXIF_EXPOSURE]) * 1e6
        iso = float(ifd[_EXIF_ISO])
    except Exception:
        return None
    mean = float(np.array(Image.open(path).convert("L")).mean())
    if shutter_us * iso <= 0:
        return None
    return mean / (shutter_us * iso / 100.0)


def scene_luminance_from_bayer(bayer, shutter_us, gain):
    if shutter_us * gain <= 0:
        return None
    return float(np.mean(bayer)) / (shutter_us * gain)


def shoot_day_probe(out_path):
    cmd = ["rpicam-still", "--immediate", "-n", "-o", str(out_path), "-t", "500"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=15)


def shoot_night_fits(out_path):
    """10s raw -> .fits.fz. Returns the Bayer ndarray, or None on failure."""
    sidecar_jpg = out_path.with_suffix(".tmp.jpg")
    dng_path = sidecar_jpg.with_suffix(".dng")
    cmd = [
        "rpicam-still",
        "-o", str(sidecar_jpg),
        "-n", "-t", "500",
        "--shutter", str(NIGHT_SHUTTER_US),
        "--gain", str(NIGHT_GAIN),
        "--raw",
    ]
    timeout_s = NIGHT_SHUTTER_US // 1_000_000 + 15
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    if r.returncode != 0 or not dng_path.exists():
        print(f"night capture FAILED -> {dng_path}", file=sys.stderr)
        print(r.stderr[-400:], file=sys.stderr)
        sidecar_jpg.unlink(missing_ok=True)
        return None

    with rawpy.imread(str(dng_path)) as raw:
        bayer = raw.raw_image_visible.copy()
        pattern = "".join(chr(raw.color_desc[i]) for i in raw.raw_pattern.flatten())
    hdu = fits.CompImageHDU(data=bayer, compression_type="RICE_1")
    hdu.header["EXPTIME"] = NIGHT_SHUTTER_US / 1e6
    hdu.header["GAIN"] = NIGHT_GAIN
    hdu.header["BAYERPAT"] = pattern
    hdu.header["DATE-OBS"] = utcnow().isoformat()
    hdu.header["CAMERA"] = "imx219"
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(out_path, overwrite=True)
    dng_path.unlink(missing_ok=True)
    sidecar_jpg.unlink(missing_ok=True)
    return bayer


def load_sky_tiles():
    """Return list of (col, row) tile indices that are unoccluded sky.
    Trees excluded; eves kept in (they self-mask via zero detections)."""
    occ = json.loads(OCCLUSION_FILE.read_text())
    cols = occ["grid"]["cols"]
    rows = occ["grid"]["rows"]
    col_labels = occ["grid"]["col_labels"]
    row_labels = occ["grid"]["row_labels"]
    trees = set(occ["trees"])
    sky = []
    for c in range(cols):
        for r in range(rows):
            label = f"{col_labels[c]}{row_labels[r]}"
            if label not in trees:
                sky.append((c, r, label))
    return sky, cols, rows


def starfind_tiles(bayer, sky_tiles, n_cols, n_rows):
    """Run DAOStarFinder per sky tile on a luminance proxy of the Bayer image.
    Returns list of dicts with tile + centroid info. Empty list is fine."""
    # Cheap luminance: average 2x2 Bayer block -> half-resolution grey.
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
    out = []
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
        # Coordinates here are in the 2x2-binned grey image (half the Bayer
        # frame size). Multiply by 2 to recover full-res Bayer pixel coords.
        for s in sources:
            out.append({
                "tile": label,
                "x": float(s["x_centroid"]) + x0,
                "y": float(s["y_centroid"]) + y0,
                "flux": float(s["flux"]),
            })
    return out


def decide_mode(prev_mode, prev_hold, last_lum):
    if last_lum is None:
        return prev_mode, prev_hold + 1
    if prev_hold < MODE_HOLD_TICKS:
        return prev_mode, prev_hold + 1
    if prev_mode == "day" and last_lum < LUMINANCE_NIGHT_ENTER:
        return "night", 0
    if prev_mode == "night" and last_lum > LUMINANCE_NIGHT_EXIT:
        return "day", 0
    return prev_mode, prev_hold + 1


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
    hold = int(state.get("hold", MODE_HOLD_TICKS))
    last_lum = state.get("lum")
    last_starfind = 0.0

    # Match cover to current mode at startup (idempotent).
    cover("open" if mode == "night" else "closed")

    while not _stop:
        t0 = time.monotonic()
        now = utcnow()
        day_dir = FRAMES / now.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        hhmm = now.strftime("%H%M")

        if mode == "day":
            probe = day_dir / f"{hhmm}.jpg"
            shoot_day_probe(probe)
            lum = scene_luminance_from_jpeg(probe) if probe.exists() else None
        else:
            secs = now.strftime("%H%M%S")
            fits_path = day_dir / f"{secs}.fits.fz"
            bayer = shoot_night_fits(fits_path)
            lum = (
                scene_luminance_from_bayer(bayer, NIGHT_SHUTTER_US, NIGHT_GAIN)
                if bayer is not None else None
            )
            if bayer is not None and (t0 - last_starfind) >= STARFIND_INTERVAL_S:
                cands = starfind_tiles(bayer, sky_tiles, n_cols, n_rows)
                cand_path = fits_path.with_suffix("").with_suffix(".cands.json")
                cand_path.write_text(json.dumps({
                    "frame": fits_path.name,
                    "utc": now.isoformat(),
                    "n": len(cands),
                    "stars": cands,
                }))
                print(f"starfind {hhmm} -> {len(cands)} candidates", flush=True)
                last_starfind = t0

        new_mode, new_hold = decide_mode(mode, hold, lum if lum is not None else last_lum)
        if new_mode != mode:
            print(f"mode {mode} -> {new_mode} (lum={lum})", flush=True)
            cover("open" if new_mode == "night" else "closed")
        mode, hold = new_mode, new_hold
        if lum is not None:
            last_lum = lum
        save_state({"mode": mode, "hold": hold, "lum": last_lum})

        tick = NIGHT_TICK_S if mode == "night" else DAY_TICK_S
        elapsed = time.monotonic() - t0
        sleep_for = max(0.0, tick - elapsed)
        # Short sleeps so SIGTERM lands fast.
        end = time.monotonic() + sleep_for
        while not _stop and time.monotonic() < end:
            time.sleep(min(1.0, end - time.monotonic()))


if __name__ == "__main__":
    main()
