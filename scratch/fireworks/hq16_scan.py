"""Per-frame brightness stats for eclipticam hq16 (colour IMX477) to find fireworks."""
import sys, glob, os, numpy as np
from astropy.io import fits
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
L = ZoneInfo("Europe/London")
root = "/mnt/muppet/bigstore/eclipticam-frames/night"
for night in sys.argv[1:]:
    fs = sorted(glob.glob(f"{root}/{night}/hq16/*/*.fits.fz"), key=lambda p: int(os.path.basename(p).split('.')[0]))
    print(f"# {night} {len(fs)} frames", flush=True)
    for f in fs:
        ms = int(os.path.basename(f).split('.')[0])
        t = datetime.fromtimestamp(ms/1000, timezone.utc).astimezone(L)
        try:
            d = fits.getdata(f).astype(np.float32)
        except Exception as e:
            print(night, t.strftime('%H:%M'), "ERR", e, flush=True); continue
        s = d[::4, ::4]
        print(night, t.strftime('%H:%M:%S'), ms, f"{np.median(s):.0f} {np.percentile(s,99):.0f} {np.percentile(s,99.9):.0f} {s.max():.0f} {(d>=4000).sum()}", flush=True)
