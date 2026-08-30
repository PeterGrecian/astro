---
id: 2026-08-26-satellite-fading-into-shadow
title: Satellite rising into the sunlight
category: satellite
confidence: confirmed
date: 2026-08-26
time: "04:14 BST"
camera: eclipticam
night: 2026-08-25
source:
  frames:
    - eclipticam-frames/night/2026-08-25/v3w/03/1787714061176.fits.fz
    - eclipticam-frames/night/2026-08-25/v3w/03/1787714121085.fits.fz
  combine: max
  crop: [3560, 880, 4360, 1880]   # x0, y0, x1, y1 in full-res sensor pixels
  stretch: {fn: arcsinh, gain: 6.0, hi_pct: 99.97}
  scale: 2
---

# Caption

Rising out of the treeline into open sky, caught across two consecutive 60-second exposures combined in the image. The satellite first appears at 03:14:21 as it catches the pre dawn sun and fades out in the next minute as the reflected light then misses us on the ground.

# Reasoning

It moves too quickly for a plane, but too slowly to be a meteor or lightning. It's also the perfect window of time at the end of the night to reflect the sun yet be against a dark sky.

From its sweep rate of about 0.30 degrees per second we can calculate it to be about 500km up in low earth orbit.

# Evidence

- present in two consecutive exposures (03:14:21, 03:15:21 UTC), segments abutting
  within 2 px at the readout gap — rules out a meteor
- single unbroken line, no strobe beading, no double light track — unlike the 20:10:03
  and 21:14:57 aircraft trails the same night
- 22.3 deg of sky, az 241.2/alt 12.5 to az 250.0/alt 33.4; >= 0.30 deg/s, ~75x the local
  star-trail rate
- rate implies a slant range near 1100-1400 km, so an orbit of roughly 400-700 km
- light curve: 1.5 s rise, ~14 s plateau at ~200 ADU, then a 6x decay over ~60 s while
  the range was closing
- peak brightness ~mag 0 (sky-calibrated, +/-1); a diffuse reflector at that range would
  be 40-60 m across, so the light is specular — a glint, which independently explains
  the fade
- shadow-exit reading NOT established: pointing carried from another night, camera moved
  1.9 deg between them, and the shadow edge sits within that margin
