have the website have eclipticam output per day like a calendar like starcam.

put the colour sweep video in each day as the story of the night 
and the brightness curve

backfill the existing eclipticam nights

## astrocam capture-write pipeline (2026-06-13)

Measured 11.73 s mean cadence on 2026-06-13 00 UTC: 9.6 s of actual
integration (8 × 1.2 s coadd) + ~2.1 s of FITS write + starfind
overhead per output. ~82% duty cycle.

Move capture writes to a **ramdisk** (`/dev/shm` or a `tmpfs` mount,
sized to ~1 night of frames so the writer never blocks). Move
processing — bin, starfind, FITS encode/compress, badpix flag — to
**async workers** using the queue tools in `super/bin/` (the same
async-file-transfer pattern the rest of the fleet uses). Capture
loop becomes write-uncompressed-numpy-to-ramdisk-and-go-back-to-the-camera.

This should close the per-frame overhead to under 200 ms (just the
raw → ramdisk write) so we capture at the camera's natural rate
(IMX219 at 1.2 s × 8 coadd ≈ 9.6 s ideal cadence) instead of the
current 11.7 s.

Notes for astrocam specifically:
- Cover is transparent so the camera can stay running through day;
  no need to coordinate with cover-open before each shot.
- Camera is in the shade — sun never directly illuminates it, so
  the thermal-burn concern doesn't apply.
- v3w on eclipticam wants the same treatment but with the streaming-
  daemon design (see eclipticam/v3w-streaming-daemon.md), since it
  currently uses rpicam-still per tick and has different overhead.



