"""Render fireworks frames to JPEG (one 60 s sub per frame, no stacking).

  render.py v3w   2026-11-05 19:40 20:30 OUTDIR   # publishable: privacy crop, clock, scale bar
  render.py hq16  2026-11-07 17:48 20:12 OUTDIR   # look-only frames for splay

Colour: 2x2 block demosaic (half res), black subtracted, white-balanced on
the median sky of the first frame, ONE fixed asinh stretch for the whole
run so bursts brighten against a steady sky, never re-normalised per frame.
"""
import sys, os, glob, json
import numpy as np, cv2
from astropy.io import fits
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

L = ZoneInfo("Europe/London")
ROOT = "/mnt/muppet/bigstore/eclipticam-frames/night"
cam, night, t0, t1, out = sys.argv[1:6]
os.makedirs(out, exist_ok=True)
sub = {"v3w": "v3w", "hq16": "hq16"}[cam]
BLACK = {"v3w": 64.0, "hq16": 256.0}[cam]
SAT = {"v3w": 1023.0, "hq16": 4095.0}[cam]


def when(p):
    ms = int(os.path.basename(p).split(".")[0])
    return datetime.fromtimestamp(ms / 1000, timezone.utc).astimezone(L)


fs = sorted(glob.glob(f"{ROOT}/{night}/{sub}/*/*.fits.fz"),
            key=lambda p: int(os.path.basename(p).split(".")[0]))
hm = lambda t: t.strftime("%H:%M")
# night dir spans midnight: compare on minutes-after-noon
mn = lambda s: (int(s[:2]) * 60 + int(s[3:5]) - 720) % 1440
fs = [p for p in fs if mn(t0) <= mn(hm(when(p))) <= mn(t1)]
print(f"{len(fs)} frames {cam} {night} {t0}-{t1}", flush=True)


def rgb(p):
    d = fits.getdata(p).astype(np.float32)
    if cam == "hq16" and d.max() > 4096:      # MSB-aligned container
        d /= 16.0
    r = d[0::2, 0::2]; g = 0.5 * (d[0::2, 1::2] + d[1::2, 0::2]); b = d[1::2, 1::2]
    return np.dstack([r, g, b]) - BLACK


ref = rgb(fs[0])
sky = np.median(ref.reshape(-1, 3), axis=0)
wb = sky[1] / np.maximum(sky, 1)              # neutral sky
lo = 0.85 * sky[1]                            # keep a little sky glow
hi = (SAT - BLACK) * 0.9
K = 12.0
print("sky", sky, "wb", wb, flush=True)

meta = []
for i, p in enumerate(fs):
    t = when(p)
    x = rgb(p) * wb
    v = np.clip((x - lo) / (hi - lo), 0, None)
    y = np.arcsinh(K * v) / np.arcsinh(K)
    img = (np.clip(y, 0, 1) * 255).astype(np.uint8)[:, :, ::-1].copy()  # BGR
    if cam == "v3w":
        img = img[:1064]                      # privacy.json publish_keep_top_px (binned)
        h, w = img.shape[:2]
        # scale bar: gnomonic f = 1957.8 full-res px -> 978.9 binned; 10 deg at centre
        bar = int(round(978.9 * np.tan(np.radians(10))))
        x0, y0 = 40, h - 40
        cv2.line(img, (x0, y0), (x0 + bar, y0), (224, 224, 224), 3)
        for xx in (x0, x0 + bar):
            cv2.line(img, (xx, y0 - 10), (xx, y0 + 10), (224, 224, 224), 3)
        cv2.putText(img, "10 deg (field centre)", (x0, y0 - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (224, 224, 224), 2, cv2.LINE_AA)
        label = t.strftime("%a %d %b %Y  %H:%M %Z") + "   60 s exposure"
        cv2.putText(img, label, (w - 820, h - 30), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (224, 224, 224), 2, cv2.LINE_AA)
    name = f"{cam}_{t.strftime('%Y%m%d_%H%M%S')}.jpg"
    cv2.imwrite(os.path.join(out, name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    sat = float((x >= (SAT - BLACK) * 0.98 * wb.min()).mean())
    meta.append({"file": name, "src": p, "london": t.isoformat(), "sat_frac": round(sat, 5)})
    print(name, round(sat, 5), flush=True)
json.dump(meta, open(os.path.join(out, "frames.json"), "w"), indent=1)
