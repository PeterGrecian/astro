#!/usr/bin/env python3
"""One-shot: normalise today's skycam frames to 1296x728.

For each frame found under the legacy and new paths, ensure there's a
1296x728 RGB JPEG at ~/skycam-frames/day/2026-05-18/HH/{epoch_ms}_day.jpg.

Sources handled:
  - ~/skycam-frames/2026/05/18/{HH}/*.jpg    (legacy 2592x1944 4:3) → top-16:9 crop + LANCZOS resize
  - ~/skycam-frames/day/2026-05-18/{HH}/*.jpg sized 1280x720         → LANCZOS upscale to 1296x728
  - ~/skycam-frames/day/2026-05-18/{HH}/*.jpg already 1296x728       → no-op
Idempotent: skips when dest exists and is the right size.
"""
from pathlib import Path
from PIL import Image
import sys

TARGET = (1296, 728)
JPEG_QUALITY = 90
DATE = "2026-05-18"
LEGACY_ROOT = Path.home() / "skycam-frames" / "2026" / "05" / "18"
NEW_ROOT    = Path.home() / "skycam-frames" / "day" / DATE


def crop_top_16x9(img):
    w, h = img.size
    crop_h = (w * 9 + 15) // 16
    return img if crop_h >= h else img.crop((0, 0, w, crop_h))


def ensure(img_path: Path, dest_path: Path) -> str:
    """Return verdict: 'skip'|'wrote'|'failed'."""
    if dest_path.exists():
        try:
            with Image.open(dest_path) as d:
                if d.size == TARGET:
                    return "skip"
        except Exception:
            pass  # treat as needs rewrite
    try:
        img = Image.open(img_path).convert("RGB")
    except Exception as e:
        print(f"  ERR open {img_path}: {e}", file=sys.stderr)
        return "failed"
    if img.size != TARGET:
        # If 4:3-ish, top-crop first
        w, h = img.size
        if h * 16 > w * 9:  # taller than 16:9
            img = crop_top_16x9(img)
        if img.size != TARGET:
            img = img.resize(TARGET, Image.Resampling.LANCZOS)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest_path, "JPEG", quality=JPEG_QUALITY)
    return "wrote"


def main():
    total = {"skip": 0, "wrote": 0, "failed": 0}
    by_hour = {}

    # Legacy path frames (hours 00..09 typically)
    if LEGACY_ROOT.is_dir():
        for hour_dir in sorted(LEGACY_ROOT.iterdir()):
            if not hour_dir.is_dir() or len(hour_dir.name) != 2:
                continue
            hh = hour_dir.name
            dest_dir = NEW_ROOT / hh
            for src in sorted(hour_dir.iterdir()):
                if not src.name.endswith(".jpg"):
                    continue
                dest = dest_dir / src.name
                v = ensure(src, dest)
                total[v] += 1
                by_hour.setdefault(hh, {"skip":0,"wrote":0,"failed":0})[v] += 1
            print(f"  legacy hour {hh}: {by_hour.get(hh, {})}")

    # New path: anything 1280x720 needs upscaling
    if NEW_ROOT.is_dir():
        for hour_dir in sorted(NEW_ROOT.iterdir()):
            if not hour_dir.is_dir() or len(hour_dir.name) != 2:
                continue
            hh = hour_dir.name
            hour_stats = {"skip":0,"wrote":0,"failed":0}
            for src in sorted(hour_dir.iterdir()):
                if not src.name.endswith(".jpg"):
                    continue
                try:
                    with Image.open(src) as img:
                        if img.size == TARGET:
                            hour_stats["skip"] += 1
                            continue
                except Exception as e:
                    print(f"  ERR open {src}: {e}", file=sys.stderr)
                    hour_stats["failed"] += 1
                    continue
                v = ensure(src, src)  # in-place rewrite
                hour_stats[v] += 1
                total[v] += 1
            if any(hour_stats.values()):
                print(f"  new hour {hh}: {hour_stats}")

    print(f"\nTOTAL: {total}")


if __name__ == "__main__":
    main()
