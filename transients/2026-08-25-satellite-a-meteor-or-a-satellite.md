---
id: 2026-08-25-satellite-a-meteor-or-a-satellite
title: Almost certainly a satellite
category: satellite
confidence: likely
date: 2026-08-25
time: "04:48 BST"
camera: eclipticam
night: 2026-08-24
source:
  frames:
    - eclipticam-frames/night/2026-08-24/v3w/03/1787629684508.fits.fz
  combine: single
  crop: [2800, 200, 4608, 1900]   # x0, y0, x1, y1 in full-res sensor pixels
  stretch: {fn: arcsinh, gain: 5.0, hi_pct: 99.9}
  scale: 2
  demosaic: true
---

# Caption

A clean, straight trail spanning 44 degrees across the sky, captured in a single 60-second exposure low in the west.

It is almost certainly a satellite because the crossing happens at the right time of night when satellites in orbit catch the rising sun while the sky remains dark, and the 44-degree length shows rapid crossing. However, because it appears in only one single exposure rather than stepping across consecutive frames, it is not possible to completely rule out a much faster but unusually long meteor.

