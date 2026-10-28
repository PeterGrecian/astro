"""For each streak in streaks.json: is anything on its line (extended) in the +/-3 neighbouring subs? And test several Oct shower radiants.
usage: chain.py <night> <hh> <frame-id>...  (run via bigstore-run)"""
import os, sys, json, glob, numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy import ndimage as nd
night, hh, ids = sys.argv[1], sys.argv[2], sys.argv[3:]
D=f"/mnt/muppet/bigstore/astrocam-frames/{night}/{hh}"; out=os.path.expanduser(f"~/tmp/orionids/{night}")
S=json.load(open(f"{out}/streaks.json"))
names=[os.path.basename(f).split(".")[0] for f in sorted(glob.glob(D+"/*.fits.fz"))]
cache={}
def load(n):
    if n not in cache:
        a=fits.getdata(f"{D}/{n}.fits.fz").astype(np.float32); cache[n]=a.reshape(a.shape[0]//2,2,a.shape[1]//2,2).sum((1,3))
    return cache[n]
def diff(n):
    i=names.index(n); nb=[names[j] for j in (i-2,i-1,i+1,i+2) if 0<=j<len(names)]
    d=nd.gaussian_filter(load(n)-np.median([load(m) for m in nb],0),1.5); return d,1.4826*np.median(np.abs(d-np.median(d)))
SHOWERS={"ORI Orionids":(95.0,15.8),"LMI Leonis Minorids":(162.0,37.0),"EGE eps-Geminids":(104.0,27.0),
         "STA S Taurids":(38.0,11.0),"NTA N Taurids":(42.0,19.0)}
def xyz(ra,de): ra,de=np.radians(ra),np.radians(de); return np.array([np.cos(de)*np.cos(ra),np.cos(de)*np.sin(ra),np.sin(de)])
for n in ids:
    w=WCS(fits.getheader(f"{out}/full-{n}.wcs")); i=names.index(n); print(n,S[n]["date"])
    for s in S[n]["streaks"]:
        e1,e2=np.array(s["e1"])/2,np.array(s["e2"])/2; v=(e2-e1)/np.linalg.norm(e2-e1); L=np.linalg.norm(e2-e1)
        sky=[w.all_pix2world([e],0)[0] for e in (e1,e2)]; nrm=np.cross(xyz(*sky[0]),xyz(*sky[1])); nrm/=np.linalg.norm(nrm)
        offs=", ".join(f"{k.split()[0]} {np.degrees(np.arcsin(abs(xyz(*r)@nrm))):.0f}" for k,r in SHOWERS.items())
        line=[]
        for j in range(i-3,i+4):
            if j==i or not 0<=j<len(names): continue
            d,sg=diff(names[j]); H,W=d.shape; t=np.arange(-4*L-200,5*L+200)
            p=(e1[None]+t[:,None]*v[None]).round().astype(int); ok=(p[:,0]>=2)&(p[:,0]<W-2)&(p[:,1]>=2)&(p[:,1]<H-2)
            vals=np.max([d[p[ok,1]+b,p[ok,0]+a] for a,b in [(0,0),(1,0),(-1,0),(0,1),(0,-1)]],0)
            hi=vals>4*sg; seg=max([r[0].stop-r[0].start for r in nd.find_objects(nd.label(hi)[0])] or [0])
            line.append(f"{j-i:+d}:{seg}")
        print(f"   ({s['e1'][0]:.0f},{s['e1'][1]:.0f}) len {2*L:.0f}px peak {s['peak']}  longest >4sig run on its line in subs  {' '.join(line)}  | radiant off-line deg: {offs}")
