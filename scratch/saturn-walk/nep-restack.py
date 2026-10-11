#!/usr/bin/env python3
"""Re-stack Neptune nights onto neptune.py's current patch WITHOUT refitting:
the per-frame pointing (az0, alt0, roll, f, t_mid) is already in the records of
an earlier stack, so each usable frame is only loaded and re-projected.

    python nep-restack.py nep-narrow     # reads <dir>/*.npz, writes nep/<night>.npz
"""
import glob, json, os, sys
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np
from scipy.ndimage import map_coordinates

HERE = os.path.expanduser("~/astro/scratch/saturn-walk")
sys.path.insert(0, HERE)
import check3                                                    # noqa: E402
import neptune as N                                              # noqa: E402
from check3 import BASE, LOC, P, model, _enu                     # noqa: E402
from astropy.coordinates import AltAz, GCRS, SkyCoord            # noqa: E402
from astropy.time import Time                                    # noqa: E402
import astropy.units as u                                        # noqa: E402


def one(args):
    night, r = args
    t0 = datetime.fromtimestamp(int(r["frame"].split(".")[0]) / 1000, timezone.utc)
    img, _ = check3.load(f"{BASE}/{night}/v3w/{t0:%H}/{r['frame']}")
    tm = Time(datetime.fromisoformat(r["t_mid"]))
    sky = SkyCoord(N.RA.ravel() * u.deg, N.DEC.ravel() * u.deg, frame=GCRS(obstime=tm))
    aa = sky.transform_to(AltAz(obstime=tm, location=LOC, pressure=0))
    x, y = model(dict(P, az0=r["az0"], alt0=r["alt0"], roll=r["roll"], f=r["f"])).project(
        _enu(np.radians(aa.az.deg), np.radians(aa.alt.deg)))
    return map_coordinates(img, [y, x], order=1, cval=np.nan).reshape(N.GH, N.GW).astype(np.float32)


def main():
    src = sys.argv[1]
    os.makedirs(N.OUTD, exist_ok=True)
    with Pool(6) as pool:
        for p in sorted(glob.glob(f"{HERE}/{src}/*.npz")):
            night = os.path.basename(p)[:-4]
            recs = json.loads(str(np.load(p)["recs"]))
            use = [r for r in recs if "noise" in r]
            patches = pool.map(one, [(night, r) for r in use], chunksize=4)
            S, Wsum = N.stack(patches, [r["noise"] for r in use])
            np.savez_compressed(f"{N.OUTD}/{night}.npz", stack=S, weight=Wsum, n=len(patches),
                                recs=json.dumps(recs, default=float), ra0=N.RA0, dec0=N.DEC0, scale=N.SCALE)
            print(f"{night}: {len(patches)} frames re-projected", flush=True)


if __name__ == "__main__":
    main()
