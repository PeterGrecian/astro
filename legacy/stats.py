import glob, os, time
import numpy as np
files = sorted(glob.glob("/home/peter/starcam-frames/night/raw/*/*/*.npy"))
print(f"total: {len(files)}")
target = files[-2]
print(f"latest stable: {target}")
print(f"  mtime: {time.strftime('%H:%M:%S', time.gmtime(os.path.getmtime(target)))} UTC")
arr = np.load(target)
print(f"  shape: {arr.shape} dtype={arr.dtype}")
print(f"  min={int(arr.min())}  max={int(arr.max())}  mean={arr.mean():.2f}  median={int(np.median(arr))}")
print(f"  stdev={arr.std():.2f}")
c = arr[472:1472, 796:1796]
print(f"  centre 1000x1000:  min={int(c.min())} max={int(c.max())} mean={c.mean():.2f} median={int(np.median(c))}")
bright = int((arr > 500).sum())
sat = int((arr >= 1023).sum())
print(f"  bright (>500):     {bright:>8d} ({100*bright/arr.size:.3f}%)")
print(f"  saturated (=1023): {sat:>8d} ({100*sat/arr.size:.4f}%)")
