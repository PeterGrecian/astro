"""astro.bayer — read a raw frame at the individual photosite.

Everything above this layer works in demosaiced or luminance space, where
the sensor's 2x green weighting and the 2x2 mosaic have already been
averaged away. That average is exactly what hides undersampling: a star
whose PSF is comparable to the pixel pitch lands on ONE Bayer phase, and
the "missing" colour is not a dead channel, it is a photosite that the
star never illuminated. Telling those two apart — and seeing the
checkerboard aliasing that follows — needs the mosaic left intact.

So these helpers all work in GLOBAL (uncropped) pixel coordinates, and
take the Bayer pattern explicitly. Parity is a property of the sensor
and the capture orientation, not of the crop, and every function here
depends on getting it right:

  RGGB  IMX708 (astrocam v3s, eclipticam v3w)
  SBGGR IMX219 (astrocam v2)
  SGBRG OV5647 (starcam, eclipticam v1)

Note that a 180-degree rotation swaps the diagonal: an RGGB sensor read
out and then stored rotated is BGGR in stored coordinates. The capture
engine rotates in-capture (StreamingConfig.rotation_180), so BAYERPAT in
the header describes the SENSOR, not necessarily the stored array — use
`bin/bayer-parity` to settle it empirically on a real star rather than
trusting the keyword.

ADU scale: these tools assume 10-bit LSB-aligned raw (0..1023), which is
what the whole archive is since the 2026-08 repack (see bin/repack-msb).
A frame carrying RAWSHIFT in its header has already been converted.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

# Bayer channel -> plot colour, shared by every renderer here.
DOT = {"R": "#ff3030", "G": "#20c020", "B": "#3060ff"}

# Sensor -> the top-left 2x2 read row-major. 'S' prefix is "sensor", not
# a colour, and is stripped.
KNOWN_PATTERNS = {"RGGB", "BGGR", "GRBG", "GBRG"}


def open_frame(path) -> tuple[np.ndarray, dict]:
    """Return (float data, header) for a FITS frame, compressed or not."""
    from astropy.io import fits
    with fits.open(path) as hdul:
        hdu = hdul[1] if len(hdul) > 1 and hdul[1].data is not None else hdul[0]
        return hdu.data.astype(float), dict(hdu.header)


def normalise_pattern(pattern: str | None, header: dict | None = None) -> str:
    """Resolve a Bayer pattern from an override or the FITS BAYERPAT."""
    p = pattern or (header or {}).get("BAYERPAT") or "RGGB"
    p = str(p).upper().strip().lstrip("S")
    if len(p) != 4:
        raise ValueError(f"pattern must be 4 letters (got {pattern!r})")
    return p


def bayer_channel(ys, xs, pattern: str = "RGGB") -> np.ndarray:
    """Map GLOBAL pixel coords -> 'R'/'G'/'B' arrays for a 2x2 pattern.

    `pattern` is the top-left 2x2 read ROW-MAJOR: RGGB = (0,0)=R (0,1)=G
    (1,0)=G (1,1)=B. Pass GLOBAL (uncropped) y,x so parity survives the
    crop.
    """
    p = normalise_pattern(pattern)
    cell = {(0, 0): p[0], (0, 1): p[1], (1, 0): p[2], (1, 1): p[3]}
    out = np.empty(np.asarray(ys).shape, dtype="<U1")
    for (dy, dx), c in cell.items():
        out[(ys % 2 == dy) & (xs % 2 == dx)] = c
    return out


def phase_colours(pattern: str = "RGGB") -> dict[tuple[int, int], str]:
    """(y%2, x%2) -> colour letter, for reporting one phase at a time."""
    p = normalise_pattern(pattern)
    return {(0, 0): p[0], (0, 1): p[1], (1, 0): p[2], (1, 1): p[3]}


def phase_mask(y0: int, x0: int, shape, py: int, px: int) -> np.ndarray:
    """Boolean mask of one Bayer phase over a crop with global origin."""
    ys, xs = np.mgrid[y0:y0 + shape[0], x0:x0 + shape[1]]
    return (ys % 2 == py) & (xs % 2 == px)


def assume_white(sub, chan, thresh=0.15, max_gain=4.0, min_signal=0.05):
    """Scale R,B photosites up to G on the bright patch = assume-white.

    Removes the green-dominated checkerboard so the true PSF shows.
    Returns (z, (wb_R, wb_B)). WB ~1.0 means an already-neutral star.

    `sub` is background-subtracted by the caller, so a channel whose
    bright-patch mean is ~0 has essentially NO signal. Balancing it means
    dividing by ~0 -> a giant gain that detonates that channel's noise
    into false bright pixels (seen on a red star: blue ~empty -> WB Bx447
    painted 4 huge blue cells). Two guards:

      min_signal: below this fraction of G the channel is genuinely empty
        (a real colour — a red star has almost no blue), so DON'T balance
        it; leave it dark rather than amplify noise.
      max_gain: never scale by more than this, so even a modestly-weak
        channel can't blow up. A neutral star needs gains ~1; only
        near-empty channels reach the cap, and capping them is correct.
    """
    br = sub > thresh * sub.max()
    m = {c: (sub[br & (chan == c)].mean() if (br & (chan == c)).any() else 0.0)
         for c in "RGB"}
    g = max(m["G"], 1e-6)

    def gain(c):
        if m[c] < min_signal * g:      # genuinely empty: a real colour
            return 1.0
        return min(g / m[c], max_gain)

    wr, wb = gain("R"), gain("B")
    z = sub.copy()
    z[chan == "R"] *= wr
    z[chan == "B"] *= wb
    return np.clip(z, 0, None), (wr, wb)


def assume_white_rgb(rgb, thresh=0.15, max_gain=4.0, min_signal=0.05):
    """assume_white for an already-demosaiced (h, w, 3) image.

    Same guards and the same reasoning as `assume_white` — that function
    works on the mosaic, where each pixel belongs to one channel; this one
    works on separated planes. Returns (balanced, (wb_R, wb_B)).
    """
    lum = rgb.max(axis=2)
    br = lum > thresh * lum.max() if lum.max() > 0 else np.zeros(lum.shape, bool)
    m = {c: (rgb[:, :, i][br].mean() if br.any() else 0.0)
         for i, c in enumerate("RGB")}
    g = max(m["G"], 1e-6)

    def gain(c):
        if m[c] < min_signal * g:      # genuinely empty: a real colour
            return 1.0
        return min(g / m[c], max_gain)

    wr, wb = gain("R"), gain("B")
    out = rgb.copy()
    out[:, :, 0] *= wr
    out[:, :, 2] *= wb
    return np.clip(out, 0, None), (wr, wb)


def local_sky(data, y: int, x: int, box: int = 40) -> float:
    """Median of a box near (x, y), clear of the target itself.

    A global median is fine on a sparse star field but drifts badly near
    a bright source or vignetted corner, and every measurement here is
    "ADU above sky" — so sample locally by default.
    """
    h, w = data.shape
    y0, y1 = max(0, y - box), min(h, y + box)
    x0, x1 = max(0, x - box), min(w, x + box)
    return float(np.median(data[y0:y1, x0:x1]))


def local_sky_by_channel(data, y: int, x: int, box: int = 40,
                         pattern: str = "RGGB") -> dict[str, float]:
    """Median of a nearby box computed SEPARATELY for each colour.

    Use this, not `local_sky`, whenever you report "ADU above sky" per
    channel. The four Bayer phases do not share a background: they differ
    in spectral response and in black level, so on astrocam's IMX708 the
    red photosites sit ~10 ADU below a median taken across all phases at
    once. Subtract that mixed median and red comes out NEGATIVE on a real
    star — which reads exactly like a dead channel and is nothing of the
    sort. Each channel must be measured against its own background.
    """
    h, w = data.shape
    y0, y1 = max(0, y - box), min(h, y + box)
    x0, x1 = max(0, x - box), min(w, x + box)
    crop = data[y0:y1, x0:x1]
    ys, xs = np.mgrid[y0:y1, x0:x1]
    chan = bayer_channel(ys, xs, pattern)
    return {c: (float(np.median(crop[chan == c])) if (chan == c).any()
                else float("nan")) for c in "RGB"}


def channel_peaks(data, y: int, x: int, size: int = 8,
                  sky: dict[str, float] | float | None = None,
                  pattern: str = "RGGB") -> dict[str, float]:
    """Peak ADU above each channel's OWN sky, in a box centred on (x, y)."""
    if sky is None:
        sky = local_sky_by_channel(data, y, x, pattern=pattern)
    if not isinstance(sky, dict):
        sky = {c: float(sky) for c in "RGB"}
    b = size // 2
    y0, x0 = y - b, x - b
    crop = data[y0:y0 + size, x0:x0 + size]
    ys, xs = np.mgrid[y0:y0 + size, x0:x0 + size]
    chan = bayer_channel(ys, xs, pattern)
    out = {}
    for c in "RGB":
        m = chan == c
        out[c] = float(crop[m].max() - sky[c]) if m.any() else float("nan")
    return out


def find_peak(data, y: int, x: int, radius: int = 6) -> tuple[int, int, float]:
    """Brightest pixel within `radius` of (x, y). Returns (x, y, value)."""
    h, w = data.shape
    y0, y1 = max(0, y - radius), min(h, y + radius + 1)
    x0, x1 = max(0, x - radius), min(w, x + radius + 1)
    box = data[y0:y1, x0:x1]
    iy, ix = np.unravel_index(np.argmax(box), box.shape)
    return x0 + int(ix), y0 + int(iy), float(box[iy, ix])


def demosaic_rggb(sub, y0: int, x0: int, pattern: str = "RGGB"):
    """Cheap 2x2-block demosaic of a crop -> (h/2, w/2, 3) RGB.

    One output pixel per Bayer cell — no interpolation, so nothing is
    invented. Halves resolution, which is the honest representation of
    what a single 2x2 cell actually measured.
    """
    # Align the crop to an even global origin so the 2x2 blocks are cells.
    oy, ox = y0 % 2, x0 % 2
    s = sub[oy:, ox:]
    h = (s.shape[0] // 2) * 2
    w = (s.shape[1] // 2) * 2
    s = s[:h, :w]
    cell = phase_colours(pattern)
    quad = {(0, 0): s[0::2, 0::2], (0, 1): s[0::2, 1::2],
            (1, 0): s[1::2, 0::2], (1, 1): s[1::2, 1::2]}
    acc = {"R": [], "G": [], "B": []}
    for ph, arr in quad.items():
        acc[cell[ph]].append(arr)
    rgb = np.zeros((h // 2, w // 2, 3))
    for i, c in enumerate("RGB"):
        rgb[:, :, i] = np.mean(acc[c], axis=0) if acc[c] else 0.0
    return rgb


def render(crop, x0, y0, pattern="RGGB", out="bayer_heatmap.png",
           white=True, threed=True, title=""):
    """Render a raw crop as an intensity heat-map with Bayer-channel dots.

    crop is a 2D raw-mosaic array; (x0, y0) is its global origin.
    white: apply assume-white balance. threed: include the 3D-stem panel.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    h, w = crop.shape
    ys, xs = np.mgrid[y0:y0 + h, x0:x0 + w]
    sub = crop.astype(float) - np.median(crop)
    chan = bayer_channel(ys, xs, pattern)
    if white:
        z, (wr, wb) = assume_white(sub, chan)
    else:
        z, (wr, wb) = np.clip(sub, 0, None), (1.0, 1.0)

    ncol = 2 if threed else 1
    fig = plt.figure(figsize=(9 * ncol, 8))
    col = 1
    if threed:
        ax = fig.add_subplot(1, ncol, col, projection="3d")
        for i in range(h):
            for j in range(w):
                ax.plot([xs[i, j], xs[i, j]], [ys[i, j], ys[i, j]],
                        [0, z[i, j]], color=DOT[chan[i, j]], alpha=0.5, lw=0.9)
        ax.scatter(xs.ravel(), ys.ravel(), z.ravel(),
                   c=[DOT[c] for c in chan.ravel()], s=16,
                   depthshade=False, edgecolors="k", linewidths=0.15)
        ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_zlabel("intensity")
        ax.set_title("3D by Bayer channel")
        ax.view_init(elev=25, azim=-70)
        col += 1

    ax2 = fig.add_subplot(1, ncol, col)
    im = ax2.imshow(z, origin="lower", cmap="inferno", aspect="equal",
                    extent=[x0 - .5, x0 + w - .5, y0 - .5, y0 + h - .5])
    for i in range(h):
        for j in range(w):
            ax2.plot(xs[i, j], ys[i, j], "o", ms=3, color=DOT[chan[i, j]],
                     alpha=0.7, mec="k", mew=0.2)
    ax2.set_title("top-down: intensity + Bayer dots")
    plt.colorbar(im, ax=ax2, shrink=0.7)

    sup = title or "Bayer heat-map"
    fig.suptitle(f"{sup} | WB R x{wr:.2f} B x{wb:.2f} | peak {z.max():.0f}",
                 fontsize=13)
    plt.tight_layout()
    plt.savefig(out, dpi=100)
    plt.close(fig)
    return out, (wr, wb)
