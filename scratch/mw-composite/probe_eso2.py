#!/usr/bin/env python3
"""eso0932a geometry by search: plate carree in galactic, centre l0, direction sgn (+1 = l increases to the
left), vertical offset db. Score = summed local-peak brightness at 26 bright stars' predicted pixels."""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
Image.MAX_IMAGE_PIXELS = None
a = np.asarray(Image.open("/home/peter/tmp/mwcomp/dl/eso0932a.jpg").convert("L")).astype(np.float32); Hh, Ww = a.shape
s = ndi.maximum_filter(a, 5) - ndi.median_filter(a[::1, ::1], 25)    # point-source contrast
ST = [(227.23, -8.89), (261.21, -25.29), (15.06, 69.11), (67.45, 19.24), (162.59, 4.57), (209.24, -25.25), (199.79, -8.96),
      (351.95, 15.06), (316.11, 50.84), (84.28, 1.99), (47.74, -8.91), (290.84, -58.79), (311.77, -0.68), (315.73, -0.68),
      (213.70, 12.97), (195.97, -71.89), (180.63, -4.04), (198.12, -29.09), (196.95, 58.71), (165.05, 67.72),
      (21.49, 69.50), (232.72, -55.61), (194.48, 42.97), (303.02, 26.92), (236.50, -46.37), (339.38, -20.14)]
L, B = np.array(ST).T
best = []
for sgn in (1, -1):
    for l0 in np.arange(-30, 30.01, 0.5):
        for db in np.arange(-6, 6.01, 0.5):
            x = Ww / 2 - sgn * (((L - l0 + 180) % 360) - 180) / 360 * Ww; y = Hh / 2 - (B - db) / 180 * Hh
            ok = (x >= 0) & (x < Ww) & (y >= 0) & (y < Hh)
            best.append((s[y[ok].astype(int), x[ok].astype(int)].mean(), sgn, l0, db))
best.sort(reverse=True); print("top:", [(round(b[0], 1), b[1], b[2], b[3]) for b in best[:5]], " median score", round(float(np.median([b[0] for b in best])), 1))
sc, sgn, l0, db = best[0]
for l0f in np.arange(l0 - 0.5, l0 + 0.51, 0.1):
    for dbf in np.arange(db - 0.5, db + 0.51, 0.1):
        x = Ww / 2 - sgn * (((L - l0f + 180) % 360) - 180) / 360 * Ww; y = Hh / 2 - (B - dbf) / 180 * Hh
        best.append((s[y.astype(int).clip(0, Hh - 1), x.astype(int) % Ww].mean(), sgn, round(l0f, 2), round(dbf, 2)))
best.sort(reverse=True); print("refined:", best[0])
