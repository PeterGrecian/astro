---
id: 2026-08-20-canon-cygnus-milky-way
title: Cygnus and the Northern Cross in Summer
category: deep-sky
target: NGC 7000 / Deneb / Sadr Region
constellation: Cygnus
featured: true
date: 2026-08-20
time: "23:15 BST"
camera: canon
night: 2026-08-20
equipment:
  optics: Canon EF 50mm f/1.8 STM
  focal_length: 50mm
  f_ratio: f/2.8
  sensor: Canon EOS 2000D (24.1 MP APS-C CMOS)
  mount: Heavy Fixed Tripod
  filter: Stock Internal UV/IR Cut
exposure:
  subs: 40
  sub_time: 30s
  total_integration: 20m
  iso_gain: ISO 1600
  bortle: Class 6 (Suburban, SQM ~19.4)
source:
  image: "canon-frames/night/2026-08-20/cygnus_preview.jpg"
  combine: median
  stretch: {fn: asinh, gain: 4.0, hi_pct: 99.8}
---

# Caption

A rich widefield view across Cygnus cutting through the star clouds of the summer Milky Way. Bright Deneb shines at the top, anchoring the Northern Cross, with the crimson glow of the North America Nebula (NGC 7000) emerging along the Great Rift.

# Observation & Processing

Captured on a fixed mount using short 30-second sub-exposures to control sidereal trailing before stacking. The individual raw CR2 files were converted with bad-pixel masking (MAD hot/cold map) to eliminate sensor artefacts. Star centroids were computed and aligned with sub-pixel affine registration, followed by kappa-sigma median clipping to reject aircraft strobes and low-orbit satellite reflections. Background sky gradient was modelled with a 2D polynomial surface and subtracted, followed by a non-linear asinh stretch to preserve star colour while bringing out faint interstellar dust lanes.

# Technical Highlights

- 40 × 30s light frames registered with sub-pixel affine transformation (RMS alignment error < 0.18 px)
- 2D polynomial background sky gradient subtraction to remove suburban light pollution floor
- Asinh non-linear luminance stretch preserves star core saturation without chromatic blooming
- Kappa-sigma outlier rejection completely cleans 3 crossing aircraft tracks without manual painting
