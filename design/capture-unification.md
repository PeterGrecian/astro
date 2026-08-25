# Capture unification — design notes

**Status** (re-checked 2026-08-12, owned by the `astro-capture` strand):
partly implemented. The old status line ("design, not implemented beyond
the eclipticam v3w streaming daemon", 2026-06-15) understated it — two
live cameras now share the streaming engine:

| Piece | State |
|---|---|
| `astro/capture/streaming.py` | ✔ exists |
| eclipticam v3w on the shared module | ✔ `eclipticam/v3w_night_daemon.py` |
| **astrocam on the shared module** (migration step 1) | ✔ **done** — `astrocam/astrocam_v3_night_daemon.py` is a thin wrapper; imx219 `astrocam/capture.py` retired 2026-07-29 |
| starcam (step 3) | ✘ **moot — camera decommissioned 2026-08-02** |
| skycam (step 4) | ✘ still in `Berrylands/gardencam` |
| eclipticam v1 | ✘ hand-rolled, does not import the shared module |
| `uploader.py` / `modes.py` / `host.py` / `__main__.py` | ✘ not written; `astro/capture/` holds only `__init__.py` + `streaming.py` |

**Direction correction — share the conventions, not the code path**
(Peter, 2026-08-11). "Target shape" and "Migration order" below are
written bottom-up-by-absorption: one generic engine that each camera is
*migrated into* until per-camera dirs hold only `camera.json`. That is
not the model. The per-camera work is legitimately and permanently
camera-specific and **stays put**; the unified pipeline is assembled
**from** those parts by *wrapping* them. Unification is a layer over the
device work, not a solvent that dissolves it.

Consequences: the EOS 2000D (gphoto2/USB) is not an awkward exception
but the normal case seen clearly — it has its own mechanism, as every
camera does. `streaming.py` is demoted from "the engine" to *one shared
implementation*, the thing the two picamera2 cameras happen to have in
common. The remaining migrations (v1, skycam) still stand, but because
those are Pi cameras that would genuinely share that mechanism — not
because everything must end up in the module. The real substance of the
unified layer is the **conventions**, below.

## The conventions — what actually binds every camera

These hold across gphoto2/USB and picamera2/CSI alike, and none of them
requires a shared code path. This is the unified layer's real content.

**1. A frame name is never reused.** A capture run that restarts must
not overwrite frames from an earlier run of the same night. Restart-safe
naming is the rule; how a camera achieves it is its own business.

**2. One capture = one frame.** A single logical capture must fire the
shutter exactly once. (The canon violated this on 08-10: Continuous
Shooting drive mode meant holding the full press fired ~20 frames of
which one was downloaded — pure shutter wear on a body rated ~100k
actuations.)

### Audit: frame naming across all five cameras (2026-08-12)

Prompted by the canon's 08-10 restart-collision bug (pass numbering
restarted at 1 after an abort, so a re-run silently overwrote the
previous run — this destroyed ~1,000 frames on 07-28 and, on 08-10, the
only frames containing an aircraft). The question was whether the Pi
daemons carry the same latent bug. **They do not** — but they satisfy
rule 1 by three different mechanisms, none of them a shared one:

| Camera | Naming | Restart-safe? | Mechanism |
|---|---|---|---|
| astrocam (imx708) | `<epoch_ms>.fits.fz` | ✔ | monotonic wall clock |
| eclipticam v3w | `<epoch_ms>.fits.fz` | ✔ | same (shared `streaming.py`) |
| skycam | `<epoch_ms>.jpg` | ✔ | same convention, **independently arrived at** in `Berrylands/gardencam` |
| eclipticam v1 | `NNNN.fits.fz` per hour dir | ✔ | scans the dir for `max(seq)+1` on every write — continues rather than restarts |
| **EOS 2000D** | `<RUN_TAG>_pNN_iNN_dNN` | ✔ | per-run UTC `RUN_TAG` stamped into the stem |

So the estate is currently **sound on rule 1**, and the run-tag audit's
finding is not a bug list but a convention observation: `epoch_ms` is the
de-facto house naming convention — three cameras converged on it
independently, and it is carried unchanged through the upload seam
(`astrocam_v3_uploader.py` files by `epoch_ms` into
`<night>/HH/<epoch_ms>.fits.fz`, no renumbering). The `RUN_TAG` scheme
in `bin/eos-focus-cycle` is the DSLR's answer to the same rule, needed
because gphoto2 pass/index numbering restarts where a clock does not.

Verified empirically on astrocam 2026-08-11: 426 frames, 426 distinct
names, minimum inter-frame gap 59.79 s against a 1 ms name resolution.

**The one theoretical hole**, recorded rather than fixed: `epoch_ms` is
read from `time.time()` at capture, so two frames landing inside the
same millisecond would collide, and the writer does not check
(`writeto(..., overwrite=True)` then rename). At the cameras' real
cadences (~60 s) the margin is ~5 orders of magnitude, so this is not
worth code today. It becomes real only if a camera ever runs a fast
burst, or if the wall clock steps backwards (NTP correction mid-night).
**If a burst mode is ever added, this must be revisited first.**

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

## Streaming + AE coexist (2026-06-16)

picamera2 streaming mode and auto-exposure are independent — `AeEnable`
is a per-tick control on the held-open camera, not a session-level
choice. So one streaming session can run AE-on by day and AE-off with
a locked 55 s exposure by night, switching at dusk/dawn transitions
without reopening the camera.

Implication for `camera.json` modes:
```jsonc
"day":   { "ae": true,  "exposure_us": "auto",          "gain": "auto" }
"night": { "ae": false, "exposure_us": "cadence - readout",
                        "gain": 1.0 }
```

Per-frame brightness stays comparable across modes because
`per_s = mean / (exposure_s × gain)` already normalises out whatever
AE chose — this is what brightness.csv records and what stage 1 reads.

Two operational notes:
- **AE settling at dawn**: re-enabling AE after a 55 s locked night
  exposure takes a few frames to converge. Either accept the bad
  frames or bound AE with `ExposureTimeRange` / `AnalogueGainRange`
  so the first day frame is already in the ballpark.
- **24h streaming is opt-in per camera, not the default.** Astrocam
  is fine (transparent cover, shaded, no dark-current concern).
  Eclipticam v3w may show elevated dark current at night if kept
  warm all day — needs measurement before committing. A
  `camera.json["stream_24h"]: false` flag lets a camera return to
  start-of-night / stop-at-dawn while everything else stays unified.

## Target shape

> **Read with the direction correction at the top.** This section is
> written in the absorption model — "per-camera dirs hold **only**
> camera.json". That is not the target. The modules below are a *wrapper*
> layer over per-camera implementations that stay where they are, and
> they crystallise through use rather than being written up front.

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

> **Superseded in part — see the status table at the top.** Steps 1 and 2
> are **done**; step 3 (starcam) is **moot**, the camera was
> decommissioned 2026-08-02. The live remainder is skycam (step 4), the
> gardencam move (step 5), and **eclipticam v1**, which this list never
> mentioned but is now the most interesting migration: it is the
> multi-camera-per-host case (v3w's mode gates whether v1 captures at
> all), which is what `host.py` is *for*.

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

## Storage and Buffering Architecture (ramfs / tmpfs vs direct storage)

The historical role of an intermediate RAM buffer (`/var/lib/*-buffer` tmpfs) differs across instruments, but streaming mode fundamentally changes the latency and buffering requirements:

1. **astrocam (NFS mount storage):**
   - Uses NFS mounts directly to `muppet`'s `bigstore`.
   - Originally used a local `tmpfs` buffer under the assumption of requiring low-latency writes to decouple capture from network I/O.
   - **Streaming reality:** In streaming mode, Picamera2/libcamera buffers frame requests internally in memory, and with ~60s exposure cadences, there is ample wall-clock time between frame deliveries (~55s) for synchronous network writes. The separate `tmpfs` buffer is therefore probably not needed for latency.

2. **eclipticam (local fast SSD storage):**
   - Uses a local fast SSD (`/mnt/ssd`) for night capture, forwarding/shipping the completed night tree to central storage at the end of the night.
   - Also operates in streaming mode.
   - **Streaming reality:** Because writes land directly on local SSD flash and streaming mode provides internal driver buffering, eclipticam **definitely does not need ramfs/tmpfs** for capture latency or throughput.

3. **Risk of brittle RAM buffers:**
   - Staging to a constricted `tmpfs` (e.g. 50 MB) creates a severe point of failure: if an uploader service experiences a startup race (e.g. waiting for USB SSD enumeration) or network stall, the buffer exhausts in ~4 frames, fatally crashing compression worker threads while masking the failure from systemd.

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
