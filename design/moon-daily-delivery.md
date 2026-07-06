# Daily moon delivery — automated on eclipticam

> **PARTLY ABANDONED 2026-07-06.** The **moon-net render + publish** is retired
> (deliverables removed from site/pipeline/S3; Altair star-ID superseded the
> anchoring; not needed for the quests). The **moon extraction / montage**
> (`moon-extract`, `moon-track`, `moon-deliver`) is KEPT as a real v3w
> deliverable. So: moon crops/montage stay; the moon-NET part is gone. See
> `retire-moon-marking-v1.md`.

**Goal:** every night, automatically extract the moon from v3w night frames,
render the cumulative moon-net, and publish both, with no hand-running.

**Decided 2026-07-02:** runs **on eclipticam**, on a nightly systemd timer.

## Why eclipticam

**eclipticam is taking over the processing puppy was doing and becoming a
self-contained astronomy appliance** (decided 2026-07-02). So the daily
moon delivery is not a special carve-out on an otherwise-capture-only Pi —
it is the **leading edge of eclipticam's full stage-3 role**. Puppy is
being retired from eclipticam processing.

⚠️ STALE DOCS: `services/astro-process.env.eclipticam` still says the Pi
does NOT run stage-3 ("~13x slower reading frames back over NFS", CAMERAS=
""). That was written before (a) the local-SSD migration and (b) this
appliance decision — it is now wrong and should be updated when stage-3
moves to eclipticam. The env comment itself gated on the unblocking
condition: "*A Pi can only do the pipeline once it gains its own LOCAL
storage.*" — which is now met.

Why it works now:
- Frames are on eclipticam's **local SSD** — no NFS read-back penalty.
- Measured: moon-extract ~**1.1 s/frame on eclipticam** vs 1.5 s on pip
  over NFS. A night (~100-200 in-FOV frames) = ~3-5 min.
- The moon step is light (one debayer + bright-blob find per frame).

Fits `project-astro-appliance-vision`: the camera Pi delivers its own
products over wifi, no dependence on puppy.

## Pipeline (one wrapper script, `services/moon-daily-run.sh`)

For the just-finished night (noon-rollover; default = last night):
1. `moon-extract --camera eclipticam-v3w --night <N> --mode night
   --out <cropdir>` — EXIF-tagged moon JPEGs (only in-FOV frames).
2. `moon-overlay --camera eclipticam-v3w --extend --publish` — redraw
   moon-net.png (auto-backdrop = most-recent max-stack) and upload to
   `s3://astro-berrylands-eu-west-1/eclipticam-v3w/moon-net.png`.
3. Publish the crops: a moon montage / the night's crop set to
   `s3://.../eclipticam-v3w/nights/<N>/moon/` (TBD exact form — a contact
   sheet or an mp4 of the disc drifting is the "wow"; the raw crops are the
   science). START with the render only; add crop delivery once the form
   is chosen.

## Trigger

`services/moon-daily.timer` + `.service` on eclipticam, modelled on
`storage-report.timer`. Fire once daily in the late morning (after the
night is complete and the noon-rollover has ticked) — e.g. `OnCalendar=
*-*-* 09:00` Europe/London. `Persistent=true` so a missed run (Pi
asleep/offline) catches up.

Deploy via ansible: add to `roles/eclipticam-astro` (templates + enable),
gated by a host_var like `enable_moon_daily`. NOT hand-installed.

## Open questions
- **Crop delivery form**: contact sheet? mp4 loop of the disc drifting
  (like the sweep mp4s)? raw crops in a tarball? Decide before wiring
  step 3. Render (step 2) can ship first.
- **Retention**: the crops are derived; keep on S3 or regenerate on
  demand? Ship-and-free per GLOBAL.md — probably keep only the render +
  a montage, not every raw crop, long-term.
- **v1**: no night capture yet, no pointing model — out of scope until
  v1 night HDR lands (`design/v1-night-hdr.md`).

## 2-Claude boundary (this session)
This work touches ONLY: `bin/moon-*`, `mark-moon-net`, `moon-overlay`,
`services/moon-daily.*`, and the eclipticam-astro role's moon bits. It does
NOT touch `eclipticam/` capture code, `camera.json` calibration values, or
`detrans-sweep` (the other Claude's live edits).
