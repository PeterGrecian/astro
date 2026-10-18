"""Which astrocam frames saw the sky through an OPEN cover.

From 2026-10-18 (epoch 5, av3s-z) the cover is transparent and capture runs
while it is closed: closed frames pass ~91% with a violet cast, so they must
never be mixed with open frames in photometry, glow maps, stacks or camera-model
fits. Every FITS from then on carries COVER = open / closed / moving; a frame
without the keyword predates it and counts as open.

One earlier night has no header but a side log: 2026-10-17 (epoch 4) had a
2-minute cover dip at :30 past each hour, logged in
<frames>/cover-dips-<night>.log as "<ISO>Z closed|open" lines. A frame whose
exposure OVERLAPS a dip is dropped, not just one that starts inside it.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache


@lru_cache(maxsize=None)
def _dips(log_path: str) -> tuple:
    """Closed intervals (start, end) in unix seconds from a cover-dips log."""
    if not os.path.exists(log_path):
        return ()
    out, closed_at = [], None
    for line in open(log_path):
        parts = line.split()
        if len(parts) != 2 or parts[1] not in ("closed", "open"):
            continue                       # "skip ..." and other notes
        t = datetime.strptime(parts[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        if parts[1] == "closed":
            closed_at = t
        elif closed_at is not None:
            out.append((closed_at, t))
            closed_at = None
    if closed_at is not None:
        out.append((closed_at, float("inf")))
    return tuple(out)


def frame_open(path: str, header=None) -> bool:
    """True if the frame at path was exposed through an open cover.

    path is <frames>/<night>/<HH>/<ms>.fits.fz; header (HDU 1) is read if not given.
    """
    if header is None:
        from astropy.io import fits
        header = fits.getheader(path, 1)
    cover = header.get("COVER")
    if cover is not None:
        return str(cover).strip().lower() == "open"
    night_dir = os.path.dirname(os.path.dirname(path))
    dips = _dips(os.path.join(os.path.dirname(night_dir), f"cover-dips-{os.path.basename(night_dir)}.log"))
    if not dips:
        return True
    t0 = int(os.path.basename(path).split(".")[0]) / 1000     # filename = exposure start
    t1 = t0 + float(header.get("EXPTIME", 60.0))
    return not any(a < t1 and t0 < b for a, b in dips)
