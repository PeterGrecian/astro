---
id: 2026-10-30-arcsecond
title: How big is an arc second anyway?
instrument: firstscope
camera: firstscope
date: 2026-10-30
tags: [scale, units, arcseconds, dut1, earth-rotation, polar-motion, firstscope]
source:
  earth: IERS Bulletin A and finals.daily, fetched 2026-10-30. UT1-UTC -0.0225 s on 10-01, -0.0005 s on 09-09, -0.0532 s on 10-30, predicted -0.119 s on 2027-01-01. Polar motion x 0.141, y 0.318 arcsec on 10-30. Bulletin D rounded DUT1 -0.1 s
  scale: Earth turns 15.04 arcsec per second of time. FirstScope 76 mm, 300 mm focal length, so 1 arcsec is 1.45 microns at the focus. Photosites 1.55 microns (HQ) and 1.4 microns (v1), theoretical scale, not plate solved. Diffraction 1.22 lambda/D at 550 nm
  other: Berrylands latitude 51.4 N; arm's length 65 cm as in note 2026-10-11-arcminute; 1p coin 20.3 mm; Proxima parallax 0.77 arcsec; FirstScope focus from note 2026-09-20-firstscope-derotation and astro-capture's 2026-10-28 focus report
---

The Earth is late. It does not turn at a steady rate, and our clocks, which run
on atoms, take no notice. The gap has a name, **DUT1**: the time told by the
Earth's turning (UT1) minus the time on the clock (UTC).

- It crossed zero on 9 September.
- On 1 October it reached -0.022 seconds, and since the sky turns 15 arcseconds
  every second, the stars were **a third of an arcsecond** from where the clock
  said they should be.
- Today it is -0.053 seconds, which is **0.8 arcseconds**.
- It is growing by about a millisecond a day, because each day just now is
  about a millisecond longer than 86,400 seconds. It is predicted to reach -0.119
  seconds, 1.8 arcseconds, by New Year.

Being negative, it means every star arrives late: tonight a star crosses the
meridian 53 milliseconds after the clock says it should, and is that much east
of its predicted place. Those figures are for the celestial equator. Away from
it they shrink like right ascension does, with the cosine of the declination.

The ground is what is out of place, of course, not the stars. Here in London we
travel at 290 metres per second, so the house is about **15 metres** short of
where an Earth keeping clock time would have put it.

If the gap ever nears 0.9 seconds, 13.5 arcseconds, UTC gets a leap second to
close it. The last was at the end of 2016.

## The ladder

Carrying on down from [How big is an arc minute
anyway?](/astro/notes/2026-10-11-arcminute):

- **20 arcseconds:** how far the Earth's speed round the Sun displaces every
  star, in a circle or ellipse each year (aberration).
- **15 arcseconds:** how far the sky turns in one second.
- **2.4 arcseconds:** Neptune's whole disc.
- **2 arcseconds:** about what London's air allows on a good night.
- **1.8 arcseconds:** the finest detail the FirstScope's 76 mm mirror can show
  in green light. Also DUT1 by New Year.
- **1 arcsecond:** one photosite on the FirstScope, near enough (1.07 with the
  HQ camera, 0.96 with the v1). A 1p coin at 4.2 kilometres. 3 thousandths of a
  millimetre at arm's length. 2 kilometres on the Moon. 66 milliseconds of the
  sky's turning.
- **0.8 arcseconds:** DUT1 today.
- **0.77 arcseconds:** the parallax of Proxima Centauri, the nearest star: how
  far it shifts because we moved one Earth-Sun distance. Every other star shifts
  less, which is why no star is as close as a parsec.
- **A third of an arcsecond:** DUT1 on 1 October, and as it happens also how far
  the pole is from its reference position today, see below. One micron at arm's length.
- **A twentieth of an arcsecond:** the finest detail the Hubble Space Telescope
  can show.

## The other third of an arcsecond

The Earth also wobbles on its axis, so the pole wanders over the ground. Today
it is 0.32 arcseconds one way and 0.14 the other from the reference position:
**0.35 arcseconds, or 11 metres** on the ice. That moves the sky over London by
about 0.3 arcseconds. It is the same size as DUT1 was a month ago, and it
wanders in loops rather than growing.

## Can the FirstScope see it?

Just about, in one sense, and not in the sense that matters.

**It cannot resolve it.** 0.8 arcseconds is under one photosite and less than
half the blur of the mirror. At the focus a third of an arcsecond is half a
micron, which is about one wavelength of green light.

**It can locate it.** Resolving is telling two things apart. Locating one star
is much easier: the centre of a blur can be measured to a small part of its
width, about a hundredth of an arcsecond for a well-focused star at 100 times the
noise. So the optics and the sensor have what it takes, once the focus does.
They have not shown it yet. The best measured star so far is 11.5 arcseconds
wide (September, an upper bound), and with the HQ camera the scope is still 2.7
mm of travel short of focus on the stars.

**The trouble is that every star moves together.** DUT1 shifts the whole sky as
one, so no picture shows it. A plate solve would just report that the scope
points a little to the east. To see it, the scope must be a fixed reference: time
stars across the same pixel on a run of nights, and watch them come 15
thousandths of an arcsecond later each day. That is how the Earth's turning was
measured before atomic clocks. It asks a lot:

- **The mount.** One arcsecond is 0.4 microns of tilt across the width of the
  mirror. The FirstScope is a tabletop Dobsonian, with a cardboard collar, indoors.
- **The clock.** 0.8 arcseconds is 53 milliseconds, so the frame's timestamp has
  to be good to a few milliseconds. The Pi's network time is around that at best,
  and the sensor reads out from top to bottom over about a tenth of a second.
- **The air.** Refraction lifts a star at 45 degrees by about an arcminute, so a
  1 percent change in air pressure moves it 0.6 arcseconds. That lift is straight
  up, so a scope pointing due south escapes most of it: on the meridian, up is
  north-south and the timing runs east-west. What remains is the shimmer.

So the FirstScope's numbers reach this scale and the table it stands on does not.

For the other cameras it is not even a question. DUT1 today is about a seventy-fifth
of an astrocam v3 photosite and a hundred-and-thirty-fifth of an eclipticam v3w one
at the centre of its frame.
On the FirstScope's September field, 4 degrees from the pole, it would be just
0.06 arcseconds.
