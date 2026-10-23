import os, glob, numpy as np
from astropy.io import fits
from scipy import ndimage as nd
D="/mnt/muppet/bigstore/astrocam-frames/2026-10-21/04"
names=[os.path.basename(f).split(".")[0] for f in sorted(glob.glob(D+"/*.fits.fz"))]
probes=[("1792643225921",2184,1532),("1792643225921",3118,590),("1792643419671",2966,2208),("1792642972751",3471,1586)]
cache={}
def load(n):
    if n not in cache:
        a=fits.getdata(f"{D}/{n}.fits.fz").astype(np.float32)
        # 2x2 bin the Bayer mosaic -> 1296x2304 luminance
        cache[n]=a.reshape(a.shape[0]//2,2,a.shape[1]//2,2).sum((1,3))
    return cache[n]
def diff(n):
    i=names.index(n); nb=[names[j] for j in (i-2,i-1,i+1,i+2) if 0<=j<len(names)]
    d=load(n)-np.median([load(m) for m in nb],0)
    d=nd.median_filter(d,3)
    s=np.std(np.clip(d,*np.percentile(d,[5,95])))
    return d,s
def streak(n,px,py,tol=60):
    d,s=diff(n); m=d>4*s
    m=nd.binary_dilation(m,iterations=2)
    lab,_=nd.label(m); x,y=px//2,py//2
    win=lab[max(y-tol,0):y+tol,max(x-tol,0):x+tol]; ids=[i for i in np.unique(win) if i]
    if not ids: return None
    best=max(ids,key=lambda i:(lab==i).sum()); yy,xx=np.nonzero(lab==best)
    P=np.c_[xx,yy].astype(float); c=P.mean(0); u,sv,vt=np.linalg.svd(P-c,full_matrices=False)
    t=(P-c)@vt[0]; e1=c+t.min()*vt[0]; e2=c+t.max()*vt[0]
    H,W=d.shape; touch=any(min(e[0],W-1-e[0],e[1],H-1-e[1])<8 for e in (e1,e2))
    ang=np.degrees(np.arctan2(vt[0][1],vt[0][0]))%180
    prof=d[yy,xx]; 
    return dict(len=2*(t.max()-t.min()),ang=round(ang,1),e1=(2*e1).round().astype(int).tolist(),e2=(2*e2).round().astype(int).tolist(),
                width=round(2*sv[1]/np.sqrt(len(P))*np.sqrt(12),1),elong=round(sv[0]/sv[1],1),touches_border=touch,peak_sigma=round(prof.max()/s,1),npx=len(P),line=(c,vt[0]))
def on_line(n,c,v,s_thr=4):
    # does neighbouring frame n carry a streak along the same line (satellite moves along its own track)?
    d,s=diff(n); H,W=d.shape; t=np.arange(-3000,3000)
    pts=(c[None]+t[:,None]*v[None]).round().astype(int); ok=(pts[:,0]>=2)&(pts[:,0]<W-2)&(pts[:,1]>=2)&(pts[:,1]<H-2); pts=pts[ok]
    vals=np.max([d[pts[:,1]+o[1],pts[:,0]+o[0]] for o in [(0,0),(1,0),(-1,0),(0,1),(0,-1)]],0)
    hi=vals>s_thr*s; return int(hi.sum()), len(vals)
for n,x,y in probes:
    r=streak(n,x,y); print(f"\n{n} probe ({x},{y}) {fits.getheader(f'{D}/{n}.fits.fz',1).get('DATE-OBS')}")
    if not r: print("  no streak above 4 sigma near probe"); continue
    c,v=r.pop("line"); print("  ",r)
    i=names.index(n)
    for j in (i-1,i+1):
        if 0<=j<len(names): print(f"   along-track pixels >4sig in {names[j][-6:]}: %d of %d"%on_line(names[j],c,v), " (self: %d of %d)"%on_line(n,c,v))
