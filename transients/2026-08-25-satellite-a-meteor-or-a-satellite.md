---
id: 2026-08-25-satellite-a-meteor-or-a-satellite
title: A meteor or a satellite, at dawn
category: satellite
confidence: possible
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
---

# Caption

A clean straight line 44 degrees long, drawn in a single 60-second exposure and running
off the right-hand edge of the picture. It starts in mid-air, high in the south-west,
and leaves the frame low in the west. It is in one exposure only: nothing in the minute
before, nothing in the minute after.

# Reasoning

This one is honestly unresolved, and it is worth showing because of WHY. A meteor and a
satellite leave exactly the same mark. Both are a point of light dragged across the
sensor while the shutter is open, and a photograph records where the light went, not how
long it took. The thing that settled our other satellite - it was caught in two
consecutive exposures, so it was up there for over a minute, and no meteor lasts that
long - is precisely what this one denies us. It appears in one exposure and one only.
What we can rule out is an aeroplane. It sweeps 44 degrees in at most a minute, which is
0.73 degrees a second - a jet at any believable distance cannot do that - and there is
no flashing anywhere on it, no strobe, and no second parallel track from a far wingtip,
all of which the genuine aircraft on these same nights wear plainly. The clock is the
best argument for a satellite. The sun was 11 degrees below the horizon and climbing; a
satellite is only visible when it is in sunlight while the ground below is dark, so it
must be near dawn or dusk, and this is exactly that window. A meteor, which makes its
own light, cares nothing for the hour. Dawn favours the satellite, but it does not prove
it.

# Evidence

- 44.0 deg of sky, az 234.2/alt 49.1 to az 249.6/alt 7.0, in a single 59.9 s exposure ->
  >= 0.73 deg/s
- present in one exposure only — the multi-exposure persistence that identifies a
  satellite is unavailable here
- one end interior, the other at the frame border; on geometry alone the two tests
  disagree
- no strobe beading and no double light track, unlike the aircraft trails on these
  nights
- solar altitude -11 deg and rising, inside the dawn window when satellites are lit and
  the ground is dark
- astrometry from the plate solution for this night (Altair, Tarazed, Alshain and the
  Moon; rms 1.5 px, checked against Saturn to 3-6 px)
