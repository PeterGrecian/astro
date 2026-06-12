"""Bayer pattern registry per sensor.

The fleet mixes patterns — a recurring source of bugs (SGBRG vs SRGGB
vs SBGGR). New code should look patterns up here (or better, from the
camera's camera.json via astro.config) rather than hard-coding.

Note: rawpy reports OV5647 DNGs as GRBG after its own rotation; the
true raw stream out of picamera2 is SGBRG10. Trust the stream/registry,
not rawpy, when debayering picamera2 output.
"""

# sensor -> packed 10-bit raw format name (libcamera/picamera2 convention)
SENSOR_RAW_FORMAT = {
    "OV5647": "SGBRG10",   # Pi Camera v1 (starcam, eclipticam-v1)
    "IMX219": "SBGGR10",   # Pi Camera v2 (astrocam)
    "IMX708": "SRGGB10",   # Pi Camera 3 Wide (eclipticam-v3w)
}


def pattern(raw_format: str) -> str:
    """4-letter Bayer pattern from a raw format name, e.g. SGBRG10 -> GBRG."""
    s = raw_format.upper().lstrip("S")
    for n in (10, 12, 8, 16):
        s = s.removesuffix(str(n))
    if len(s) != 4 or set(s) - set("RGB"):
        raise ValueError(f"can't parse Bayer pattern from {raw_format!r}")
    return s


def for_sensor(sensor: str) -> str:
    """4-letter Bayer pattern for a sensor name."""
    return pattern(SENSOR_RAW_FORMAT[sensor.upper()])


def bin2x2(arr):
    """2x2 sum-bin a Bayer mosaic into grey superpixels (one full RGGB
    quad per output pixel). This is what deliverables are derived from —
    stacking/derotating the raw mosaic leaves a Bayer checkerboard and
    mixes Bayer phases under interpolation. Sum (not mean) to preserve
    integer photon counts, matching bin-frames. Output uint16 when the
    sums fit (10-bit sources always do), else uint32."""
    import numpy as np
    H, W = arr.shape
    b = arr[:H - H % 2, :W - W % 2].reshape(
        H // 2, 2, W // 2, 2).sum(axis=(1, 3), dtype=np.uint32)
    if b.max() <= 65535:
        return b.astype(np.uint16)
    return b


def bin2x2_rgb(arr, pattern: str):
    """Split a Bayer mosaic into 3 colour planes by stride-2 slicing,
    summing the two greens. Output shape (H/2, W/2, 3), one full
    RGGB quad per pixel — same shape as bin2x2() but RGB.

    For video / colour visualisation only. Stacking and the science
    pipeline always use grey bin2x2.
    """
    import numpy as np
    H, W = arr.shape
    a = arr[:H - H % 2, :W - W % 2]
    off = plane_offsets(pattern)
    def _plane(rc):
        r, c = rc
        return a[r::2, c::2]
    r = _plane(off["R"])
    g = _plane(off["G1"]).astype(np.uint32) + _plane(off["G2"])
    b = _plane(off["B"])
    out = np.empty((r.shape[0], r.shape[1], 3), dtype=np.uint32)
    out[..., 0] = r
    out[..., 1] = g
    out[..., 2] = b
    return out


def plane_offsets(pat: str) -> dict:
    """Map plane name -> (row_offset, col_offset) for a 4-letter pattern.
    Green planes are named G1 (first in reading order) and G2."""
    pat = pat.upper()
    out = {}
    g_seen = 0
    for i, ch in enumerate(pat):
        rc = (i // 2, i % 2)
        if ch == "G":
            g_seen += 1
            out[f"G{g_seen}"] = rc
        else:
            out[ch] = rc
    return out
