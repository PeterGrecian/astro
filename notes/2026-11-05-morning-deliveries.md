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
  scaling: each processing step taken as proportional to the length of the night (10-29 for eclipticam, 11-04 for xoverpi); hq16 timed on the Pi on 2026-11-05 (night of 11-04, colour sweep only, 114 min wall)
---

Every morning the cameras' nights are turned into stacks, sweeps and videos.
None of it runs on a clock: capture and processing are tied to the Sun, so
deliveries arrive later as the nights lengthen: about an hour later at
midwinter than in early November, and four hours earlier on the clock at
midsummer (five by the Sun, since summer clocks run an hour ahead).

## How a night becomes a delivery

- **Capture** runs while the Sun is more than about 10° below the horizon.
- **xoverpi** (FirstScope, hqfs) writes every frame straight to the big store
  on muppet, which starts processing the moment capture stops. On the night of
  4 November 2026 that was 58 minutes from last frame to published.
- **eclipticam** keeps its frames on its own SSD and processes them itself, on
  the Pi 5, starting at civil dawn (Sun 6° down). v3w took 2 h 21 min that
  night, most of it rendering three sweeps. Afterwards the night's frames are
  copied to the big store over Wi-Fi, which takes about 2 hours.

## One measured night: 4 to 5 November 2026 (GMT)

| | Last frame | Delivered |
|---|---|---|
| xoverpi | 06:13 | 07:11 |
| eclipticam v3w | 06:00 | 08:48 |
| eclipticam hq16 | 06:00 | not yet automatic; timed by hand on 5 November at 1 h 54 min |
| frames on the big store | | about 11:35 |

## Through the year (London time, 21st of each month)

Assumes the order proposed in November 2026: hq16 processed on eclipticam straight after v3w, then the copy.

| | Night | xoverpi | v3w | hq16 | Big store |
|---|---|---|---|---|---|
| Jan | 13.2 h | 08:04 | 09:36 | 11:37 | 13:44 |
| Feb | 11.6 h | 07:09 | 08:31 | 10:17 | 12:09 |
| Mar | 9.7 h | 06:00 | 07:11 | 08:40 | 10:14 |
| Apr | 7.5 h | 05:37 | 06:36 | 07:45 | 08:57 |
| May | 5.3 h | 04:28 | 05:16 | 06:05 | 06:57 |
| Jun | 4.2 h | 04:00 | 04:45 | 05:24 | 06:05 |
| Jul | 5.4 h | 04:38 | 05:27 | 06:16 | 07:08 |
| Aug | 7.5 h | 05:44 | 06:44 | 07:53 | 09:06 |
| Sep | 9.8 h | 06:48 | 07:59 | 09:29 | 11:03 |
| Oct | 11.7 h | 07:45 | 09:08 | 10:55 | 12:47 |
| Nov | 13.2 h | 07:41 | 09:14 | 11:15 | 13:23 |
| Dec | 13.8 h | 08:15 | 09:52 | 11:59 | 14:12 |

The longest night, 21 to 22 December, is the worst case: everything is
delivered by about noon and copied by about a quarter past two, still
nearly three hours before the next night's capture begins at 17:07.

## Caveats (as of 5 November 2026)

- The stars-held-still (derot) sweep was not yet running on eclipticam. Once it
  runs it adds about half an hour to v3w and pushes everything after it back.
- hq16's column uses its one timed run on the Pi (1 h 54 min for the night
  of 4 November, colour sweep only). Detrans and derot sweeps for hq16 would
  add to it.
- Summer short nights are probably a few minutes later than shown, because
  some steps take the same time whatever the night's length.
