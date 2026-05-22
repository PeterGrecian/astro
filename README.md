# astro

Scientific image processing for astronomy: long-baseline accumulation,
plate solving, FITS workflows, arc fitting, derotation.

Not to be confused with `~/photography/timelapse/starcam/` — that
sibling repo is about pretty-pictures-as-time-lapse-video. This one
is about measurement: turning long stacks of Bayer raws into
WCS-annotated images and arc geometry.

## Scope

| Input | Bayer raw `.npy` frames from `starcam_night_daemon` (and future cameras: back, front, sky) on puppy at `~/<cam>-frames/night/YYYY-MM-DD/HH/<epoch_ms>.npy` |
|---|---|
| Output | `.fits.fz` (Rice-compressed, plate-solved with SIP), accumulator images (`.fits`/`.exr`), arc geometry, sky-quality stats |
| Display | community tools: Siril, ASIFITSView, FITS Liberator, oiiotool, DS9, djv — no bespoke viewer |

## Cameras

Aspirational layout: `back`, `front`, `sky` (clouds), `experimental`.
Currently only the experimental zenith-pointing OV5647 is wired up
(via `Berrylands/gardencam/starcam_night_daemon.py`).

## Layout

```
astro/
├── bin/        # human-usable CLI utilities, no AI required; in $PATH
├── astro/      # importable Python package
├── notes/      # design notes, tooling refs, feasibility studies
├── README.md
├── CLAUDE.md   # context for Claude Code
├── DECISIONS.md
├── TODO.md
└── requirements.txt
```

## Setup

```bash
cd ~/astro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo apt-get install astrometry.net bsdmainutils siril
```

Activate the venv before running any utility:

```bash
source ~/astro/.venv/bin/activate
night-stats 2026-05-22
```

## Conventions

- **Night dir = noon-rollover.** A "night" is the 24 h window centred
  on solar midnight. `night-dir 2026-05-22T03:00Z` returns
  `2026-05-21` (the night that started 21st evening).
- **Bayer pattern:** SGBRG10 on OV5647 (NOT SRGGB10 — this caught us out).
- **Timestamps:** internal = UTC (epoch_ms in filenames); human = Europe/London.
- **No `/tmp/`** for working files — use `~/tmp/`, `~/astro/tmp/`, or a
  per-night dir under `~/tmp/starcam-night/<night>/`.
