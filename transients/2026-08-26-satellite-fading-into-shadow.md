---
id: 2026-08-26-satellite-fading-into-shadow
title: A satellite, switching on and fading out
category: satellite
confidence: confirmed
date: 2026-08-26
time: 04:14 BST
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

A hockey stick rising out of the treeline into open sky. It is one object caught across
two consecutive 60-second exposures: the curved foot was drawn in the first, the long
handle in the second, and the two join within 2 pixels of each other - the width of the
gap between exposures. About 22 degrees of sky, low in the west-south-west.

# Reasoning

At first glance this could be a meteor, and the geometry even encourages it, because
both ends of the streak stop in mid-air rather than running off the edge of the picture.
But it is present in TWO exposures, one after the other, and a meteor is a sub-second
event; it is only ever caught in one. This thing was up there for well over a minute,
which settles it. Nor is it an aeroplane: it is a single unbroken line, with no flashing
on it anywhere and no second parallel track, whereas the genuine aircraft caught on
these same nights wear both plainly. So: a satellite, low and climbing, crossing at
least a third of a degree every second - about seventy times faster than the stars
drift. That rate is also a distance measurement, because everything in low orbit travels
at nearly the same 7.6 km a second, so how fast it appears to move tells us mostly how
far away it is: roughly 400 to 700 km up, the ordinary crowded shelf. The brightness is
the part we cannot finish. It switches on in about a second and a half, holds steady for
a quarter of a minute, then fades six-fold to nothing over the following minute, while
moving at a constant rate and drawing slightly CLOSER to us, which should have made it
brighter. So what changed is not where it was but what it was showing us - most likely a
sunlit face turning away, a tumbling rocket stage or a flat panel rotating out of the
angle. A tempting explanation for the sharp switch-on is the satellite leaving the
Earth's shadow, and the trail does sit along the edge of that shadow. We are not
claiming it: this camera moved 1.9 degrees between the night the pointing was solved and
the night of this photograph, and the shadow's edge here is closer than that, so the
geometry cannot be made to decide. What the photograph does prove is the identification.

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
