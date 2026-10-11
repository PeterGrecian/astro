---
id: 2026-10-11-arcminute
title: How big is an arc minute anyway?
instrument: eclipticam
camera: eclipticam-v3w
date: 2026-10-11
tags: [scale, units, arcminutes, right-ascension, eclipticam]
source:
  scale: eclipticam-v3w/cammodel-2026-10-07.json (equidistant + cubic, f 975.9 binned px, k 0.366); pixel size and field of view computed from it
  motion: Saturn from scratch/saturn-walk/walk-nights.csv (29 nights), Neptune from nep-find.json (27 nights), 2026-08-07 to 10-09
  other: Polaris precessed to 2026-10-11; Neptune's disc at 29 AU; the 1p coin is 20.3 mm across
---

Sizes on the sky are angles. A circle is 360 degrees, a degree is 60
arcminutes (1′), and an arcminute is 60 arcseconds (1″).

## The ladder

- **A fist at arm's length:** about 10 degrees.
- **Orion's belt,** end to end: 2.7 degrees.
- **The Moon, and the Sun:** each about **half a degree**, which is 30
  arcminutes. Not half an arcminute, as I first guessed: two full Moons side
  by side make a degree.
- **Polaris to the true pole:** 38 arcminutes this year, a little more than a
  Moon.
- **Neptune moved about 44 arcminutes a month** this autumn, a Moon and a half.
  **Saturn moved about 1.8 degrees a month,** three and a half Moons. Both
  were near opposition, going backwards (westwards) through the stars.
- **One arcminute:** a 1p coin seen from 70 metres.
- **8.2 arcminutes:** iota Ori and Struve 747, the closest pair eclipticam has
  split, a quarter of the Moon.
- **45 arcseconds:** Saturn's rings, end to end, this autumn.
- **One arcsecond:** the same 1p coin from 4.2 kilometres.
- **2 arcseconds:** about the finest detail the FirstScope's 76 mm mirror can
  show, and about what London's air allows on a good night. Neptune's whole
  disc is 2.4 arcseconds.

## Arc hours

Astronomers give a star's east-west position, its right ascension, in
**hours**, because the sky turns once a day: 24 hours make the full circle.

- 1 hour of right ascension = 15 degrees.
- 1 minute of right ascension = 15 arcminutes.
- 1 second of right ascension = 15 arcseconds.

That holds on the celestial equator. Away from it the circles of right
ascension crowd together towards the pole, like lines of longitude: at
declination 60 degrees an hour is only 7.5 degrees wide (15 times the cosine
of the declination).

It is also why a camera that does not move sees every star drift: 15
arcseconds every second, 15 arcminutes in a one-minute exposure.

## Eclipticam in these units

- The whole frame is about **104 x 68 degrees**.
- **Wide angle means low resolving.** A pixel covers about **1.8 arcminutes**
  at the centre of the frame, shrinking to about 1 near the edges, because the
  lens squeezes the edge of its view. Most of our work bins pixels 2 x 2, so
  3.5 arcminutes at the centre and about 2 at the edges.
- A one-minute exposure smears a star near the equator into a dash 15
  arcminutes long: about 8 full pixels, or 4 binned, at the centre.
- The Moon is about 17 pixels across at the centre of the frame, and the
  whole of Orion fits in about 400 by 550 binned pixels.
