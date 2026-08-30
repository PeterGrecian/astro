---
id: 2026-08-23-plane-two-lights-and-a-distance
title: Large Low Aircraft
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

A 60-second exposure of an airliner viewed from 9 miles south of Heathrow airport. Heathrow's runways run East-West, but this aircraft is captured in a sweeping turn we calculate to be about 320 mph (280 knots). That speed and rapid turn rate point to climbing out on its departure route, rather than a slow, straight-in landing approach. The steady headlights - landing lights as they are called - leave parallel rails, while the synchronized 1-second anti-collision strobes map out the plane's true orientation in 3D space.

# Reasoning

The gap between the tracks of the lights is 7 pixels, which at this part of the lens is 0.13 degrees — about a quarter of the width of the full Moon. An A320, for example, has a wingspan of 36 metres, which is how we worked out the speed.

The strobe flashes appear every 23 pixels along the trail, exactly once per second, at the same time, exhibiting the signature Airbus-style double-flash pattern. The lights are on the wingtips and tail top, the latter visible between the continuous landing lights.  This shows us how the plane is orientated with repect to our viewpoint. The position of the lights suggests a narrow bodied jet rather than a wide one - almost certainly the ubiquitous A320.

The altitude of the plane is about 15,000 feet, 3 miles/5km so it has climbed at a good rate of 3,000 feet per minute and an angle of ascent of about 6 degrees.  These are typical values for a plane climbing out of an airport.
