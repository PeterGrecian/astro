"""Does the foreground move between nights? Best block shift of each night's sky mask vs a reference night."""
import sys, numpy as np
ref = np.load(sys.argv[1])["sky"].astype(float)
for f in sys.argv[2:]:
    m = np.load(f)["sky"].astype(float); best = None
    for dy in range(-6, 7):
        for dx in range(-6, 7):
            s = (np.roll(m, (dy, dx), (0, 1))[6:-6, 6:-6] == ref[6:-6, 6:-6]).mean()
            if best is None or s > best[0]: best = (s, dx, dy)
    same = (m[6:-6, 6:-6] == ref[6:-6, 6:-6]).mean()
    print(f.split("/")[-2], "agree unshifted %.3f, best %.3f at block shift (%+d,%+d) (24 px blocks)" % (same, *best))
