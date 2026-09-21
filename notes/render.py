#!/usr/bin/env python3
"""render.py — rebuild a field note's figures from the recipe in its card.

Same call the Transients gallery makes (astro/transients/render.py), for the
same reason: the picture is a BUILD ARTEFACT and the recipe is the thing worth
keeping. Lose the JPEG and you type one command; lose the recipe and you can
never re-crop, re-stretch or re-scale for a different layout.

What is different here is the input. A transient is a crop of one or two raw
Bayer subs, so that renderer demosaics. A field note's figures are usually
DERIVED arrays — a de-rotated coadd, a pole-centred polar strip, a count map —
already mono, already binned, and often enormous (the 2026-09-20 strip is
1619 x 22561). So this renderer:

  * reads plain image FITS (any HDU with 2-D data — primary or first image
    extension), no Bayer assumptions;
  * takes an optional crop, an asinh or linear stretch over percentile clips,
    and a scale factor that may be FRACTIONAL, because these arrays get
    reduced far more often than enlarged;
  * accepts an ordinary PNG/JPEG too, so a screen grab can be a figure
    without inventing a second path for it.

Recipe, in the card's front matter:

    figures:
      - src: ~/tmp/derot/preview-mean.fits
        caption: 600 frames de-rotated and coadded
        crop: [200, 200, 1100, 900]        # x0, y0, x1, y1, optional
        stretch: {fn: asinh, gain: 4.0, lo_pct: 30, hi_pct: 99.7}
        scale: 0.5                          # optional, may be < 1

`src` is resolved against --root (default $HOME) when relative, and ~ is
expanded. NOTHING here writes to S3 — that is bin/add-note's job.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

# The stretch defaults. lo_pct is not 0: these arrays are mostly empty sky and
# a floor at the true minimum wastes the bottom third of the ramp on noise.
DEFAULTS = {"fn": "asinh", "gain": 4.0, "lo_pct": 25.0, "hi_pct": 99.7}


def parse_card(path: Path) -> dict:
    """Front matter of a card file, as a dict.

    Real YAML rather than a hand parser, for the reason the transients
    renderer gives: an editor that rewrites front matter (Front Matter CMS)
    reorders keys and normalises inline maps, and a tolerant parser is what
    lets a dashboard and a script share one file without fighting.
    """
    import yaml
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit(f"{path}: no front matter")
    meta = yaml.safe_load(m.group(1)) or {}
    for required in ("id", "title", "instrument", "date"):
        if not meta.get(required):
            raise SystemExit(f"{path}: front matter has no {required}:")
    return meta


def resolve(src: str, root: Path) -> Path:
    p = Path(str(src)).expanduser()
    return p if p.is_absolute() else (root / p)


def load_array(path: Path) -> np.ndarray:
    """2-D float32 array from a FITS file (first HDU that has one)."""
    from astropy.io import fits
    with fits.open(path) as hdul:
        for hdu in hdul:
            data = getattr(hdu, "data", None)
            if data is not None and getattr(data, "ndim", 0) == 2:
                return data.astype(np.float32)
    raise SystemExit(f"{path}: no 2-D image data in any HDU")


def stretch_array(a: np.ndarray, spec: dict) -> np.ndarray:
    """Percentile-clipped asinh (or linear) stretch to 0..1 floats."""
    s = dict(DEFAULTS)
    s.update(spec or {})
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return np.zeros_like(a)
    lo = float(np.percentile(finite, float(s["lo_pct"])))
    hi = float(np.percentile(finite, float(s["hi_pct"])))
    d = np.clip(np.nan_to_num(a, nan=lo) - lo, 0, None)
    span = max(hi - lo, 1e-6)
    if str(s["fn"]).lower() == "linear":
        v = d / span
    else:
        gain = max(float(s["gain"]), 1e-6)
        v = np.arcsinh(d / (span / gain)) / np.arcsinh(gain)
    return np.clip(v, 0, 1)


def render_figure(fig: dict, root: Path):
    """One figure recipe -> a PIL RGB image."""
    from PIL import Image
    src = resolve(fig["src"], root)
    if not src.exists():
        raise SystemExit(f"missing figure source: {src}")

    if src.suffix.lower() in (".fits", ".fit", ".fz"):
        a = load_array(src)
        if fig.get("crop"):
            x0, y0, x1, y1 = (int(v) for v in fig["crop"])
            a = a[y0:y1, x0:x1]
        v = stretch_array(a, fig.get("stretch"))
        img = Image.fromarray((v * 255).astype(np.uint8)).convert("RGB")
    else:
        img = Image.open(src).convert("RGB")
        if fig.get("crop"):
            x0, y0, x1, y1 = (int(v) for v in fig["crop"])
            img = img.crop((x0, y0, x1, y1))

    scale = float(fig.get("scale", 1) or 1)
    if scale != 1:
        w = max(1, round(img.width * scale))
        h = max(1, round(img.height * scale))
        img = img.resize((w, h), Image.LANCZOS)
    return img


def render_all(card: dict, root: Path):
    """[(figure_dict, PIL image)] for every figure in the card, in order."""
    return [(f, render_figure(f, root)) for f in (card.get("figures") or [])]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("card", type=Path)
    ap.add_argument("--root", type=Path, default=Path.home(),
                    help="base for relative figure sources (default: $HOME)")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="write <id>-<n>.jpg previews here instead of just "
                         "reporting what would be rendered")
    args = ap.parse_args()

    card = parse_card(args.card)
    figures = render_all(card, args.root)
    if not figures:
        print(f"{args.card}: no figures: block — nothing to render")
        return 0
    for i, (fig, img) in enumerate(figures, 1):
        line = f"  figure {i}: {img.width}x{img.height}  {fig['src']}"
        if args.out_dir:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            dst = args.out_dir / f"{card['id']}-{i}.jpg"
            img.save(dst, "JPEG", quality=90, optimize=True)
            line += f"  -> {dst}"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
