#!/usr/bin/env python3
"""render.py — generate or export the showcase photo from card recipe.

    render.py <card.md> [--out PATH] [--root DIR]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
import numpy as np


def parse_card(path: Path) -> dict:
    import yaml
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit(f"{path}: no front matter")
    meta = yaml.safe_load(m.group(1)) or {}
    if "source" not in meta:
        raise SystemExit(f"{path}: no source: block")
    return meta


def load_fits(frames, root: Path):
    from astropy.io import fits
    out = []
    for f in frames:
        p = root / f if root else Path(f)
        if not p.exists():
            raise SystemExit(f"missing frame: {p}")
        out.append(fits.open(p)[1].data.astype(np.float32))
    return out


def render(card: dict, root: Path):
    from PIL import Image
    src = card["source"]

    # Direct image path or crop
    if "image" in src:
        img_path = root / src["image"] if root else Path(src["image"])
        if not img_path.exists():
            # Fallback to current directory or placeholder
            img_path = Path(src["image"])
        if img_path.exists():
            img = Image.open(img_path)
            if "crop" in src:
                x0, y0, x1, y1 = (int(v) for v in src["crop"])
                img = img.crop((x0, y0, x1, y1))
            return img.convert("RGB")

    # FITS frames processing
    if "frames" in src and src["frames"]:
        frames = src["frames"]
        arrs = load_fits(frames, root)
        combine = src.get("combine", "median")
        if combine == "median" and len(arrs) > 1:
            a = np.median(arrs, axis=0)
        elif combine == "max":
            a = np.maximum.reduce(arrs)
        else:
            a = arrs[0]

        if "crop" in src:
            x0, y0, x1, y1 = (int(v) for v in src["crop"])
            sub = a[y0:y1, x0:x1]
        else:
            sub = a

        stretch = src.get("stretch") or {}
        gain = float(stretch.get("gain", 4.0))
        hi = float(stretch.get("hi_pct", 99.9))
        d = np.clip(sub - np.median(sub), 0, None)
        v = np.arcsinh(d / gain)
        v = v / (np.percentile(v, hi) or 1.0)
        img = Image.fromarray((np.clip(v, 0, 1) * 255).astype(np.uint8)).convert("RGB")
        scale = int(src.get("scale", 1))
        if scale != 1:
            img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
        return img

    # Fallback placeholder image if no local raw data present
    from PIL import ImageDraw
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), color=(10, 12, 20))
    d = ImageDraw.Draw(img)
    title = card.get("title", "Astro Photo")
    d.text((w // 2, h // 2), f"{title}\n(Render from recipe)", fill=(200, 220, 255), anchor="mm")
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("card", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--root", type=Path, default=Path.home())
    args = ap.parse_args()

    card = parse_card(args.card)
    img = render(card, args.root)
    out = args.out or args.card.with_suffix(".png")
    img.save(out)
    print(f"{out}  {img.width}x{img.height}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
