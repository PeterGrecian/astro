# astro — project context

Scientific astronomy image processing. Sibling repo to
`~/photography/timelapse/starcam/`; **not** part of the timelapse
pipeline. The boundary is intent: timelapse repos make videos for
humans; astro makes measurements for science.

## Pipeline (target)

```
camerapi (OV5647, Pi 1B)
  └─ starcam_night_daemon.py (in Berrylands/gardencam/)
      └─ raw Bayer .npy → NFS → puppy
          └─ ~/starcam-frames/night/YYYY-MM-DD/HH/<epoch_ms>.npy
              └─ astro/bin/to-fits      → .fits.fz (Rice compressed)
                  └─ astro/bin/platesolve  → SIP + WCS in FITS header
                      └─ astro/bin/derotate → rotation-compensated stack
                          └─ accumulator images, arc geometry, stats
```

## Tooling decision (2026-05-22)

**Use astro community standards, not bespoke code.** The TODO.md
argued this and it's right. Decision recorded in DECISIONS.md.

- **FITS** for everything past the .npy raw buffer. Rice-compressed
  `.fits.fz` is ~2× smaller, natively readable by every tool.
- **astrometry.net** (`solve-field --tweak-order 3 --pixel-error 1`)
  for plate solving. Writes SIP polynomial distortion into the WCS
  header — handles the Pi V1 lens's heavy barrel distortion.
- **Siril / ASIFITSView / FITS Liberator** for visual inspection
  with proper auto-stretch / asinh. No need to rebuild the GIMP
  recipe in code.
- **oiiotool** (OpenImageIO) for any format conversion between FITS,
  EXR, and standard images.
- **DS9** for region-based inspection.
- **djv** for .exr sequence playback.
- **Splay support dropped** (was in TODO, now off).

## Conventions

- **Venv activation required** for every utility — they `import
  numpy, astropy, cv2`. Either `source ~/astro/.venv/bin/activate`
  or invoke as `~/astro/.venv/bin/python ~/astro/bin/<tool>`.
- **No `astro-` prefix on bin/ utilities.** They live in
  `~/astro/bin/` which is scope enough; the prefix would be
  superfluous.
- **No `/tmp/`** for working files (volatile — see GLOBAL.md). Use
  `~/tmp/starcam-night/<night>/` for per-night outputs.
- **Camera naming:** today only `starcam` (experimental zenith).
  Aspirational: `back`, `front`, `sky`, `experimental`. Utilities
  should accept `--camera` not hard-code the path.
- **Bayer pattern is SGBRG10** on the OV5647 — NOT SRGGB10. This is
  a recurring mistake; the daemon and any IO code must use SGBRG.
- **OV5647 (Camera Module v1) FOV** — per official Raspberry Pi docs:
  horizontal 53.50° ± 0.13°, vertical 41.41° ± 0.11°. Sensor 2592×1944,
  pixel pitch 1.4 µm, focal length 3.60 mm. On-axis plate scale
  ~0.0206°/px at full res, ~0.0413°/px at 2×2 binned. Lens has barrel
  distortion (magnitude not yet characterised).
- **Log-scale plots: base 2, not base 10.** Brightness, photon counts,
  and other dynamic-range plots should use `ax.set_yscale("log", base=2)`
  (matplotlib) so each gridline is one stop. Base 10 obscures the
  per-stop structure that matches how we reason about exposure.
- **Night dir = noon-noon rollover.** The "night of 2026-05-21" is
  2026-05-21 12:00 → 2026-05-22 12:00 (Europe/London noon, so the
  whole observing session lives under one date string).

## Related repos

- **`Berrylands/gardencam/starcam_night_daemon.py`** — Pi-side
  capture, ships raw .npy to puppy. Lives there because Berrylands
  owns everything up to the file landing on puppy.
- **`~/photography/timelapse/starcam/`** — day-mode timelapse,
  pretty pictures. **Different repo, different goals.**

## State as of 2026-05-22

- Repo just created. Skeleton only.
- Two nights of raw data on puppy: 2026-05-21 (90 GB), 2026-05-22
  (80 GB, still landing).
- GC working, 172 GB free on puppy.
- First utilities to land: `bin/night-stats` (brightness CSV per
  night), `bin/night-dir` (noon-rollover date helper), then
  `bin/to-fits` (the bottleneck conversion that unlocks everything
  else).
