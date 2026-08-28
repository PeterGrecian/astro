#!/usr/bin/env python3
"""render.py — rebuild a transient's image from the recipe in its card file.

WHY THE IMAGE IS NOT IN GIT
---------------------------
A card's picture is derived: a crop of one or two raw subs, sky-subtracted and
asinh-stretched. Keep the JPEG and lose the recipe and you can never re-crop or
re-stretch for a different layout; keep the recipe and lose the JPEG and you
type one command. The FITS is the archive, the picture is a build artefact --
the same call the accumulator design already makes about raw frames.

So each card carries a `source:` block naming its frames, crop, stretch and
scale, and this reproduces the published image byte-for-byte-ish from it.

    render.py <card.md> [--out PATH] [--root DIR]

`--root` is where the camera frame trees live (default: the camera's own
frames_root as resolved by astro.config, so this works on the capture host and
on a workstation with the export mounted).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np


def parse_card(path: Path) -> dict:
    """Front matter of a card file, as a dict.

    Real YAML, not a hand parser, because Front Matter CMS (VS Code) rewrites
    these files when a field is edited in its UI — reordering keys, normalising
    inline maps, dropping comments. A tolerant parser here is what lets the
    dashboard and this script share one file without fighting.
    """
    import yaml
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit(f"{path}: no front matter")
    meta = yaml.safe_load(m.group(1)) or {}
    if "source" not in meta:
        raise SystemExit(f"{path}: no source: block — nothing to render from")
    return meta


def load(frames, root: Path):
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
    x0, y0, x1, y1 = (int(v) for v in src["crop"])
    stretch = src.get("stretch") or {}
    gain = float(stretch.get("gain", 6.0))
    hi = float(stretch.get("hi_pct", 99.9))
    scale = int(src.get("scale", 1))

    arrs = load(src["frames"], root)
    a = arrs[0] if len(arrs) == 1 else np.maximum.reduce(arrs)
    sub = a[y0:y1, x0:x1]
    d = np.clip(sub - np.median(sub), 0, None)
    v = np.arcsinh(d / gain)
    v = v / np.percentile(v, hi)
    img = Image.fromarray((np.clip(v, 0, 1) * 255).astype(np.uint8)).convert("RGB")
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("card", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--root", type=Path, default=Path.home(),
                    help="directory the source paths are relative to "
                         "(default: $HOME, where the frame trees live)")
    args = ap.parse_args()

    card = parse_card(args.card)
    img = render(card, args.root)
    out = args.out or args.card.with_suffix(".png")
    img.save(out)
    print(f"{out}  {img.width}x{img.height}  from {len(card['source']['frames'])} frame(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
