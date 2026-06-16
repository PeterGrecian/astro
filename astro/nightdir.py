"""Noon-rollover night-date helpers — single source of truth.

The "night of 2026-05-21" runs 2026-05-21 12:00 UTC -> 2026-05-22 12:00 UTC,
so one observing session lives under one date string. A night dir therefore
contains UTC hours 12..23 then 00..11.

Replaces per-script copies in astrocam/nightly.py (current_night_dir),
eclipticam/capture.py (night_date) and assorted bin/ tools.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOON_OFFSET = timedelta(hours=12)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def night_of(when: datetime | None = None) -> str:
    """Night-date string for a UTC instant: (utc - 12h).date()."""
    when = when or _now()
    return (when - NOON_OFFSET).strftime("%Y-%m-%d")


def last_completed_night(when: datetime | None = None) -> str:
    """The night that most recently ENDED (ended at the last noon UTC)."""
    when = when or _now()
    return night_of(when - timedelta(days=1))


def night_window(night: str) -> tuple[datetime, datetime]:
    """[start, end) UTC datetimes for a night-date string."""
    start = datetime.strptime(night, "%Y-%m-%d").replace(
        hour=12, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def night_hours() -> list[str]:
    """UTC hour labels in chronological order within a night dir."""
    return [f"{h:02d}" for h in list(range(12, 24)) + list(range(0, 12))]


def in_night(night: str, when: datetime) -> bool:
    start, end = night_window(night)
    return start <= when < end


def night_path(night: str) -> Path:
    """Path components for a night-date string: 2026-06-15 -> 2026/06/15.

    Canonical NFS layout splits the date across three path levels to
    keep per-level fanout bounded. CLI / state.json / logs keep the
    flat YYYY-MM-DD form; translation happens at filesystem boundaries.
    """
    y, m, d = night.split("-")
    return Path(y) / m / d


def sort_hours_for_night(hours):
    """Sort UTC hour labels in chronological order within a night.

    A night runs noon-to-noon, so the hour sequence is 12..23, 00..11.
    Pass an iterable of "HH" strings; get back a list in the correct
    intra-night order.
    """
    def key(h):
        return (int(h) - 12) % 24
    return sorted(hours, key=key)
