"""Orionid sweep over one astrocam night: every sub, single-sub interior streaks, radiant test.
usage: sweep.py <night> [hh ...]   (run via bigstore-run; writes ~/tmp/orionids/<night>/sweep.json)
Pass 1: each sub minus the median of its +/-2 neighbours (2x2 binned), smoothed, elongated blobs > 3 sigma.
Pass 2: a streak is CHAINED (satellite stepping across, or a static edge) if a detection in a sub
within +/-3 lies on the same line; the rest are single-sub. Interior = both ends off the border.
Radiant test: the streak's great circle vs the Orionid radiant (drifting), via one plate solve per night;
pixel -> sky at another time = RA shifted by the sidereal-time difference (fixed camera)."""
import os, sys, glob, json, subprocess, numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from scipy import ndimage as nd
night=sys.argv[1]; hours=[h for h in sys.argv[2:] if not h.startswith('--')]
R=f"/mnt/muppet/bigstore/astrocam-frames/{night}"; out=os.path.expanduser(f"~/tmp/orionids/{night}"); os.makedirs(out,exist_ok=True)
files=sorted(f for h in (hours or sorted(os.listdir(R))) for f in glob.glob(f"{R}/{h}/*.fits.fz"))
files.sort(key=lambda f:os.path.basename(f))
print(night,len(files),"subs",flush=True)
cache={}; hdrs={}
def load(i):
    if i not in cache:
        with fits.open(files[i]) as h:
            a=h[1].data.astype(np.float32); hdrs[i]=h[1].header
        cache[i]=a.reshape(a.shape[0]//2,2,a.shape[1]//2,2).sum((1,3))
    return cache[i]
def is_open(i): return str(hdrs[i].get("COVER","open")).strip().lower()=="open"
det=[]   # per sub: list of streaks
RERANK='--rerank' in sys.argv
if RERANK:
    det=json.load(open(f'{out}/sweep.json'))['subs']; load(0)
for i in ([] if RERANK else range(len(files))):
    for k in [k for k in cache if k<i-2]: del cache[k]
    a=load(i); nb=[j for j in (i-2,i-1,i+1,i+2) if 0<=j<len(files)]
    d=nd.gaussian_filter(a-np.median([load(j) for j in nb],0),1.5); s=1.4826*np.median(np.abs(d-np.median(d)))
    lab,k=nd.label(nd.binary_dilation(d>3*s,iterations=2)); found=[]
    sizes=np.bincount(lab.ravel()); big=np.nonzero(sizes[1:]>=60)[0]+1; k=len(big)
    if k<1500:
        objs=nd.find_objects(lab)
        for n in big:
            sl=objs[n-1]; yy,xx=np.nonzero(lab[sl]==n)
            P=np.c_[xx+sl[1].start,yy+sl[0].start].astype(float); c=P.mean(0)
            u,sv,vt=np.linalg.svd(P-c,full_matrices=False); el=sv[0]/max(sv[1],1e-3); t=(P-c)@vt[0]; L=t.max()-t.min()
            if el<6 or L<30: continue
            v=d[P[:,1].astype(int),P[:,0].astype(int)]
            found.append(dict(e1=(c+t.min()*vt[0]).tolist(),e2=(c+t.max()*vt[0]).tolist(),L=float(L),peak=round(float(v.max()/s),1),
                              snr=round(float(v.mean()/s),1)))
    h=hdrs[i]; det.append(dict(f=os.path.basename(files[i]).split(".")[0],hh=files[i].split("/")[-2],date=h.get("DATE-OBS"),
                               open=is_open(i),nblob=int(k),sigma=round(float(s),2),streaks=found))
    if i%250==0: print(" ",i,h.get("DATE-OBS"),"blobs",k,"streaks",len(found),flush=True)
H,W=cache[max(cache)].shape
BUSY=3*np.median([d['nblob'] for d in det]); print('busy above',BUSY,'big blobs')
def endchain(a,b,tol=25):
    return min(np.hypot(*np.subtract(p,q)) for p in (a["e1"],a["e2"]) for q in (b["e1"],b["e2"]))<tol
def parallel(a,b,angtol=6,dist=900):
    # same object in an adjacent sub that neither chains end to end nor shares a line: a plane, a skipping satellite
    u=np.subtract(a["e2"],a["e1"]); u/=np.linalg.norm(u); w=np.subtract(b["e2"],b["e1"]); w/=np.linalg.norm(w)
    if np.degrees(np.arccos(min(1,abs(u@w))))>angtol: return False
    return np.hypot(*np.subtract(np.add(a["e1"],a["e2"]),np.add(b["e1"],b["e2"]))/2)<dist
def collinear(a,b,tol=6,angtol=3):
    u=np.subtract(a["e2"],a["e1"]); u/=np.linalg.norm(u); w=np.subtract(b["e2"],b["e1"]); w/=np.linalg.norm(w)
    if np.degrees(np.arccos(min(1,abs(u@w))))>angtol: return False
    nrm=np.array([-u[1],u[0]]); return all(abs((np.subtract(p,a["e1"]))@nrm)<tol for p in (b["e1"],b["e2"]))
# plate solve: try subs near the middle of the night until one solves
wcs=None; tsolve=None
for wf in sorted(glob.glob(f"{out}/full-*.wcs")+glob.glob(f"{out}/solve-*.wcs")):
    fid=os.path.basename(wf).split("-",1)[1].split(".")[0]; dd=[d for d in det if d["f"]==fid]
    if dd: wcs=WCS(fits.getheader(wf)); tsolve=Time(dd[0]["date"].replace("+00:00","")); print("reusing solve",fid,dd[0]["date"]); break
for i in ([] if wcs is not None else sorted(range(len(files)),key=lambda j:abs(j-len(files)*0.6))[:60:5]):
    if det[i]["nblob"]>BUSY or not det[i]["open"]: continue
    with fits.open(files[i]) as hh: a=hh[1].data.astype(np.float32)
    a=a.reshape(a.shape[0]//2,2,a.shape[1]//2,2).sum((1,3)); p=f"{out}/solve-{det[i]['f']}.fits"; fits.writeto(p,a,overwrite=True)
    subprocess.run(["solve-field","--overwrite","--no-plots","--scale-units","arcsecperpix","--scale-low","100","--scale-high","150",
                    "--downsample","1","--tweak-order","4","--cpulimit","180","--objs","400","--dir",out,p],capture_output=True)
    wf=p.replace(".fits",".wcs")
    if os.path.exists(wf): wcs=WCS(fits.getheader(wf)); tsolve=Time(det[i]["date"].replace("+00:00","")); print("solved on",det[i]["date"]); break
def xyz(ra,de): ra,de=np.radians(ra),np.radians(de); return np.array([np.cos(de)*np.cos(ra),np.cos(de)*np.sin(ra),np.sin(de)])
# recurrent: a streak whose line matches detections in >=1 other sub anywhere (a sky object cannot land on the same pixels twice) in the night is a fixed feature (foreground, lit edge)
allst=[(i,s) for i,D in enumerate(det) for s in D["streaks"]]
mid=np.array([np.add(s["e1"],s["e2"])/2 for _,s in allst]) if allst else np.zeros((0,2))
def recurrent(i,s):
    m=np.add(s["e1"],s["e2"])/2; near=np.nonzero(np.hypot(*(mid-m).T)<40)[0]
    return len({allst[k][0] for k in near if allst[k][0]!=i and collinear(s,allst[k][1],tol=10,angtol=8)})>=1
cands=[]
for i,D in enumerate(det):
    for s in D["streaks"]:
        chained=any(collinear(s,o) for j in range(max(0,i-3),min(len(det),i+4)) if j!=i for o in det[j]["streaks"]) or \
                any(endchain(s,o) or parallel(s,o) for j in (i-1,i+1) if 0<=j<len(det) for o in det[j]["streaks"]) or \
                any(parallel(s,o) for o in D["streaks"] if o is not s)
        interior=all(min(p[0],W-1-p[0],p[1],H-1-p[1])>8 for p in (s["e1"],s["e2"]))
        if chained or not interior or recurrent(i,s) or not D["open"] or D["nblob"]>BUSY: continue
        c=dict(f=D["f"],hh=D["hh"],date=D["date"],e1=[round(2*x) for x in s["e1"]],e2=[round(2*x) for x in s["e2"]],
               len_px=round(2*s["L"]),peak=s["peak"],snr=s["snr"],nblob=D["nblob"])
        if wcs is not None:
            t=Time(D["date"].replace("+00:00","")); dra=360.98565*(t-tsolve).jd
            sky=[w for w in wcs.all_pix2world([s["e1"],s["e2"]],0)]; sky=[((r+dra)%360,de) for r,de in sky]
            days=(t-Time("2026-10-21T00:00")).jd; rad=(95.5+1.23*days,15.9+0.13*days)
            lst=(280.46061837+360.98564736629*(t.jd-2451545.0)-0.29)%360; ha=np.radians(lst-rad[0]); la=np.radians(51.39)
            c["rad_alt"]=round(float(np.degrees(np.arcsin(np.sin(la)*np.sin(np.radians(rad[1]))+np.cos(la)*np.cos(np.radians(rad[1]))*np.cos(ha)))),1)
            v1,v2=xyz(*sky[0]),xyz(*sky[1]); nrm=np.cross(v1,v2); nrm/=np.linalg.norm(nrm); r=xyz(*rad)
            c.update(sky=[[round(x,2) for x in p] for p in sky],len_deg=round(float(np.degrees(np.arccos(np.clip(v1@v2,-1,1)))),2),
                     rad_off=round(float(np.degrees(np.arcsin(abs(r@nrm)))),1),
                     rad_dist=[round(float(np.degrees(np.arccos(np.clip(r@v,-1,1)))),1) for v in (v1,v2)])
        cands.append(c)
json.dump(dict(night=night,nsubs=len(det),solved=wcs is not None,subs=det,cands=cands),open(f"{out}/sweep.json","w"))
nopen=sum(d["open"] for d in det); busy=sum(d["nblob"]>BUSY for d in det)
print(f"\n{night}: {len(det)} subs, {nopen} open, {busy} busy (cloud/noise), {sum(len(d['streaks']) for d in det)} streaks, {len(cands)} single-sub interior candidates")
for c in sorted(cands,key=lambda c:c.get("rad_off",99)):
    print(f"  {c['date'][:19]} {c['f']} ({c['e1'][0]},{c['e1'][1]})->({c['e2'][0]},{c['e2'][1]}) {c['len_px']}px {c.get('len_deg','?')}deg "
          f"peak {c['peak']} snr {c['snr']}  ORI off-line {c.get('rad_off','?')} dist {c.get('rad_dist','?')} radalt {c.get('rad_alt','?')}")
