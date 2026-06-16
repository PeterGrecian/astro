# astro

Scientific image processing for a fleet of Pi-mounted astronomy
cameras: long-baseline accumulation, plate solving, FITS workflows,
arc fitting, derotation, and the per-night web deliverables that
sit on top.

Not to be confused with `~/photography/timelapse/starcam/` — that
sibling repo is about pretty-pictures-as-time-lapse-video. This one
is about measurement: turning long stacks of Bayer raws into stacked
images, brightness histories, and (eventually) catalog-matched
detections.

## Cameras

| Camera | Host | Sensor | Status |
|---|---|---|---|
| `astrocam` | astrocam (Pi 4) | IMX219 | live |
| `eclipticam-v1` | eclipticam | OV5647 | live |
| `eclipticam-v3w` | eclipticam | IMX708 | live |
| `starcam` | puppy (was zeropi) | OV5647 | decommissioned — cold archive only |

`eclipticam-v1` and `eclipticam-v3w` are two CameraConfigs sharing a
Pi. Each is a first-class camera with its own `camera.json`.

## Scope

| Input | Per-frame Bayer raws on the camera host, uploaded to puppy at `~/<camera>-frames/night/<night>/[<subcam>/]HH/<frame>` |
| Output | Per-night S3 deliverables under `s3://astro-berrylands-eu-west-1/<camera>/nights/<night>/`: stacked image, brightness plot, sweep MP4s, `summary.json`. Cold archive at `s3://.../cold/<camera>/<mode>/<night>/`. |
| Display | Splay (preferred), DS9, oiiotool, djv. No bespoke viewer. |

## Layout

```
astro/
├── bin/                    # CLI utilities (in $PATH after activate)
├── astro/                  # importable Python package
│   ├── config.py, frames.py, nightdir.py
│   ├── capture/            # generic picamera2 capture loop
│   ├── process/            # bayer, badpix, brightness, derot, pole, detect
│   └── present/            # render, privacy, summary, publish
├── astrocam/               # per-camera config + capture daemon
├── eclipticam/             # per-camera config + capture daemons (v1, v3w)
├── starcam/                # camera.json only — historical reprocess
├── services/               # systemd units (publish timers, capture services)
├── notes/                  # design notes / feasibility studies
├── legacy/                 # quarantined reference — see legacy/README.md
├── docs/                   # operational docs (pipeline.md, sg90.md)
├── README.md
├── CLAUDE.md
├── DECISIONS.md
├── COLD_STORAGE.md
├── TODO.md
└── requirements.txt
```

## Four stages, four executables

Production work runs as four continuous daemons, one per concern,
driven by config + a shared state record. CLAUDE.md has the full
diagram; the shape is:

| # | Stage | Host | Executable |
|---|---|---|---|
| 1 | Day/night state | each Pi + NFS host | `bin/astro-state` |
| 2 | Capture + on-Pi first-pass (Rice / bin) | camera Pi | `bin/astro-capture` |
| 3 | Twice-daily processing + S3 publish | NFS host | `bin/astro-process` |
| 4 | Storage management (squash / cold / prune) | NFS host | `bin/astro-storage` |

All four are Python, all four read `<camera>/camera.json`,
`host.json`, and the state record. Command-line flags exist for
dev/test only (re-running a specific night, restricting to a UTC
window, overriding the camera).

```bash
# Re-run last night's deliverables for one camera (dev/test override)
bin/astro-process --camera astrocam --night 2026-06-15

# Spot-check stack of a specific UTC window
bin/window-stack --camera eclipticam-v3w --night 2026-06-15 \
                 --window-start 23:00 --window-end 23:30
```

The four stage executables are the target shape. Today's pipeline
uses `bin/nightly-cam` + `bin/publish-night-cam` (which collapse
into `astro-process`) plus per-camera capture daemons (which collapse
into `astro-capture`). See `TODO.md` for the migration order.

## Setup

```bash
cd ~/astro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo apt-get install astrometry.net bsdmainutils
```

Activate the venv before running any utility:

```bash
source ~/astro/.venv/bin/activate
nightly-cam --camera astrocam --night 2026-06-15
```

## Conventions

- **Night dir = noon-rollover.** `night_of(utc)` returns
  `(utc - 12h).date()` — a "night" is one date, one directory, no
  straddle across UTC midnight.
- **Bayer per-sensor**: OV5647 = SGBRG10 (NOT SRGGB10), IMX708 = SRGGB10,
  IMX219 = see config. Always read from `camera.json`.
- **Timestamps:** internal = UTC; human-facing = Europe/London.
- **No `/tmp/`** for working files — use `~/tmp/`, `~/astro/tmp/`, or
  a per-night dir under `~/tmp/<camera>-night/<night>/`.
- **Per-sensor pedestal** in `camera.json` makes "stops above pedestal"
  comparable across cameras and nights.

See `CLAUDE.md` for the full pipeline shape and `DECISIONS.md` for
the load-bearing architectural choices.
