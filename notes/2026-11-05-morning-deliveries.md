---
id: 2026-11-05-morning-deliveries
title: When does last night arrive? It depends on the Sun
instrument: other
date: 2026-11-05
night: 2026-11-04
tags: [pipeline, timing, seasons, eclipticam, xoverpi, hq16]
source:
  observed: astro-process and eclipticam-ship-night journals on muppet and eclipticam, nights 2026-10-29 and 2026-11-04
  sun: capture and processing start at fixed sun depressions, solved for Berrylands (51.39 N, 0.29 W) on the 21st of each month; the model matches the observed start and stop times to within a minute
  scaling: each processing step taken as proportional to the length of the night (10-29 for eclipticam, 11-04 for xoverpi); hq16 extrapolated from v3w until it has been timed on the Pi
---

Every morning the cameras' nights are turned into stacks, sweeps and videos.
None of it runs on a clock: capture and processing are tied to the Sun, so
deliveries arrive later as the nights lengthen: about an hour later at
midwinter than this week, and four hours earlier on the clock at midsummer
(five by the Sun, since summer clocks run an hour ahead).

## How a night becomes a delivery

- **Capture** runs while the Sun is more than about 10° below the horizon.
- **xoverpi** (FirstScope, hqfs) writes every frame straight to the big store
  on muppet, which starts processing the moment capture stops. Last night that
  was 58 minutes from last frame to published.
- **eclipticam** keeps its frames on its own SSD and processes them itself, on
  the Pi 5, starting at civil dawn (Sun 6° down). v3w took 2 h 21 min last
  night, most of it rendering three sweeps. Afterwards the night's frames are
  copied to the big store over Wi-Fi, which takes about 2 hours.

## This week (GMT)

| | Last frame | Delivered |
|---|---|---|
| xoverpi | 06:13 | 07:11 |
| eclipticam v3w | 06:00 | 08:48 |
| eclipticam hq16 | 06:00 | not yet automatic |
| frames on the big store | | about 11:35 |

## Through the year (London time, 21st of each month)

Proposed order: hq16 processed on eclipticam straight after v3w, then the copy.

| | Night | xoverpi | v3w | hq16 | Big store |
|---|---|---|---|---|---|
| Jan | 13.2 h | 08:04 | 09:36 | 11:09 | 13:16 |
| Feb | 11.6 h | 07:09 | 08:31 | 09:52 | 11:44 |
| Mar | 9.7 h | 06:00 | 07:11 | 08:19 | 09:53 |
| Apr | 7.5 h | 05:37 | 06:36 | 07:28 | 08:41 |
| May | 5.3 h | 04:28 | 05:16 | 05:54 | 06:45 |
| Jun | 4.2 h | 04:00 | 04:45 | 05:14 | 05:55 |
| Jul | 5.4 h | 04:38 | 05:27 | 06:04 | 06:56 |
| Aug | 7.5 h | 05:44 | 06:44 | 07:37 | 08:50 |
| Sep | 9.8 h | 06:48 | 07:59 | 09:07 | 10:42 |
| Oct | 11.7 h | 07:45 | 09:08 | 10:29 | 12:22 |
| Nov | 13.2 h | 07:41 | 09:14 | 10:47 | 12:54 |
| Dec | 13.8 h | 08:15 | 09:52 | 11:29 | 13:43 |

The longest night, 21 to 22 December, is the worst case: everything is
delivered by about half past eleven and copied by about a quarter to two,
still three hours before the next night's capture begins at 17:07.

## Caveats

- The stars-held-still (derot) sweep is not running on eclipticam yet. When it
  does it adds about half an hour to v3w and pushes everything after it back.
- hq16's times are extrapolated from v3w's; a timed run on the Pi is under way.
- Summer short nights are probably a few minutes later than shown, because
  some steps take the same time whatever the night's length.
