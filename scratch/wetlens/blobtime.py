"""Blob region / neighbour region background ratio, frame by frame, to time a droplet's arrival."""
import os, sys, glob, datetime, numpy as np
from astropy.io import fits
root = os.environ["BIGSTORE"] + "/astrocam-frames"
for n in sys.argv[1:]:
    for p in sorted(glob.glob(f"{root}/{n}/[0-2][0-9]/*.fits.fz"))[::60]:
        with fits.open(p) as h:
            for x in h:
                if x.data is not None: d = x.data.astype(np.float32); hdr = x.header; break
        if d.ndim == 3: d = d.mean(axis=0) if d.shape[0] <= 4 else d.mean(axis=2)
        blob = np.median(d[0:430, 4030:4608]); nb = np.median(d[0:430, 3260:3840]); mid = np.median(d[1100:1500, 2000:2600])
        t = datetime.datetime.fromtimestamp(int(os.path.basename(p).split(".")[0]) / 1000, datetime.UTC)
        print(t.strftime("%m-%d %H:%M"), hdr.get("COVER", "-"), f"blob/nbr {blob/nb:5.3f}  nbr/mid {nb/mid:5.3f}  sky {mid:6.1f}")
