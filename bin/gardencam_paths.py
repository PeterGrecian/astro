"""Canonical filesystem layout for skycam capture + processing.

Single source of truth for *all* dated paths so that zeropi (capture),
puppy (processing), and the garbage collector agree on where things go.

Layout
------
~/skycam-frames/    YYYY-MM-DD/HH/{epoch_ms}_{day|night}.jpg
~/skycam-processed/ YYYY-MM-DD/HH/                          (per-hour JPEG workdir)
                    YYYY-MM-DD/sky_YYYYMMDD_HH.mp4          (hourly MP4)
                    YYYY-MM-DD/sky_YYYYMMDD_daily.mp4       (daily concat)
~/skycam-rerender/  YYYY-MM-DD/

All dated things use a single canonical YYYY-MM-DD key. canonical_date_key()
extracts that key from any path under the three roots — used by the GC.

Path getters create parent dirs as a side effect; callers can write
straight into the returned path without a separate mkdir.
"""

from datetime import datetime, timezone
from pathlib import Path

FRAMES_ROOT    = Path.home() / "skycam-frames"
PROCESSED_ROOT = Path.home() / "skycam-processed"
RERENDER_ROOT  = Path.home() / "skycam-rerender"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def date_key(when: datetime | None = None) -> str:
    return (when or _now_utc()).strftime("%Y-%m-%d")


def hour_key(when: datetime | None = None) -> str:
    return (when or _now_utc()).strftime("%H")


def frames_hour_dir(when: datetime | None = None) -> Path:
    when = when or _now_utc()
    p = FRAMES_ROOT / date_key(when) / hour_key(when)
    p.mkdir(parents=True, exist_ok=True)
    return p


def processed_hour_dir(date: str, hour: str) -> Path:
    p = PROCESSED_ROOT / date / hour
    p.mkdir(parents=True, exist_ok=True)
    return p


def processed_hourly_mp4(date: str, hour: str) -> Path:
    (PROCESSED_ROOT / date).mkdir(parents=True, exist_ok=True)
    return PROCESSED_ROOT / date / f"sky_{date.replace('-', '')}_{hour}.mp4"


def processed_daily_mp4(date: str) -> Path:
    (PROCESSED_ROOT / date).mkdir(parents=True, exist_ok=True)
    return PROCESSED_ROOT / date / f"sky_{date.replace('-', '')}_daily.mp4"


def rerender_dir(date: str) -> Path:
    p = RERENDER_ROOT / date
    p.mkdir(parents=True, exist_ok=True)
    return p


def canonical_date_key(p: Path) -> str | None:
    """Pull a YYYY-MM-DD key from any path under the three roots. Used by the GC."""
    for part in p.parts:
        if len(part) == 10 and part[4] == "-" and part[7] == "-":
            y, m, d = part[:4], part[5:7], part[8:10]
            if y.isdigit() and m.isdigit() and d.isdigit():
                return part
    return None
