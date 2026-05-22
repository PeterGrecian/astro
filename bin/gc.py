#!/usr/bin/env python3
"""file-garbage-collector — free disk by deleting oldest dated artefacts.

Runs locally on puppy. Walks the three canonical roots from
`gardencam_paths` (FRAMES_ROOT, PROCESSED_ROOT, RERENDER_ROOT), extracts a
YYYY-MM-DD key from every dated path it finds, sorts globally oldest
first, and deletes in small increments until either the free-space target
is met or a per-run delete budget is reached — whichever comes first.

Why per-run budget: deleting tens of GB in one pass spikes IO and can stall
the live encoder. Hourly timer + small per-run budget = smooth pressure
relief. The default budget is adaptive: above target → no-op; near target
→ ~1 GB/h (matches sustained write rate); far below target → drains at
gap/10 GB/h up to a 5 GB/h cap.

Never touches today or yesterday (UTC). Within a single date, all
artefacts under that date are grouped; the GC decides per-date, not
per-file (the alternative would risk deleting half an hour and confusing
downstream consumers).

Priority within the same date: rerender first (final MP4s also on S3 + YouTube),
then processed (derivable from raws), then frames (last resort).

Usage:
  file-garbage-collector.py [--dry-run] [--target-gb N] [--budget-gb N]

Env overrides:
  FREE_TARGET_GB   default 50
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from gardencam_paths import (
    FRAMES_ROOT,
    PROCESSED_ROOT,
    RERENDER_ROOT,
    canonical_date_key,
    date_key,
)


# Root → priority (lower = deleted first within the same date).
ROOTS = [
    (RERENDER_ROOT,  0),   # most expendable
    (PROCESSED_ROOT, 1),
    (FRAMES_ROOT,    2),   # last resort
]


def free_gb(path: Path) -> float:
    st = shutil.disk_usage(path)
    return st.free / (1024 ** 3)


def yesterday_key() -> str:
    # date_key() takes a datetime; subtract 1 day in UTC for "yesterday"
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def _flat_yyyymmdd_key(p: Path) -> str | None:
    """Recognise legacy flat YYYYMMDD/ dir names (no dashes) and return
    the canonical YYYY-MM-DD key. Used for ~/skycam-rerender's old
    layout. canonical_date_key() in gardencam_paths only recognises
    YYYY-MM-DD because that's the forward-looking layout; the GC has to
    cope with both."""
    n = p.name
    if len(n) == 8 and n.isdigit():
        y, m, d = n[:4], n[4:6], n[6:8]
        if 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{m}-{d}"
    return None


def _legacy_nested_dated_dirs(year_dir: Path) -> list[tuple[str, Path]]:
    """For a legacy YYYY/ tree, return [(YYYY-MM-DD, day_dir), …]. The
    layout is YYYY/MM/DD/HH/…; we pick the DD level as the deletable unit
    so a whole date is freed as a unit."""
    out: list[tuple[str, Path]] = []
    year = year_dir.name
    if not (len(year) == 4 and year.isdigit()):
        return out
    for month_dir in year_dir.iterdir():
        m = month_dir.name
        if not (m.isdigit() and 1 <= int(m) <= 12 and month_dir.is_dir()):
            continue
        for day_dir in month_dir.iterdir():
            d = day_dir.name
            if not (d.isdigit() and 1 <= int(d) <= 31 and day_dir.is_dir()):
                continue
            out.append((f"{year}-{m.zfill(2)}-{d.zfill(2)}", day_dir))
    return out


def find_dated_candidates() -> tuple[list[tuple[str, int, Path]], list[Path]]:
    """Walk all three roots. Return (candidates, orphans):
      candidates = [(date_key, priority, path), …] — deletable.
      orphans    = [path, …]                       — top-level entries
                                                     under a root that
                                                     don't yield a date key.

    Handles both the canonical flat layout (YYYY-MM-DD under root) and
    legacy nested layouts (YYYY/MM/DD under root) which still exist on
    puppy from pre-2026-05-18.

    Orphans are paths the GC can't reason about — sentinel files like
    .day_rerender_*, sidecar dirs like processed/days/, or anything
    misplaced. They're reported separately so they don't get silently
    ignored."""
    candidates: list[tuple[str, int, Path]] = []
    orphans: list[Path] = []
    for root, priority in ROOTS:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir():
                # Canonical: YYYY-MM-DD directory at the root.
                key = canonical_date_key(child)
                if key is not None:
                    candidates.append((key, priority, child))
                    continue
                # Legacy flat: YYYYMMDD directory (old rerender layout).
                key = _flat_yyyymmdd_key(child)
                if key is not None:
                    candidates.append((key, priority, child))
                    continue
                # Legacy nested: YYYY directory containing MM/DD/…
                legacy = _legacy_nested_dated_dirs(child)
                if legacy:
                    for date, day_dir in legacy:
                        candidates.append((date, priority, day_dir))
                    continue
                orphans.append(child)
            elif child.is_file():
                key = canonical_date_key(child)
                if key is not None:
                    candidates.append((key, priority, child))
                else:
                    orphans.append(child)
    return candidates, orphans


def _summarise_orphans(orphans: list[Path]) -> None:
    """Print a short orphan summary: count, total size, oldest, largest.
    Never lists every orphan."""
    if not orphans:
        return
    now = datetime.now().timestamp()
    rows: list[tuple[Path, int, float]] = []
    for p in orphans:
        try:
            size = path_size_bytes(p)
            mtime = p.stat().st_mtime
        except OSError:
            continue
        rows.append((p, size, mtime))
    if not rows:
        return
    total_bytes = sum(r[1] for r in rows)
    oldest = min(rows, key=lambda r: r[2])
    largest = max(rows, key=lambda r: r[1])
    age_days = (now - oldest[2]) / 86400
    print(f"Orphans (no date key): {len(rows)} items, {total_bytes / 1e9:.2f} GB total")
    print(f"  oldest:  {oldest[0]}  ({age_days:.0f} days old, {oldest[1] / 1e9:.2f} GB)")
    print(f"  largest: {largest[0]}  ({largest[1] / 1e9:.2f} GB)")
    stale = [(p, s, m) for (p, s, m) in rows if (now - m) > 14 * 86400]
    if stale:
        stale_bytes = sum(s for _, s, _ in stale)
        print(f"  {len(stale)} orphans older than 14 days "
              f"({stale_bytes / 1e9:.2f} GB) — may need cleanup")


def path_size_bytes(p: Path) -> int:
    if p.is_file():
        try:
            return p.stat().st_size
        except FileNotFoundError:
            return 0
    total = 0
    for sub in p.rglob("*"):
        try:
            if sub.is_file():
                total += sub.stat().st_size
        except FileNotFoundError:
            pass
    return total


def delete(p: Path, dry_run: bool) -> int:
    """Delete the path and return how many bytes were (or would be) freed."""
    size = path_size_bytes(p)
    if dry_run:
        print(f"  [dry-run] would delete {p}  ({size / 1e9:.2f} GB)")
        return size
    try:
        if p.is_file():
            p.unlink()
        else:
            shutil.rmtree(p)
        print(f"  deleted {p}  ({size / 1e9:.2f} GB)")
    except Exception as e:
        print(f"  failed to delete {p}: {e}", file=sys.stderr)
        return 0
    return size


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be deleted; don't touch the filesystem.")
    ap.add_argument("--target-gb", type=float,
                    default=float(os.environ.get("FREE_TARGET_GB", "50")),
                    help="Stop deleting once free space ≥ this many GB (default 50).")
    ap.add_argument("--budget-gb", type=float, default=None,
                    help="Per-run cap on bytes freed. Default: adaptive — "
                         "scales with how far below target we are.")
    args = ap.parse_args()

    home = Path.home()
    today = date_key()
    yday = yesterday_key()

    free = free_gb(home)

    # Adaptive budget: drain faster the further we are below target.
    # gap < 0: above target, no-op
    # gap < 5 GB: gentle 1 GB/h (matches sustained write rate ~0.5 GB/h plus
    #              headroom — keeps steady state at target without churn)
    # gap >= 5: drain at gap/10 per hour, capped at 5 GB (full backlog
    #            cleared in ~10 hours at the cap)
    if args.budget_gb is None:
        gap = args.target_gb - free
        if gap <= 0:
            budget_gb = 0.0
        else:
            # 1 GB minimum (matches sustained write rate), 5 GB max,
            # gap/10 in between.
            budget_gb = max(1.0, min(5.0, gap / 10))
    else:
        budget_gb = args.budget_gb

    print(f"Target: ≥ {args.target_gb:.0f} GB free on {os.uname().nodename}")
    print(f"Per-run budget: {budget_gb:.2f} GB"
          + (" (adaptive)" if args.budget_gb is None else " (forced)"))
    print(f"Dry run: {args.dry_run}")
    print(f"Preserving: {today} and {yday}")
    print()

    print(f"Currently {free:.1f} GB free.")

    candidates, orphans = find_dated_candidates()
    _summarise_orphans(orphans)

    if free >= args.target_gb:
        print("Already at target, nothing to do.")
        return 0

    # Skip protected dates
    candidates = [c for c in candidates if c[0] not in (today, yday)]
    # Sort: oldest date first, then by priority (0=rerender first).
    candidates.sort(key=lambda c: (c[0], c[1]))

    if not candidates:
        print("Nothing deletable found.")
        return 0

    print(f"{len(candidates)} candidates eligible.")
    budget_bytes = int(budget_gb * 1e9)
    freed = 0
    for date, priority, path in candidates:
        if freed >= budget_bytes:
            print(f"\nBudget reached ({freed / 1e9:.2f} GB ≥ {args.budget_gb} GB), stopping.")
            break
        if free_gb(home) >= args.target_gb:
            print(f"\nTarget met ({free_gb(home):.1f} GB ≥ {args.target_gb} GB), stopping.")
            break
        prio_name = {0: "rerender", 1: "processed", 2: "frames"}.get(priority, "?")
        print(f"[{date} / {prio_name}]")
        freed += delete(path, args.dry_run)

    print()
    print(f"Freed {freed / 1e9:.2f} GB. Now {free_gb(home):.1f} GB free.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
