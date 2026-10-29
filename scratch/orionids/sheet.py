"""Contact sheet of sweep candidates: each row = prev sub / this sub / next sub (neighbour-median difference), streak centred.
usage: sheet.py <night> [maxoff=15] [n=24]   (reads ~/tmp/orionids/<night>/sweep.json; run via bigstore-run)"""
import os, sys, glob, json, numpy as np
from astropy.io import fits
from scipy import ndimage as nd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
night=sys.argv[1]; maxoff=float(sys.argv[2]) if len(sys.argv)>2 else 15; N=int(sys.argv[3]) if len(sys.argv)>3 else 24
R=f"/mnt/muppet/bigstore/astrocam-frames/{night}"; out=os.path.expanduser(f"~/tmp/orionids/{night}")
J=json.load(open(f"{out}/sweep.json")); files=sorted(glob.glob(f"{R}/*/*.fits.fz"),key=os.path.basename)
idx={os.path.basename(f).split(".")[0]:i for i,f in enumerate(files)}
C=sorted([c for c in J["cands"] if c.get("rad_off",99)<=maxoff],key=lambda c:c["rad_off"])[:N]
def load(i):
    a=fits.getdata(files[i]).astype(np.float32); return a.reshape(a.shape[0]//2,2,a.shape[1]//2,2).sum((1,3))
def diff(i):
    nb=[j for j in (i-2,i-1,i+1,i+2) if 0<=j<len(files)]; return nd.gaussian_filter(load(i)-np.median([load(j) for j in nb],0),1)
fig,ax=plt.subplots(len(C),3,figsize=(9,3*len(C)),squeeze=False)
for r,c in enumerate(C):
    i=idx[c["f"]]; m=(np.add(c["e1"],c["e2"])/4).astype(int); h=max(60,int(c["len_px"]/2*0.75))
    for k,j in enumerate((i-1,i,i+1)):
        a=ax[r][k]; a.axis("off")
        if not 0<=j<len(files): continue
        d=diff(j); y0,x0=max(m[1]-h,0),max(m[0]-h,0); cr=d[y0:m[1]+h,x0:m[0]+h]; s=1.4826*np.median(np.abs(cr-np.median(cr)))
        a.imshow(cr,cmap="gray",vmin=-2*s,vmax=8*s,origin="upper")
        if k==1: a.set_title(f"{c['date'][11:19]}  ORI {c['rad_off']}°  {c['len_deg']}°  pk {c['peak']}",fontsize=8)
        else: a.set_title("prev" if k==0 else "next",fontsize=8)
fig.tight_layout(); fig.savefig(f"{out}/sheet.png",dpi=80); print(f"{out}/sheet.png",len(C),"rows")
