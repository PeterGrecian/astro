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
  other: Polaris precessed to 2026-10-11; Neptune's disc at 29 AU; arm's length taken as 65 cm, a hair as 0.07 mm, a small ant's head as 1 mm; M51 from SIMBAD/NED (11.2' x 6.9'); astrocam v3 58.9"/px from its plate solve; sword 42 Ori -4 50' to iota Ori -5 54'
---

Sizes on the sky are angles. A circle is 360 degrees, a degree is 60
arcminutes (1′), and an arcminute is 60 arcseconds (1″).

## The ladder

- **A fist at arm's length:** about 10 degrees.
- **Orion's belt,** end to end: 2.7 degrees.
- **Orion's sword,** from c Ori down to iota Ori at its tip: about 1 degree,
  two Moons, with the Orion Nebula in the middle.
- **The Moon, and the Sun:** each about **half a degree**, which is 30
  arcminutes.
- **Polaris to the true pole:** 38 arcminutes this year, a little more than a
  Moon.
- **Neptune moved about 44 arcminutes a month** this autumn, a Moon and a half.
  **Saturn moved about 1.8 degrees a month,** three and a half Moons. Both
  were near opposition, going backwards (westwards) through the stars. This
  is retrograde motion: we orbit much faster, so as Earth catches them up and
  overtakes, they seem to slip back.
- **11 by 7 arcminutes:** the Whirlpool Galaxy, M51, about a third of the
  Moon across, though only its bright core shows in a small telescope.
- **8.2 arcminutes:** iota Ori and Struve 747, the closest pair eclipticam v3w
  has split, a quarter of the Moon.
- **5 arcminutes:** a small ant's head at arm's length.
- **1.8 arcminutes:** one eclipticam v3w pixel at the centre of the frame,
  about 1 near the edges.
- **One arcminute:** one astrocam v3 pixel. A fifth of a millimetre at arm's length, two or three
  hairs side by side. About the finest detail a sharp eye can see.
- **45 arcseconds:** Saturn's rings, end to end, this autumn.
- **2 arcseconds:** about the finest detail the FirstScope's 76 mm mirror can
  show, and about what London's air allows on a good night. Neptune's whole
  disc is 2.4 arcseconds.
- **One arcsecond:** a sixtieth of an arcminute, 3 thousandths of a millimetre at
  arm's length.

## Hours of right ascension

Astronomers give a star's east-west position, its right ascension, in
**hours**, because the sky turns once a day: 24 hours make the full circle.

- 1 hour of right ascension = 15 degrees.
- 1 minute of right ascension = 15 arcminutes.
- 1 second of right ascension = 15 arcseconds.

Confusingly, but funnily, a minute of right ascension is not an arcminute:
it is a minute of time, the turn of the sky in one minute by the clock, and
it is 15 arcminutes wide. There is no such thing as an arc hour.

That holds on the celestial equator. Away from it the circles of right
ascension crowd together towards the pole, like lines of longitude: at
declination 60 degrees an hour is only 7.5 degrees wide (15 times the cosine
of the declination).

It is also why a camera that does not move sees every star drift: 15
arcseconds every second, 15 arcminutes in a one-minute exposure.

## Eclipticam v3w in these units

- The whole frame is about **104 x 68 degrees**.
- **Wide angle means low resolving.** A pixel covers about **1.8 arcminutes**
  at the centre of the frame, shrinking to about 1 near the edges, because the
  lens squeezes the edge of its view. Most of our work bins pixels 2 x 2: a
  binned pixel is one RGBG set of photosites, so 3.5 arcminutes at the centre
  and about 2 at the edges.
- A one-minute exposure smears a star near the equator into a dash 15
  arcminutes long: about 8 full pixels, or 4 binned, at the centre.
- The Moon is about 17 pixels across at the centre of the frame, and the
  whole of Orion fits in about 400 by 550 binned pixels.
