import os, numpy as np, cv2
paths = [
    "/home/peter/starcam-frames/night/raw/2026-05-21/00/1779321801078.npy",
    "/home/peter/starcam-frames/night/raw/2026-05-21/00/1779321804139.npy",
    "/home/peter/starcam-frames/night/raw/2026-05-21/00/1779321828679.npy",
    "/home/peter/starcam-frames/night/raw/2026-05-21/00/1779322098569.npy",
]
# Also render a normal neighbour for comparison
normal = "/home/peter/starcam-frames/night/raw/2026-05-21/00/1779321795000.npy"
import glob
# Pick the file closest to but not in the outlier set
candidates = sorted(glob.glob("/home/peter/starcam-frames/night/raw/2026-05-21/00/*.npy"))
# Find one between two outliers
outliers = set(os.path.basename(p) for p in paths)
normals = [c for c in candidates if os.path.basename(c) not in outliers
           and "17793218" in os.path.basename(c)]
paths.append(normals[len(normals)//2])

for p in paths:
    arr = np.load(p).astype(np.float32)
    print(f"{os.path.basename(p)}: min={arr.min():.0f} max={arr.max():.0f} "
          f"mean={arr.mean():.3f} p99.9={np.percentile(arr, 99.9):.1f} "
          f"bright(>=100)={(arr>=100).sum()}")
    # Stretch generously to see anything faint
    stretched = np.clip(arr * 10.0, 0, 255).astype(np.uint8)
    out = f"/home/peter/tmp/starcam-night/2026-05-20-21/outlier_{os.path.basename(p).replace('.npy','.jpg')}"
    cv2.imwrite(out, stretched, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"  wrote {out}")
