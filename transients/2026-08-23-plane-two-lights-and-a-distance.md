---
id: 2026-08-23-plane-two-lights-and-a-distance
title: A plane, and how far away it was
category: plane
confidence: confirmed
date: 2026-08-23
time: "04:37 BST"
camera: eclipticam
night: 2026-08-22
source:
  frames:
    - eclipticam-frames/night/2026-08-22/v3w/03/1787456239877.fits.fz
  combine: single
  crop: [2700, 0, 4400, 1000]   # x0, y0, x1, y1 in full-res sensor pixels
  stretch: {fn: arcsinh, gain: 4.0, hi_pct: 99.9}
  scale: 2
---

# Caption

Two lights flying in formation, because they are bolted to the same aeroplane. One
steady, and running exactly parallel to it a second that flashes about once a second.
The pair crosses 31 degrees of sky in a single 60-second exposure before the rose bush
takes them.

# Reasoning

Nothing else in the night sky blinks. A star does not, a satellite does not, a meteor is
gone before it could; the flashing is the anti-collision strobe, and on its own it
settles what this is. The interesting part is that the picture also tells us how far
away the aeroplane was. The two tracks stay a fixed distance apart for the whole
crossing, and that gap can only be a measurement across the WINGS: a separation along
the fuselage would lie along the direction of travel and be invisible, hidden inside the
trail. Measured across, the gap is 6.7 pixels, which at this part of the lens is 0.129
degrees - about a quarter of the width of the full Moon. If the two lights sit at the
wingtips of an A320, whose wings span 35.8 metres, then simple trigonometry puts the
aircraft 15.9 km away. That number can be checked, because the same photograph measures
the speed. The trail is 1630 pixels long, which is 31.5 degrees of sky, and it was drawn
in one 59.9-second exposure, so the aeroplane swept at least 0.53 degrees every second.
At 15.9 km that is 145 metres per second, 283 knots - an ordinary speed for an airliner
letting down towards Heathrow, and a reassuring answer to get out of a wingspan and a
bit of geometry. The strobe agrees too: its flashes fall every 23 pixels along the
trail, which at that sweep rate is one flash every 0.86 seconds, or about 70 a minute,
squarely inside the range aircraft strobes actually use.

# Evidence

- regular flashing along one track — anti-collision strobe, period 23.3 px = 0.86 s at
  the measured sweep rate (~70/min)
- two parallel tracks at constant perpendicular separation 6.7 px = 0.129 deg; a
  fuselage-axis separation would project ALONG the trail, so the baseline is spanwise
- both tracks white in the raw Bayer data (R/G 0.41, B/G 0.43 on each) — not the
  red/green wingtip navigation pair
- assuming an A320 span of 35.8 m: range 15.9 km; a half-span baseline would give 7.9 km
  and an implausible 141 kt
- trail 1630 px = 31.5 deg in one 59.9 s exposure -> >= 0.53 deg/s -> >= 145 m/s = 283
  kt at 15.9 km
- trail clipped by the frame edge and the rose bush, so the length, rate and speed are
  all lower bounds
- pointing not solved for this epoch (the rose-bush era predates the camera move), so no
  azimuth or elevation is quoted
