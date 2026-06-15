# Capture unification — design notes

**Status**: design, not implemented beyond the eclipticam v3w streaming
daemon that landed on 2026-06-15.

**Why this exists**: today we have three Pi-side capture codebases
(eclipticam, astrocam, skycam — the last two living in
`Berrylands/gardencam`). Plus `starcam_night_daemon.py`. They are 90%
the same code, drift independently, and bugfixes / improvements have
to be ported by hand. The deliverables side (`bin/nightly-cam`,
`bin/publish-night-cam`, `astro/present/*`) is already unified and
camera-parametric via `camera.json`. Capture isn't.

## The two camera classes

| Class | Goal | Cadence priority | Exposure priority |
|---|---|---|---|
| **Cosmetic** (skycam) | Smooth video for humans | Constant inter-frame interval (jitter ~ms) | Loose — AE can drift, just keep frame rate steady |
| **Scientific** (starcam, astrocam, eclipticam) | Photometric integrations, smooth trails in stacks | Constant interval (jitter ~ms) | Tight — exposure = cadence − readout (maximise duty cycle), gain/AE locked |

**Both want low jitter.** That's what motivates the streaming-camera-
held-open pattern: `picamera2` opens once at start-of-night and the
libcamera scheduler pins cadence via `FrameDurationLimits=(d,d)`.
Python timing doesn't enter the loop. Subprocess-per-frame
(rpicam-still per systemd tick) had ~5 s of jitter at 60 s cadence
on eclipticam v3w; same kind of jitter at 3 s on starcam.

The cosmetic/scientific axis collapses to **one config flag** in
`camera.json`: do we set the exposure to `cadence - readout` (science)
or let AE drive it (cosmetic). The capture mechanism is otherwise the
same.

## Target shape

```
astro/astro/capture/
  streaming.py        # ALREADY EXISTS — generic Picamera2 streaming loop
  uploader.py         # generic tmpfs → NFS drainer, parametric over camera config
  modes.py            # generic day/night/sun hysteresis state machine
  host.py             # multi-camera-per-host coordinator (eg eclipticam v3w gates v1)
  __main__.py         # entry: python3 -m astro.capture --camera <name>
```

Per-camera repo dirs (`eclipticam/`, `astrocam/`, `skycam/`,
`starcam/`) hold **only**:
- `camera.json` — sensor, modes, exposure policy, S3 target, privacy
- `host.json` (if multi-camera) — which cams on this host, cross-cam rules
- `location.json`, `occlusion.json`, `privacy.json`, `quality.json` (already the convention)

The Pi-side capture process is one command:
```
python3 -m astro.capture --camera eclipticam
```
Reads `camera.json`, runs streaming + uploader + mode-tick. Done.

## camera.json — proposed schema additions

Existing fields stay; add:

```jsonc
{
  // ... existing sensor / Bayer / resolution / pedestal / S3 ...

  "modes": {
    "night": {
      "trigger": "luminance",      // or "sun_altitude" or "schedule"
      "enter_when": "lum < 0.0005",
      "exit_when":  "lum > 0.005",
      "hold_ticks": 3,             // hysteresis
      "cadence_ms": 60000,
      "exposure_us": "cadence - 100ms",   // OR an explicit int
      "gain": 1.0,
      "lens_position": 0.0,
      "format": "fits.fz",         // OR "jpg" OR "npy"
      "saturation_stops_above_pedestal": 13.0  // exit guard
    },
    "day": {
      "trigger": "default",        // ie when no other mode applies
      "cadence_ms": 60000,
      "exposure_us": "auto",       // AE on
      "gain": "auto",
      "format": "jpg"
    },
    "sun": {                       // future: v1 with dark filter
      "trigger": "sun_altitude",
      "enter_when": "alt > 10 AND filter_engaged",
      "cadence_ms": 6000,
      "exposure_us": 1000,         // very short
      "gain": 1.0,
      "format": "fits.fz"
    }
  },

  "buffer_dir": "/var/lib/eclipticam-buffer/v3w",   // tmpfs
  "spillover_dir": "/var/lib/eclipticam-spill/v3w", // SD fallback (TODO)
  "output_layout": "percam-noon-rollover"          // matches existing layouts
}
```

The cosmetic/scientific distinction is one field:
- `"exposure_us": "cadence - 100ms"` → scientific (eclipticam v3w night)
- `"exposure_us": "auto"` → cosmetic (skycam day)

## host.json — for multi-camera Pis

eclipticam has both v1 and v3w on the same Pi. v3w's mode gates
whether v1 captures at all (v1 day mode is pointless at 03:00). That's
a per-host concern, not a per-camera concern.

```jsonc
{
  "cameras": ["v3w", "v1"],
  "rules": [
    // v1 only fires when v3w is in day; in night, v1 sleeps
    {"when": "v3w.mode == 'night'", "freeze": ["v1"]}
  ]
}
```

starcam (Pi 1B) and astrocam (Pi 4) are single-camera hosts — empty
rules, but still a host.json for symmetry.

## Migration order — least painful first

1. **astrocam → astro.capture.streaming.** Astrocam already speaks
   FITS, is night-only (cover transparent so 24h capture is fine for
   it, but mode-switching is trivial), no production publish pipeline
   to disturb. Use eclipticam v3w_night_daemon.py as the template.
   First user of the shared module beyond eclipticam — will reveal
   what was accidentally specific.
2. **astrocam-publish.timer on puppy.** Parallel to
   eclipticam-v3w-publish.timer. Same `bin/publish-night-cam` code,
   just `--camera astrocam`. (TODO_NEXT.md flagged this as item 4.)
3. **starcam → astro.capture.streaming.** Bigger lift because the Pi
   1B can't compress FITS in-line, so the format-on-Pi vs format-on-
   puppy split has to be configurable. `"format": "npy"` in camera.json
   + uploader handles `.npy → .fits.fz` on puppy. (This is the existing
   `to-fits-sweep` service.)
4. **skycam → astro.capture.streaming.** Cosmetic class. Validates the
   `"exposure_us": "auto"` path. By this point we've seen 3 sci cameras
   work and the abstraction is honest.
5. **Move daemons out of Berrylands/gardencam into astro/.** Matches
   the graduation plan already in motion. Once skycam is the last
   thing in gardencam, gardencam can probably retire.

Each step is independently shippable. The abstraction crystallises
through use, not through up-front design.

## Hard parts to be wary of

1. **Multi-camera state machines (eclipticam v3w gating v1)** belong
   in `astro.capture.host`, not in the streaming module. Get this
   boundary right or every camera will start sprouting cross-camera
   hooks.

2. **Capture format varies for real reasons.** skycam JPG is cheap +
   human-viewable, starcam .npy is because the Pi 1B can't compress,
   astrocam/eclipticam .fits.fz is because the Pi can. Format must be
   a config knob, not a hardcoded choice.

3. **Non-streaming paths are still useful.** Sparse capture (eclipticam
   day at 1/min) doesn't need the camera held open; per-tick
   rpicam-still is fine. The framework should allow both, not force
   streaming everywhere.

4. **Production cameras can't be down.** skycam and starcam are live.
   Migrate one at a time, with the old daemon left running until the
   new one has shown a full week of clean output. Don't refactor in
   place.

## Open questions

- Does `host.json` belong in the per-host repo dir (eg `eclipticam/`)
  or at a fleet level? Probably per-host (it describes physical
  arrangement).
- Mode-trigger DSL: the JSON `"enter_when": "lum < 0.0005"` is shown as
  a string above. Either parse it (small expr lang, neat) or make it
  structured (`{"field": "lum", "op": "<", "value": 0.0005}`, verbose
  but lint-able). Lean structured.
- Where does the sun-altitude calculation live? `astro.process` (it's a
  physics calc) or `astro.capture` (only capture uses it)? Probably
  `astro.location` as a new module — location is already a sibling
  config.
