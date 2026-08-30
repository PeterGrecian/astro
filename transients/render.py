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


def demosaic_bayer(sub: np.ndarray, pattern: str = "RGGB") -> np.ndarray:
    """Demosaic raw Bayer crop to float32 (H, W, 3) RGB array."""
    try:
        import cv2
        p = pattern.upper().strip().lstrip("S")
        # OpenCV Bayer code names: RGGB -> COLOR_BayerRG2RGB, BGGR -> COLOR_BayerBG2RGB, etc.
        cv_name = f"COLOR_Bayer{p[:2]}2RGB"
        code = getattr(cv2, cv_name, cv2.COLOR_BayerRG2RGB)
        sub_u16 = np.clip(sub, 0, 65535).astype(np.uint16)
        return cv2.cvtColor(sub_u16, code).astype(np.float32)
    except Exception:
        # Fallback if cv2 is not available: 2x2 cell demosaic
        oy, ox = 0, 0
        h = (sub.shape[0] // 2) * 2
        w = (sub.shape[1] // 2) * 2
        s = sub[:h, :w]
        r = s[0::2, 0::2]
        g = 0.5 * (s[0::2, 1::2] + s[1::2, 0::2])
        b = s[1::2, 1::2]
        rgb_half = np.stack([r, g, b], axis=-1)
        from PIL import Image as _Img
        return np.array(_Img.fromarray(rgb_half.astype(np.uint8)).resize((w, h), _Img.BILINEAR)).astype(np.float32)


def render(card: dict, root: Path):
    from PIL import Image
    src = card["source"]
    x0, y0, x1, y1 = (int(v) for v in src["crop"])
    stretch = src.get("stretch") or {}
    gain = float(stretch.get("gain", 6.0))
    hi = float(stretch.get("hi_pct", 99.9))
    scale = int(src.get("scale", 1))
    demosaic = src.get("demosaic", True)  # default to RGB demosaic for raw Bayer
    pattern = src.get("pattern", "RGGB")

    arrs = load(src["frames"], root)
    a = arrs[0] if len(arrs) == 1 else np.maximum.reduce(arrs)
    sub = a[y0:y1, x0:x1]

    if demosaic:
        rgb = demosaic_bayer(sub, pattern)
        bg = np.median(rgb, axis=(0, 1))
        d = np.clip(rgb - bg, 0, None)
        v = np.arcsinh(d / gain)
        hi_val = np.percentile(v, hi)
        v = np.clip(v / max(1e-6, hi_val), 0, 1)
        img = Image.fromarray((v * 255).astype(np.uint8))
    else:
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
