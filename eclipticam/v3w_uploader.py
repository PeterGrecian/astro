#!/usr/bin/env python3
"""eclipticam-v3w-uploader — drain /var/lib/eclipticam-buffer/v3w/*.fits.fz
to NFS night-tree at ~/eclipticam-frames/night/<night>/v3w/HH/.

Same pattern as starcam-uploader: long-running, polls the buffer dir
every UPLOAD_INTERVAL_S, moves files (rename when on the same FS, copy
+ unlink otherwise) so the buffer drains even if the streaming
daemon is mid-write to other files. brightness.csv is concatenated
to the night dir's brightness.csv.

Layout derivation from filename:
  buffer/<epoch_ms>.fits.fz
  → ~/eclipticam-frames/night/<night-date>/v3w/HH/<epoch_ms>.fits.fz
where night-date = (utc - 12h).date() (noon-rollover).
"""
from __future__ import annotations

import logging
import os
import shutil
import signal
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BUFFER_DIR = Path(os.environ.get("V3W_BUFFER_DIR",
                                 "/var/lib/eclipticam-buffer/v3w"))
FRAMES_ROOT = Path(os.environ.get("V3W_FRAMES_ROOT",
                                  str(Path.home() / "eclipticam-frames")))
UPLOAD_INTERVAL_S = float(os.environ.get("V3W_UPLOAD_INTERVAL_S", "5"))

_stop = False


def _on_signal(signum, _frame):
    global _stop
    logging.info(f"signal {signum}; stopping")
    _stop = True


def _night_dir_for(epoch_ms: int) -> Path:
    """Noon-rollover night date: night-of = (utc - 12h).date()."""
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    night = (dt - timedelta(hours=12)).date().isoformat()
    hh = dt.strftime("%H")
    return FRAMES_ROOT / "night" / night / "v3w" / hh


def _drain_brightness():
    """Append the buffer's brightness.csv into per-night brightness
    files. Each line carries epoch_ms so we know which night it
    belongs to. Truncate the buffer file when done."""
    src = BUFFER_DIR / "brightness.csv"
    if not src.exists() or src.stat().st_size == 0:
        return
    # Read everything, partition by night, append, truncate.
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
        nd = _night_dir_for(epoch_ms).parent.parent  # night/<date>/v3w/
        bf = nd / "brightness.csv"
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
    """Move *.fits.fz into the night tree. Skip *.fits.fz.tmp (still
    being written). Returns the number moved this pass."""
    moved = 0
    for src in sorted(BUFFER_DIR.glob("*.fits.fz")):
        # Sanity: filename must be <epoch_ms>.fits.fz.
        try:
            epoch_ms = int(src.name.split(".", 1)[0])
        except ValueError:
            log.warning(f"skip non-epoch file: {src.name}")
            continue
        hour_dir = _night_dir_for(epoch_ms)
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
    log = logging.getLogger("eclipticam-v3w-uploader")
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    BUFFER_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"draining {BUFFER_DIR} -> {FRAMES_ROOT}/night/<date>/v3w/HH/")
    while not _stop:
        try:
            n = _drain_frames(log)
            _drain_brightness()
            if n:
                log.info(f"moved {n} frames")
        except Exception as e:
            log.error(f"drain pass: {e}")
        # Final pass after stop to flush whatever the capture daemon
        # finished writing just before shutdown.
        for _ in range(int(UPLOAD_INTERVAL_S * 10)):
            if _stop:
                break
            time.sleep(0.1)
    # Final flush.
    _drain_frames(log)
    _drain_brightness()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
