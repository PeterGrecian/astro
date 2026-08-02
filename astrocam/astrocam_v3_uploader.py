#!/usr/bin/env python3
"""astrocam-v3-uploader — drain /var/lib/astrocam-buffer/v3/*.fits.fz to the
NFS night tree at ~/astrocam-frames/<night>/HH/.

Mirrors eclipticam's v3w_uploader, but astrocam uses a FLAT night layout
(camera.json night_layout="flat"): YYYY-MM-DD/HH/<epoch_ms>.fits.fz with the
night date decided by noon-rollover (utc - 12h). No per-camera subdir — this
Pi only has the one camera.

Long-running: polls the buffer dir every UPLOAD_INTERVAL_S, moves *.fits.fz
(skipping *.tmp still being written), and concatenates brightness.csv into
per-night files. brightness.csv rows carry epoch_ms so each is filed to the
night it belongs to.
"""
from __future__ import annotations

import logging
import os
import shutil
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running directly or via systemd; put the repo on the path so
# astro.config is importable, then take frames_root from camera.json —
# the single source of truth for where frames live (see camera.json
# frames_root_notes). ASTROCAM_FRAMES_ROOT still overrides for tests.
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from astro.config import CameraConfig

BUFFER_DIR = Path(os.environ.get("ASTROCAM_BUFFER_DIR",
                                 "/var/lib/astrocam-buffer/v3"))
FRAMES_ROOT = Path(os.environ["ASTROCAM_FRAMES_ROOT"]) \
    if os.environ.get("ASTROCAM_FRAMES_ROOT") \
    else CameraConfig.load("astrocam").frames_root
UPLOAD_INTERVAL_S = float(os.environ.get("ASTROCAM_UPLOAD_INTERVAL_S", "5"))

_stop = False


def _on_signal(signum, _frame):
    global _stop
    logging.info(f"signal {signum}; stopping")
    _stop = True


def _night_of(epoch_ms: int) -> str:
    """Noon-rollover night date: (utc - 12h).date()."""
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    return (dt - timedelta(hours=12)).date().isoformat()


def _hour_dir_for(epoch_ms: int) -> Path:
    """Flat layout: <frames_root>/<night>/HH/."""
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    return FRAMES_ROOT / _night_of(epoch_ms) / dt.strftime("%H")


def _drain_brightness():
    """Append the buffer's brightness.csv into per-night brightness files
    (<frames_root>/<night>/brightness.csv), partitioned by each row's
    epoch_ms, then truncate the buffer file (keeping its header)."""
    src = BUFFER_DIR / "brightness.csv"
    if not src.exists() or src.stat().st_size == 0:
        return
    lines = src.read_text().splitlines()
    if not lines:
        return
    header = lines[0] if lines[0].startswith("epoch_ms") else None
    body = lines[1:] if header else lines
    by_night: dict[Path, list[str]] = {}
    for ln in body:
        if not ln:
            continue
        try:
            epoch_ms = int(ln.split(",", 1)[0])
        except ValueError:
            continue
        bf = FRAMES_ROOT / _night_of(epoch_ms) / "brightness.csv"
        by_night.setdefault(bf, []).append(ln)
    for bf, lns in by_night.items():
        bf.parent.mkdir(parents=True, exist_ok=True)
        new = not bf.exists()
        with bf.open("a") as fh:
            if new and header:
                fh.write(header + "\n")
            for ln in lns:
                fh.write(ln + "\n")
    src.write_text((header + "\n") if header else "")


def _drain_frames(log: logging.Logger) -> int:
    """Move *.fits.fz into the night tree. Skip *.fits.fz.tmp (still being
    written). Returns the number moved this pass."""
    moved = 0
    for src in sorted(BUFFER_DIR.glob("*.fits.fz")):
        try:
            epoch_ms = int(src.name.split(".", 1)[0])
        except ValueError:
            log.warning(f"skip non-epoch file: {src.name}")
            continue
        hour_dir = _hour_dir_for(epoch_ms)
        hour_dir.mkdir(parents=True, exist_ok=True)
        dst = hour_dir / src.name
        try:
            shutil.move(str(src), str(dst))
            moved += 1
        except Exception as e:
            log.warning(f"move {src.name} -> {dst}: {e}")
    return moved


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("astrocam-v3-uploader")
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    BUFFER_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"draining {BUFFER_DIR} -> {FRAMES_ROOT}/<night>/HH/ (flat)")
    while not _stop:
        try:
            n = _drain_frames(log)
            _drain_brightness()
            if n:
                log.info(f"moved {n} frames")
        except Exception as e:
            log.error(f"drain pass: {e}")
        for _ in range(int(UPLOAD_INTERVAL_S * 10)):
            if _stop:
                break
            time.sleep(0.1)
    # Final flush.
    _drain_frames(log)
    _drain_brightness()
    return 0


if __name__ == "__main__":
    sys.exit(main())
