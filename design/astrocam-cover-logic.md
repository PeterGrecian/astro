# astrocam cover logic — v2 (cloud-close + durable log)

**Status: DESIGN (2026-07-06).** Prompted by Peter noticing the rain gap and
asking whether cover transitions are logged.

## Physical setup

astrocam is in a **waterproof box**: lens → **phone glass** (fixed aperture
cover, lens sits adjacent) → **sg90-moved transparent cover** → sky. Fairly
sheltered by the house. The sg90 cover moves; the phone glass is always in the
path. (The phone glass is the prime suspect for the ~8px soft PSF — non-optical
glass, can fog/dust on the inside; inspect/clean it before blaming the lens.)

`cover.py`: `open`=servo min, `closed`=servo mid (calibrated 2026-06-09).

## Current logic (capture.py) — brightness only

State machine on `frame.mean`:
- `mean <= COVER_DARK_MEAN (80)` for 5 frames → **open** (`day→night`).
- `mean >= COVER_BRIGHT_MEAN (250)` for 5 frames → **close** (`night→day`).
- 300 s lockout between flips. Closed-cover mean ~3.

**So: opens at dusk (dark), closes at dawn (bright). This is correct for
day/night — but it knows NOTHING about weather.**

## The gaps

### 1. Rain gap (the important one)
The cover closes on **brightness**, not weather. At **night + raining** it stays
**OPEN** → water ingress. Peter's fix: **"if it's cloudy it should be closed — it
must be cloudy to rain."** Cloud is the free rain-proxy — and astrocam **already
computes it**: DAOStarFinder runs every co-add, so **star count** is available.
Clear → many stars; cloudy → few/none (a *better* cloud detector than raw
brightness, since cloud can be dark-but-starless).

**v2 decision:** open only when **(dark AND clear)**; close when **(bright OR
cloudy)**. Add a star-count term:
- `n_stars >= N_CLEAR` → clear; `n_stars < N_CLOUDY` for M frames → cloudy → close.
- Keep the brightness day/night term as-is; OR the cloud term into the close
  condition. Keep the lockout + hysteresis to avoid flapping on passing cloud.
- Tune N_CLEAR/N_CLOUDY from a clear-vs-cloudy night's star counts.

### 2. No durable cover log
Transitions are `print()`ed to the journal (`mode day->night (mean=...)`), but:
- the journal query returned nothing recent (rotated/empty — unreliable);
- `save_state()` writes only `{mode, frame_mean}`, **overwritten every frame** —
  no timestamped history.

**So "did it open at dusk and close at dawn last night?" is NOT answerable from a
persistent record.** Fix: append timestamped events to a durable file, e.g.
`~/astrocam-frames/<night>/cover.log` (or the canonical `state.json` with a
transition list): `<utc> open|closed reason=dark|bright|cloudy mean=.. n_stars=..`.
Then dusk-open / dawn-close / rain-close are auditable.

### 3. Capture is gated by cover state (mode==night == cover OPEN)
CONFIRMED (Peter): astrocam CAPTURES ONLY when the cover is OPEN. `if mode ==
"night":` gates all capture (coadd/FITS/brightness/starfind); "Day mode just
discards the raw and doesn't write FITS" (capture.py L69). mode<->cover are
locked: night==open, day==closed (L290). So **cover-close and capture-stop are
the SAME event.**

Consequences for cloud-close:
- A sustained cloud closes the cover -> capture stops (correct for rain, but also
  halts imaging). Must NOT flap on transient cloud (sg90 wear + fragmented
  imaging) -> cloud-close needs a LONGER hysteresis than day/night: close only on
  PERSISTENT low star-count (minutes), rely on the 300s lockout.
- **No bootstrap problem — the cover is TRANSPARENT** (Peter). The camera still
  sees the sky brightness AND star count THROUGH the closed cover (mean ~3 is the
  DARK sky through glass, not blindness; day mode merely CHOOSES not to save
  frames). So clarity is judgeable continuously whether open or closed -> the
  cloud-close/clear-open decision runs on the through-glass star count with NO
  peek needed. Closed = rain protection only, not a blind shutter.

## Fail-safe consideration
Given the box is only *fairly* sheltered, bias toward safety: on **ambiguity or
sensor failure, default to CLOSED**. Better to miss a clear night than flood the
box. (The cover-decision logic historically lives on starcam —
`project-cover-logic-owner-starcam`; consider whether astrocam should share a
fleet cloud/weather signal rather than decide alone.)

## Actions
1. Add star-count cloud term to the cover close condition (open = dark∧clear).
2. Add a durable timestamped cover transition log.
3. Inspect/clean the phone glass (the likely ~8px softness cause) next visit.
4. Tune N_CLEAR/N_CLOUDY from real clear/cloudy star counts.
