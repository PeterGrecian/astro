"""Plate-solve a whole binned astrocam sub, then test each streak's great circle against the Orionid radiant.
usage: radiant.py <night> <hh> <frame-id> [<frame-id>...]  (streaks.json from streaks.py; run via bigstore-run)"""
import os, sys, json, subprocess, numpy as np
from astropy.io import fits
from astropy.wcs import WCS
night, hh, ids = sys.argv[1], sys.argv[2], sys.argv[3:]
D=f"/mnt/muppet/bigstore/astrocam-frames/{night}/{hh}"; out=os.path.expanduser(f"~/tmp/orionids/{night}")
S=json.load(open(f"{out}/streaks.json"))
RAD=(95.0,15.8)   # Orionid radiant ~Oct 21-22 (IMO: 6h20m +16)
def xyz(ra,de): ra,de=np.radians(ra),np.radians(de); return np.array([np.cos(de)*np.cos(ra),np.cos(de)*np.sin(ra),np.sin(de)])
r=xyz(*RAD)
for n in ids:
    a=fits.getdata(f"{D}/{n}.fits.fz").astype(np.float32); a=a.reshape(a.shape[0]//2,2,a.shape[1]//2,2).sum((1,3))
    p=f"{out}/full-{n}.fits"; wcsf=f"{out}/full-{n}.wcs"
    if not os.path.exists(wcsf):
        fits.writeto(p,a,overwrite=True)
        subprocess.run(["solve-field","--overwrite","--no-plots","--scale-units","arcsecperpix","--scale-low","100","--scale-high","150",
                        "--downsample","1","--tweak-order","4","--cpulimit","180","--objs","400","--dir",out,p],capture_output=True)
    if not os.path.exists(wcsf): print(n,"full frame did not solve"); continue
    w=WCS(fits.getheader(wcsf))
    print(n,S[n]["date"])
    for s in S[n]["streaks"]:
        e=[np.array(s["e1"])/2,np.array(s["e2"])/2]
        sky=[w.all_pix2world([[x,y]],0)[0] for x,y in e]
        v1,v2=xyz(*sky[0]),xyz(*sky[1]); nrm=np.cross(v1,v2); nrm/=np.linalg.norm(nrm)
        off=np.degrees(np.arcsin(abs(r@nrm)))                    # radiant distance from the streak's great circle
        d1,d2=[np.degrees(np.arccos(np.clip(r@v,-1,1))) for v in (v1,v2)]
        arc=np.degrees(np.arccos(np.clip(v1@v2,-1,1)))
        print(f"   ({s['e1'][0]:.0f},{s['e1'][1]:.0f})->({s['e2'][0]:.0f},{s['e2'][1]:.0f}) len {arc:.1f} deg  "
              f"radiant {off:.1f} deg off its line; ends {d1:.0f}/{d2:.0f} deg from radiant  peak {s['peak']}  "
              f"RA/Dec {sky[0][0]:.1f},{sky[0][1]:.1f} -> {sky[1][0]:.1f},{sky[1][1]:.1f}")
