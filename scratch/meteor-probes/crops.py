import os, sys, glob, numpy as np
from astropy.io import fits
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
D = "/mnt/muppet/bigstore/astrocam-frames/2026-10-21/04"
probes = [("1792643225921",2184,1532),("1792643225921",3118,590),
          ("1792643419671",2966,2208),("1792642972751",3471,1586)]
files = sorted(glob.glob(D+"/*.fits.fz")); names=[os.path.basename(f).split(".")[0] for f in files]
def load(n):
    h = fits.open(f"{D}/{n}.fits.fz"); hd=[x for x in h if x.data is not None][0]
    a = hd.data.astype(np.float32)
    if a.ndim==3: a=a.mean(0)
    return a, hd.header
a,h = load(probes[0][0]); print("shape", a.shape, {k:h.get(k) for k in ("EXPTIME","COVER","BAYERPAT","XBINNING","DATE-OBS")})
print("cadence s", np.diff([int(n) for n in names[:6]])/1000)
R=150
rows=[]
for n,x,y in probes:
    i=names.index(n); seq=[names[j] for j in range(i-2,i+3) if 0<=j<len(names)]
    imgs=[load(m)[0] for m in seq]
    # probe coords are on display RES 4608x2592; map to array
    sy=imgs[0].shape[0]/2592; sx=imgs[0].shape[1]/4608
    cx,cy=int(x*sx),int(y*sy); r=int(R*sx)
    crops=[im[max(cy-r,0):cy+r, max(cx-r,0):cx+r] for im in imgs]
    others=[c for m,c in zip(seq,crops) if m!=n]; med=np.median(others,0)
    diff=crops[seq.index(n)]-med
    rows.append((n,x,y,seq,crops,diff))
    s=diff; print(n,x,y,"diff max %.1f  p99.9 %.1f  sky-noise %.1f"%(s.max(),np.percentile(s,99.9),1.4826*np.median(np.abs(s-np.median(s)))))
fig,ax=plt.subplots(len(rows),6,figsize=(18,3.2*len(rows)))
for r_,(n,x,y,seq,crops,diff) in enumerate(rows):
    lo,hi=np.percentile(crops[0],[1,99.7])
    for k in range(5):
        A=ax[r_,k]; A.axis("off")
        if k<len(crops):
            A.imshow(crops[k],cmap="gray",vmin=lo,vmax=hi,origin="upper")
            A.set_title(("*" if seq[k]==n else "")+seq[k][-6:],fontsize=8)
    sd=1.4826*np.median(np.abs(diff-np.median(diff)))
    ax[r_,5].imshow(diff,cmap="gray",vmin=-3*sd,vmax=8*sd); ax[r_,5].axis("off"); ax[r_,5].set_title(f"{n[-6:]} minus nbr median ({x},{y})",fontsize=8)
plt.tight_layout(); out="crops.png"; plt.savefig(out,dpi=70); print(out)
