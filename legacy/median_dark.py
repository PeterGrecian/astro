import numpy as np, glob, os, time
files = sorted(glob.glob("/home/peter/starcam-frames/night/raw/*/*/*.npy"))
dark = []
for f in files:
    mt = time.gmtime(os.path.getmtime(f))
    if 23 <= mt.tm_hour or mt.tm_hour < 2:
        dark.append(f)
sample = dark[::35][:100]
stack = np.stack([np.load(f) for f in sample])
print(f"stack shape: {stack.shape}")
median_frame = np.median(stack, axis=0)
print(f"median: min={median_frame.min()} max={median_frame.max()} mean={median_frame.mean():.2f}")
for thr in (10, 20, 30, 50, 100):
    n = int((median_frame > thr).sum())
    print(f"  px with median > {thr}: {n}")
print("top 10 brightest median values:")
flat = median_frame.flatten()
top = np.argsort(-flat)[:10]
for i in top:
    y, x = i // 2592, i % 2592
    print(f"  ({x:4d}, {y:4d}) median={flat[i]:.1f}")
np.save("/home/peter/tmp/starcam-night/2026-05-20-21/median_dark_frame.npy", median_frame)
print("saved median_dark_frame.npy")
