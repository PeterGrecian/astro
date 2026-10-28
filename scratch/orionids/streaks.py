"""All streaks in a few astrocam subs (neighbour-median difference), plus a plate solve of a central crop.
usage: streaks.py <night> <hh> <frame-id>...   (run via bigstore-run)"""
import os, sys, glob, subprocess, json, numpy as np
from astropy.io import fits
from scipy import ndimage as nd
night, hh, ids = sys.argv[1], sys.argv[2], sys.argv[3:]
D=f"/mnt/muppet/bigstore/astrocam-frames/{night}/{hh}"
names=[os.path.basename(f).split(".")[0] for f in sorted(glob.glob(D+"/*.fits.fz"))]
out=os.path.expanduser(f"~/tmp/orionids/{night}"); os.makedirs(out,exist_ok=True)
cache={}
def load(n):
    if n not in cache:
        a=fits.getdata(f"{D}/{n}.fits.fz").astype(np.float32)
        cache[n]=a.reshape(a.shape[0]//2,2,a.shape[1]//2,2).sum((1,3))
    return cache[n]
def diff(n):
    i=names.index(n); nb=[names[j] for j in (i-2,i-1,i+1,i+2) if 0<=j<len(names)]
    d=load(n)-np.median([load(m) for m in nb],0)
    d=nd.median_filter(d,3)
    s=1.4826*np.median(np.abs(d-np.median(d)))
    return d,s
res={}
for n in ids:
    d,s=diff(n); hdr=fits.getheader(f"{D}/{n}.fits.fz",1)
    # matched filter along lines is overkill: smooth then threshold low, keep elongated blobs
    ds=nd.gaussian_filter(d,1.5); ss=1.4826*np.median(np.abs(ds-np.median(ds)))
    m=nd.binary_dilation(ds>3*ss,iterations=2); lab,k=nd.label(m)
    found=[]
    for i,sl in enumerate(nd.find_objects(lab),1):
        yy,xx=np.nonzero(lab[sl]==i); 
        if len(yy)<60: continue
        P=np.c_[xx+sl[1].start,yy+sl[0].start].astype(float); c=P.mean(0)
        u,sv,vt=np.linalg.svd(P-c,full_matrices=False); el=sv[0]/max(sv[1],1e-3)
        t=(P-c)@vt[0]; L=t.max()-t.min()
        if el<6 or L<30: continue
        e1=c+t.min()*vt[0]; e2=c+t.max()*vt[0]
        # brightness profile along the streak in 10 bins
        bins=np.linspace(t.min(),t.max(),11); v=ds[P[:,1].astype(int),P[:,0].astype(int)]
        prof=[round(float(v[(t>=bins[j])&(t<=bins[j+1])].mean()/ss),1) for j in range(10)]
        found.append(dict(e1=(2*e1).round().tolist(),e2=(2*e2).round().tolist(),len_full=round(2*L),elong=round(el,1),
                          ang=round(np.degrees(np.arctan2(vt[0][1],vt[0][0]))%180,1),peak=round(float(v.max()/ss),1),prof=prof))
    found.sort(key=lambda f:-f["len_full"])
    res[n]=dict(date=hdr.get("DATE-OBS"),exp=hdr.get("EXPTIME"),streaks=found[:12])
    np.save(f"{out}/diff-{n}.npy",ds.astype(np.float32))
    print(n,hdr.get("DATE-OBS"),"exp",hdr.get("EXPTIME"),"sigma",round(float(ss),2))
    for f in found[:12]: print("  ",f)
# plate solve: central 1100x1100 binned crop of the first frame, as a FITS image
n=ids[0]; a=load(n); H,W=a.shape; cy,cx=H//2,W//2
crop=a[cy-550:cy+550,cx-550:cx+550]
p=f"{out}/crop-{n}.fits"; fits.writeto(p,crop,overwrite=True)
r=subprocess.run(["solve-field","--overwrite","--no-plots","--scale-units","arcsecperpix","--scale-low","40","--scale-high","300",
                  "--downsample","1","--tweak-order","3","--cpulimit","120","--dir",out,p],capture_output=True,text=True)
print(r.stdout[-1500:]); print("crop origin binned",cx-550,cy-550)
json.dump(res,open(f"{out}/streaks.json","w"),indent=1)
