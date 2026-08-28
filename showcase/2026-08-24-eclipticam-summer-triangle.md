---
id: 2026-08-24-eclipticam-summer-triangle
title: Summer Triangle and the Ecliptic Sweep
category: milky-way
target: Vega, Altair, Deneb & Ecliptic Corridor
constellation: Lyra / Aquila / Cygnus
featured: false
date: 2026-08-24
time: "01:10 BST"
camera: eclipticam
night: 2026-08-24
equipment:
  optics: 120-Degree Wide Angle Lens
  focal_length: 2.8mm
  f_ratio: f/2.2
  sensor: Sony IMX708 Wide (12 MP CMOS)
  mount: South-Facing Ecliptic Bracket
  filter: Anti-Reflective Optical Glass
exposure:
  subs: 120
  sub_time: 60s
  total_integration: 2h 00m
  iso_gain: Analogue Gain 8.0
  bortle: Class 6 (Suburban)
source:
  image: "eclipticam-frames/night/2026-08-24/ecliptic_sweep.jpg"
  combine: max
  stretch: {fn: asinh, gain: 5.0, hi_pct: 99.5}
---

# Caption

Widefield 120-degree landscape sweep capturing the Summer Triangle — Vega in Lyra, Altair in Aquila, and Deneb in Cygnus — bridging the southern sky along the celestial equator and ecliptic path.

# Observation & Processing

Streamed by the dual-sensor Eclipticam v3w system. The wide-angle IMX708 sensor captures an expansive chunk of the southern meridian. 120 sixty-second sub-exposures were max-stacked to visualize stellar motion along the celestial equator while preserving foreground rooftop silhouette references.

# Technical Highlights

- 120° diagonal field of view with optical distortion polynomial correction
- Real-time frame quality monitoring via streaming brightness telemetry
- High-dynamic-range max-pixel accumulation reveals subtle constellation paths
