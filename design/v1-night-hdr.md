# v1 day–night–sun HDR — v1 as the wide-DR highlights camera

> **ABANDONED 2026-07-06.** The whole day/moon/sun/v1 line is retired — v1
> capture is stopped (eclipticam is night-only now) and the day frames deleted.
> This HDR idea never left design and won't be built. Not needed for the quests.

**Status: ABANDONED (was: design only 2026-07-01. No code was ever written.)**

## Scope grew (read this first)

Started as "unsaturated moon at night on v1"; the concept is now **v1 as a
full day→night HDR camera**, potentially imaging the **sun** too, using
**moveable neutral-density filters** to span the range. v3w stays the
faint-sky science camera (60 s full-res). v1 becomes the highlights/detail
camera across the whole diurnal cycle.

## Correction: v1 does NOT have a resolution advantage at night

An earlier version of this note justified v1 by "~2× finer than v3w at
night." **That was wrong** — it used v3w's stale binned plate scale. v3w
captures **full-res (4608×2592) at night since 2026-06-22**, so:

| | angular resolution | moon spans |
|---|---|---|
| v1 (2592px, 53.5°) | 74.2 arcsec/px | ~24 px |
| v3w full-res (4608px, 102°) | 79.7 arcsec/px | ~23 px |

They're **essentially equal**. So v1 is NOT justified by sharper-moon —
v3w full-res already resolves the moon as well. v1's real, narrower case:
- **Narrower FOV** (53° vs 102°): moon + context fills more of the frame.
- **Independent exposure/HDR**: v1 on its own clock can bracket sun→moon
  without touching v3w's continuous 60 s stream.
- **Different sensor/lens** (OV5647 vs IMX708): colour, saturation, and it
  frees v3w to stay optimised for faint sky.

## Measured relative orientation (v1 vs v3w), 2026-06-25 shared moon

Both cameras marked the same moon on 06-25 → common sky reference. FULL
POSE SOLVED by time-correcting: fit each camera's moon track pixel=f(UTC),
interpolate BOTH to common instants (removes the 57–118s motion smear),
Umeyama LSQ similarity v1px→v3wpx (residual ~1px):
- **scale = 0.791** (v1→v3w px)
- **rotation = −2.80°** (v1 rel v3w)
- **v1 boresight offset from v3w centre = (2.51°, −4.38°)** on sky — v1
  points ~2.5° right / 4.4° up from v3w. **Near-coaligned** (shared mount).

Confidence: 1px-residual fit, but one night, v1 arc only 6° az in one
corner. A truly-simultaneous pair or per-camera WCS
(`project-astro-orientation-lock`) confirms. NB the offset IS calculable
from simultaneous sightings — the moon in both cameras at (near-)common
times is the correspondence.

## Dynamic range this must span (with sun)

| target | ~EV | note |
|---|---|---|
| Sun disc | +30 | ~19 stops above full moon; needs OPTICAL ND |
| Daytime / full moon | +14–15 | sunlit rock |
| Twilight | +6–10 | |
| Foreground lights | +3–6 | |
| Faint stars | −6..+2 | v3w territory, not v1's |

Sun↔dark-sky is ~50 stops — no exposure ladder alone covers it. Sun needs
~13–20 stops of ND on top of the ~20 stops of electronic range (30 µs–3.07 s
exposure × ~4 stops gain). Hence *moveable* ND: in for the sun, out for
moon/night. (User's read: brief sun exposure isn't sensor-damaging on a
small CMOS behind a modest lens — treat the design problem as *getting an
unsaturated image*, not sensor survival, but still ND the sun.)

## Moveable ND mechanism (hardware inbound 2026-07)

**Filters:** Selens **ND6** and **ND9** gel sheets (stop-rated: 6 and 9
stops). Stack **adds** → four attenuation levels:

| selection | stops | for |
|---|---|---|
| clear | 0 | night moon (~300 µs, no ND), dark sky |
| ND6 | 6 | bright twilight / daytime sky+moon |
| ND9 | 9 | (intermediate) |
| ND6+ND9 | **15** (32768×) | **sun** → ~EV15 daytime-bright, image at short exp |

15 stops tames the sun disc (~EV30) to daytime-bright — imageable. Good.

**Actuator:** SG90 servo slides the filters past the lens (user plan:
"overlapping stacked filters"). Two mechanisms:
- **Two independent slides** (2 servos), one per sheet → any of the 4
  combos by overlapping. Matches the "stack past the lens" idea directly.
- **One 4-window strip** (1 servo): laminate `[clear][ND6][ND9][ND6+ND9]`
  into one strip, servo picks the window. Simpler, fewer failure points —
  **recommended** unless the two-slide overlap is preferred for packing.

**Gotchas (design in, don't discover later):**
1. One SG90 = one slide = **3 positions max** cleanly; the 4-window strip
   or a 2nd servo is needed for all 4 levels.
2. **IR leakage / colour cast** — cheap ND gel often passes IR the sensor
   sees → magenta/warm cast; matters for a colour moon/sun. May need an IR
   cut, or characterise & correct. Sheets must be **flat** (wrinkle = soft
   focus / uneven density) — flat mount, not flapping film.
3. **Not weatherproof** — SG90 + gel outdoors is the first thing to fail on
   a rooftop appliance (`project-astro-appliance-vision`). Enclose; keep
   the filter window fog/ice-free.
4. SG90 repeatability ~±1–2° → size strip windows with margin so the wrong
   window can't clip the aperture.
5. Servo = one Pi GPIO PWM. **Move BETWEEN captures**, detach PWM during
   exposure (stop jitter/buzz). State machine: sun-up → ND stack; moon/
   night → clear; twilight → ND6.

## Motivation

v3w night frames saturate the moon hard — a 60 s exposure blows the disc to
a flat white blob (measured max 65472/65535). Fine for *marking* (centroid
is saturation-tolerant), useless for a *sharp, unsaturated* moon (craters,
terminator, HDR deliverable). The moon and the faint sky can't share one
exposure: ~20 stops apart.

Idea we kept circling back to: **use v1 as a dedicated moon/highlights
camera at night**, co-pointed with v3w, running a SHORT exposure that holds
the moon unsaturated. v3w keeps doing faint-sky science (60 s). Together
they're a two-camera HDR rig, not a single-camera bracket.

Originally framed as "HDR in the interval between exposures" — but the v3w
night loop now streams **continuously** (~100 ms readout between 60 s
frames, >99% duty; see `astro/capture/streaming.py`). There is no dead
interval to fill. v1 is a *separate camera*, so it can bracket on its own
clock without touching v3w's stream. That's the realisable form.

## Is the moon even in v1's frame at night?

**Not yet confirmed from data — v1 does not capture at night** (0 v1 night
frames on every recent night; `eclipticam-v1/camera.json` has no `capture`
block — day-only by design).

Geometric inference (v1 & v3w co-located, same mount, look S/SSW):
- Day 2026-06-25 the moon crossed **both** v1 and v3w at az 191–197°, so
  their fields overlap there (v1 marks: az 191–197, alt 14–15).
- v1 FOV ≈ 53.5° horizontal (OV5647 stock lens, `plate_scale_deg_px`
  0.0206); v3w ≈ 102°. v1 sees ~the central half of v3w's field.
- Night 2026-06-30 the moon tracked az 167→201° at alt 10–12°, **passing
  through** the az~194° band v1 is known to see, ~02:00 UTC.
- ⚠️ Altitude caveat: v1 day marks were alt 14–15°; the night moon crossed
  ~2–3° lower. v1's vertical FOV (~40°) almost certainly still contains it,
  but this is inferred — **one real v1 night frame settles it** (a manual
  short grab at moon transit; deferred).

**Working assumption: yes, the moon is in v1's field for ~20–40 min around
transit each night it's up.** Validate on first run.

## Exposure sizing (Looney-11)

Full moon is sunlit rock ≈ EV14–15 — a *daytime* subject.
- Correct full-moon exposure ≈ 1/125 s at f/11, ISO100 (Looney-11).
- v1 lens ≈ f/2.0 → ~5.5 stops faster → **~250–500 µs** holds the moon
  unsaturated at gain ≈ 1. Well inside OV5647 limits (min ~30 µs, max
  3.07 s per `max_single_exposure_us`).
- At ~300 µs: moon disc + terminator detail unsaturated, bright foreground
  lights OK, sky floor black (no stars — expected; stars are v3w's job).

## Capture design

Reuse the streaming path (`astro.capture.streaming.run` +
`StreamingConfig`), a new `v1_night_daemon.py` mirroring
`v3w_night_daemon.py`:
- `cam_idx = CAM_V1`, `sensor_size (2592,1944)`, `bayer SGBRG10/GBRG`,
  `rotation_180` per v1 mount, `lens_position=None` (OV5647 fixed-focus,
  no VCM), `pedestal 10180`.
- `exposure_us ≈ 300` (tune on first frames), `gain 1.0`.
- Cadence: v1 has no 60 s integration, so it can fire much faster. A frame
  every **5–15 s** is plenty to trace the moon arc (it moves ~0.13 px/s on
  v3w scale; v1 is ~2× finer so ~0.26 px/s → a few px between 15 s frames).
- Mode `"night"`, writes `night/<night>/v1/HH/<epoch_ms>.fits.fz` (percam
  layout, same as day). brightness.csv appends per row.
- Gate identically to v3w on the state record (capture only when
  `sun_altitude < -10°` AND moon above horizon — the moon-up gate is new;
  no point running when the moon's down. Compute from `ephem` in the
  daemon or the state controller).

New `camera.json` `capture` block for v1:
```json
"capture": {"night_exposure_us": 300, "night_gain": 1.0}
```

## HDR merge (later, optional)

The point deliverable is the **unsaturated moon frame itself** — that alone
is the win. A true HDR *merge* (v1-short highlights ⊕ v3w-long faint sky)
is a second step: register v1↔v3w via the shared WCS (needs the
orientation-lock work, `project-astro-orientation-lock`), reproject one
onto the other, blend by luminance. Not required for v1 to be useful.

## Cost

~300 µs frames are tiny; even at 1/10 s cadence a night is a few hundred
frames, far less data than v3w's 60 s FITS. Storage negligible. The real
cost is standing up + gating a second night daemon on the Pi.

## Open items

1. **Confirm framing** — first v1 night frame at moon transit (or the
   deferred manual grab).
2. Add moon-above-horizon gate to the state machine (both cameras benefit).
3. Tune `exposure_us` from real frames (300 µs is an order-of-magnitude
   start).
4. v1 night frames also give a **night moon-net thread for v1** — feeds the
   same WCS fit, at v1's finer plate scale.
