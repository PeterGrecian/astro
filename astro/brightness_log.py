"""Per-frame brightness CSV — written by capture, read by state.

Path: <frames_root>/<YYYY>/<MM>/<DD>/<camera>/brightness.csv

Outside the day|night/ mode subtree so the state daemon can read
dusk's day-mode samples to decide the day->night transition. One
file per camera per night, rolling at noon UTC via night_of().

Writer: append-only, one row per captured frame, cheap (mean/EXPTIME/GAIN
are already computed in astro.process.brightness).

Reader: tail(N) returns the most recent N rows for stage 1's decision.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .nightdir import night_of, night_path

COLUMNS = [
    "utc_iso", "epoch_ms", "mode",
    "exptime_s", "gain",
    "mean", "per_s", "stops_above_pedestal",
]


@dataclass(frozen=True)
class BrightnessRow:
    utc_iso: str
    epoch_ms: int
    mode: str
    exptime_s: float
    gain: float
    mean: float
    per_s: float
    stops_above_pedestal: float

    @property
    def utc(self) -> datetime:
        return datetime.fromisoformat(self.utc_iso.replace("Z", "+00:00"))


def path_for(frames_root: Path, camera: str, when: datetime | None = None) -> Path:
    """Brightness CSV path for the night containing `when` (defaults to now)."""
    when = when or datetime.now(timezone.utc)
    return Path(frames_root) / night_path(night_of(when)) / camera / "brightness.csv"


def append(frames_root: Path, camera: str, row: BrightnessRow) -> Path:
    """Append one row to the brightness CSV for row's night. Creates the
    file (with header) and parent dirs if needed. Returns the path written."""
    p = path_for(frames_root, camera, row.utc)
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(COLUMNS)
        w.writerow([
            row.utc_iso, row.epoch_ms, row.mode,
            f"{row.exptime_s:.6f}", f"{row.gain:.4f}",
            f"{row.mean:.3f}", f"{row.per_s:.3e}",
            f"{row.stops_above_pedestal:.3f}",
        ])
    return p


def tail(frames_root: Path, camera: str, n: int = 20,
         when: datetime | None = None) -> list[BrightnessRow]:
    """Most recent N rows from this night's CSV. Returns [] if file missing."""
    p = path_for(frames_root, camera, when)
    if not p.exists():
        return []
    with p.open() as f:
        rows = list(csv.DictReader(f))
    return [_row_from_dict(r) for r in rows[-n:]]


def latest(frames_root: Path, camera: str,
           when: datetime | None = None) -> BrightnessRow | None:
    """Most recent row, or None if no rows yet for this night."""
    rows = tail(frames_root, camera, n=1, when=when)
    return rows[0] if rows else None


def _row_from_dict(d: dict) -> BrightnessRow:
    return BrightnessRow(
        utc_iso=d["utc_iso"],
        epoch_ms=int(d["epoch_ms"]),
        mode=d["mode"],
        exptime_s=float(d["exptime_s"]),
        gain=float(d["gain"]),
        mean=float(d["mean"]),
        per_s=float(d["per_s"]),
        stops_above_pedestal=float(d["stops_above_pedestal"]),
    )
