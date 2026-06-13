"""Per-frame star detection on 2x2-binned grey frames.

Outputs the cands.json sidecar format used by astrocam/derot.py:
    {"utc": "...", "frame": "...", "stars": [{"tile": "A1", "x": ..., "y": ..., "flux": ...}, ...]}

So per-tile pole fitting / derot machinery downstream works
unchanged on whatever camera produced the cands.

Camera-agnostic; the only camera-specific input is the binned tile
grid (cols, rows, labels) which the caller supplies.
"""
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats

# Tunables (start at DAOStarFinder defaults; can be overridden per call).
FWHM_DEFAULT = 3.0
THRESHOLD_SIGMA = 5.0
EDGE_GUARD_PX = 8  # ignore detections within this many px of the binned-frame edge


def _tile_label(x, y, grid, W, H):
    """Map a pixel (x, y) to its tile label (e.g. "A1")."""
    c = min(int(x * grid["cols"] / W), grid["cols"] - 1)
    r = min(int(y * grid["rows"] / H), grid["rows"] - 1)
    return f"{grid['col_labels'][c]}{grid['row_labels'][r]}"


def detect_one(arr, grid, fwhm=FWHM_DEFAULT, threshold_sigma=THRESHOLD_SIGMA,
               edge_guard_px=EDGE_GUARD_PX):
    """Run DAOStarFinder on the binned grey image `arr` and return a
    list of dicts ready to drop into the cands.json `stars` field."""
    from photutils.detection import DAOStarFinder  # heavy import, lazy

    H, W = arr.shape
    af = arr.astype(np.float32)
    mean, median, std = sigma_clipped_stats(af, sigma=3.0)
    finder = DAOStarFinder(fwhm=fwhm, threshold=threshold_sigma * std)
    tbl = finder(af - median)
    if tbl is None:
        return []
    out = []
    for row in tbl:
        x = float(row["x_centroid"])
        y = float(row["y_centroid"])
        if (x < edge_guard_px or x > W - edge_guard_px
                or y < edge_guard_px or y > H - edge_guard_px):
            continue
        out.append({
            "tile": _tile_label(x, y, grid, W, H),
            "x": x,
            "y": y,
            "flux": float(row["flux"]),
        })
    return out


def cands_path_for(fits_path: Path) -> Path:
    """Sidecar path: foo.fits.fz -> foo.cands.json"""
    return fits_path.with_suffix("").with_suffix(".cands.json")


def write_cands(fits_path: Path, utc_iso: str, stars: list):
    """Write the cands.json sidecar next to the source FITS."""
    cands = {
        "utc": utc_iso,
        "frame": fits_path.name,
        "stars": stars,
    }
    cands_path_for(fits_path).write_text(json.dumps(cands))


def load_grid(occlusion_path: Path) -> dict:
    """Pick the {cols, rows, col_labels, row_labels} grid out of an
    occlusion JSON without parsing the rest."""
    data = json.loads(Path(occlusion_path).read_text())
    return {
        "cols": data["grid"]["cols"],
        "rows": data["grid"]["rows"],
        "col_labels": data["grid"]["col_labels"],
        "row_labels": data["grid"]["row_labels"],
    }
