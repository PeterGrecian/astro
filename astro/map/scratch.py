#!/usr/bin/env python3
"""map-scratch — low-resolution scratch pass over the archive.

Peter, 2026-08-13: "we should start doing scratch runs. low resolution
accumulations. coarse buckets for sorting good pixels from bad."

WHY LOW RESOLUTION FIRST. The theory (capacity law, TDI, drizzle) is settled;
what is NOT settled is the plumbing — the walk, the epoch split, the derived-
product exclusion, the projection, the bucket thresholds. Every error this
project has hit today was in the plumbing, not the maths: a night-level
sum.fits.fz counted as a frame, a nested metadata tree mistaken for the data,
a meteor threshold guessed from three frames that scored 1/38. A decimated pass
exercises all of that at 1/64 the pixels, so a mistake costs minutes.

It also fixes the thresholds problem the honest way: coarse buckets derived
from the WHOLE archive beat fine buckets guessed from a handful of frames.

MEASURED COST (muppet, local disk, 2026-08-13):
    full read              0.15 s/frame  -> ~3.7 h for 88,415 frames
    .section[::8,::8]      0.09 s/frame  -> ~2.2 h      <-- what this uses
    header only            0.002 s/frame -> ~3 min
  (the same read over pip's wifi mount is 1.65 s -> ~40 h. Compute follows the
  data: this MUST run on muppet.)

.section is the point: it reads a strided slice without materialising the full
array, so decimation is a saving in TIME, not only memory.

WHAT IT EMITS: one row per frame into a sidecar CSV (astro-storage's "derived,
regenerable" class). No accumulation yet — this pass exists to decide the
buckets, and to be the archive-wide integrity scrub astro-storage asked for.

HOUSE RULES OBSERVED:
  - resolvable via astro-where; never hand-roll a date glob (astrocam has TWO
    trees and the nested one is empty metadata)
  - FITS only from depth 3, two-digit hour dirs; night-level FITS are DERIVED
    (sum.fits.fz is an already-accumulated night stack)
  - do not follow symlinks (latest-astrocam points off bigstore)
  - nice/ionice at the caller; resumable per night; log bad reads, never repair
"""
import argparse
import csv
import os
import sys
import time

import numpy as np
from astropy.io import fits

DECIMATE = 8


def hour_dirs(night_dir):
    """Two-digit children only. Everything else at the night level is derived."""
    try:
        names = sorted(os.listdir(night_dir))
    except OSError:
        return []
    out = []
    for n in names:
        if len(n) == 2 and n.isdigit():
            p = os.path.join(night_dir, n)
            if os.path.isdir(p) and not os.path.islink(p):
                out.append(p)
    return out


def frames_in(night_dir):
    fs = []
    for h in hour_dirs(night_dir):
        for n in sorted(os.listdir(h)):
            if n.endswith(".fits.fz") or n.endswith(".fits"):
                p = os.path.join(h, n)
                if not os.path.islink(p):
                    fs.append(p)
    return fs


def measure(path):
    """Coarse per-frame quality signals from a decimated read."""
    with fits.open(path, memmap=False) as hd:
        hdu = hd[1] if len(hd) > 1 else hd[0]
        hdr = hdu.header
        small = np.asarray(hdu.section[::DECIMATE, ::DECIMATE], dtype=np.float32)

    med = float(np.median(small))
    p99 = float(np.percentile(small, 99))
    # Coarse "good pixels vs bad": saturated / dead fractions, and how much
    # structure sits above the sky floor. Deliberately cheap and robust —
    # these choose BUCKETS, they are not science measurements.
    hi = float((small >= 1020).mean())
    lo = float((small <= 1).mean())
    mad = float(np.median(np.abs(small - med)))
    return {
        "median": round(med, 2),
        "p99": round(p99, 2),
        "mad": round(mad, 3),
        "contrast": round((p99 - med) / max(mad, 1e-3), 2),
        "sat_frac": round(hi, 6),
        "dead_frac": round(lo, 6),
        "exptime": hdr.get("EXPTIME"),
        "gain": hdr.get("GAIN"),
        "date_obs": str(hdr.get("DATE-OBS", "")),
        "camera_hdr": str(hdr.get("CAMERA", "")),
        "posindex": hdr.get("POSINDEX"),
        "naxis1": hdr.get("NAXIS1"),
        "naxis2": hdr.get("NAXIS2"),
        "bayer": str(hdr.get("BAYERPAT", "")),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="e.g. /mnt/bigstore/astro-data/astrocam-frames")
    ap.add_argument("--out", required=True, help="sidecar CSV (one row per frame)")
    ap.add_argument("--nights", default=None, help="comma list; default = all date dirs")
    ap.add_argument("--limit-frames", type=int, default=0, help="per night, 0 = all")
    args = ap.parse_args()

    if args.nights:
        nights = args.nights.split(",")
    else:
        nights = sorted(n for n in os.listdir(args.root)
                        if len(n) == 10 and n[4] == "-" and n[7] == "-")

    # Resumable: skip nights already present in the CSV.
    done = set()
    if os.path.exists(args.out):
        with open(args.out) as fh:
            for row in csv.DictReader(fh):
                done.add(row["night"])
        print(f"resuming: {len(done)} night(s) already done", flush=True)

    fields = ["night", "camera", "path", "median", "p99", "mad", "contrast",
              "sat_frac", "dead_frac", "exptime", "gain", "date_obs",
              "camera_hdr", "posindex", "naxis1", "naxis2", "bayer"]
    new = not os.path.exists(args.out)
    fh = open(args.out, "a", newline="")
    w = csv.DictWriter(fh, fieldnames=fields)
    if new:
        w.writeheader()

    badlog = args.out + ".badreads"
    camera = os.path.basename(args.root.rstrip("/")).replace("-frames", "")
    t_all = time.time()
    n_ok = n_bad = 0

    for night in nights:
        if night in done:
            continue
        nd = os.path.join(args.root, night)
        fs = frames_in(nd)
        if args.limit_frames:
            fs = fs[:args.limit_frames]
        if not fs:
            print(f"{night}: 0 frames (empty or products-only)", flush=True)
            continue
        t0 = time.time()
        for p in fs:
            try:
                row = measure(p)
            except Exception as e:                      # log, never repair
                n_bad += 1
                with open(badlog, "a") as bl:
                    bl.write(f"{night}\t{camera}\t{p}\t{type(e).__name__}: {e}\n")
                continue
            row.update(night=night, camera=camera, path=p)
            w.writerow(row)
            n_ok += 1
        fh.flush()                                      # checkpoint per night
        dt = time.time() - t0
        print(f"{night}: {len(fs)} frames in {dt:.1f}s "
              f"({dt/max(len(fs),1)*1000:.0f} ms/frame)", flush=True)

    fh.close()
    print(f"\n{n_ok} frames measured, {n_bad} bad reads, "
          f"{time.time()-t_all:.0f}s total -> {args.out}")
    if n_bad:
        print(f"bad reads logged to {badlog}")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Sample selection — "thin in time, exhaustive in sources" (Peter, 2026-08-13)
# ---------------------------------------------------------------------------

def select_nights(nights, every_days=7, per_epoch=True, epoch_of=None):
    """Thin a night list to ~weekly, but keep EVERY epoch represented.

    Peter: "start with images from each epoch, maybe at weekly intervals, maybe
    just for the midnight hour, to cut the iteration time down. But still be
    exhaustive of the data sources."

    So: thin the TIME axis hard, keep the SOURCE axis complete. An epoch with
    only a few nights must still contribute — thinning must never silently drop
    a whole calibration epoch, which is exactly the boundary the map must not
    co-add across.
    """
    if not nights:
        return []
    nights = sorted(nights)
    if not per_epoch or epoch_of is None:
        keep, last = [], None
        for n in nights:
            if last is None or _days_between(last, n) >= every_days:
                keep.append(n)
                last = n
        return keep

    by_epoch = {}
    for n in nights:
        by_epoch.setdefault(epoch_of(n), []).append(n)
    keep = []
    for ep, ns in sorted(by_epoch.items(), key=lambda kv: str(kv[0])):
        sub, last = [], None
        for n in sorted(ns):
            if last is None or _days_between(last, n) >= every_days:
                sub.append(n)
                last = n
        # never drop an epoch entirely, however short it is
        if not sub and ns:
            sub = [sorted(ns)[0]]
        keep.extend(sub)
    return sorted(keep)


def _days_between(a, b):
    from datetime import date
    ya, ma, da = (int(x) for x in a.split("-"))
    yb, mb, db = (int(x) for x in b.split("-"))
    return (date(yb, mb, db) - date(ya, ma, da)).days


def midnight_hours(night_dir, hours=("23", "00", "01")):
    """Hour dirs near local midnight — the darkest, most comparable slice.

    CAVEAT (measured 2026-08-13): sampling one clock hour weekly advances
    SIDEREAL phase only ~28 min/week (3.93 min/day). Over a full YEAR that
    sweeps 23.9 h — effectively complete phase coverage — but over this
    archive's ~9 weeks it is only ~4.1 h. So a midnight-only sample is fine for
    plumbing, buckets and photometry, but the tree-vs-star SIDEREAL-PHASE test
    stays weak until the baseline is long. Use all hours when testing that.
    """
    out = []
    for h in hour_dirs(night_dir):
        if os.path.basename(h) in hours:
            out.append(h)
    return out
