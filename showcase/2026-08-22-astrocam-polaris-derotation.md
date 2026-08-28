---
id: 2026-08-22-astrocam-polaris-derotation
title: Four Hours Around the Celestial Pole
category: derotated
target: Polaris & Northern Polar Alignment
constellation: Ursa Minor / Cepheus
featured: false
date: 2026-08-22
time: "02:40 BST"
camera: astrocam
night: 2026-08-22
equipment:
  optics: Raspberry Pi Camera Module v2 (3.04mm lens)
  focal_length: 3.04mm
  f_ratio: f/2.0
  sensor: Sony IMX219 (8.08 MP 1/4" CMOS)
  mount: North-Facing Fixed Housing
  filter: None
exposure:
  subs: 240
  sub_time: 60s
  total_integration: 4h 00m
  iso_gain: Analogue Gain 12.0
  bortle: Class 6 (Suburban)
source:
  image: "astrocam-frames/night/2026-08-22/polar_derot.jpg"
  combine: derot-median
  stretch: {fn: asinh, gain: 3.2, hi_pct: 99.7}
---

# Caption

A four-hour continuous stack derotated around the true North Celestial Pole. By continuously counter-rotating every one-minute sub-exposure by the sidereal rate before stacking, Polaris resolves into its tiny 0.7-degree offset orbit while surrounding background stars integrate into pinpoints.

# Observation & Processing

Acquired automatically by the astrocam daemon over 240 consecutive one-minute exposures. The pivot centre was solved globally via non-linear least squares on star arcs across the entire night. Each tile was transformed with bicubic interpolation to rotate out Earth's rotation, then summed using variance weighting against the darkest contiguous window of the night.

# Technical Highlights

- Global LSQ pole fit resolves true rotation axis to ±0.04 pixels
- Dynamic frame gating: anchors stack against the darkest 10-minute window of the night
- Continuous streaming tile derotation pipeline avoids loading whole night dataset into RAM
- Pinpoint star reconstruction down to magnitude +7.2 in suburban skies
