# Cold storage & squashed-frame format

starcam is being decommissioned. Raw `.fits.fz` per-frame data is
~270 GB across 14 substantive nights — too much to keep online, too
valuable to delete. This doc records what we're keeping where, in
what form, and why.

## Tiers

| Tier | Medium | Layout | Notes |
|---|---|---|---|
| Hot | local disk (puppy / muppet) | `~/starcam-frames/night/<night>/` or `~/starcam-backup/<night>/` | The "online" copy. May be squashed in place. |
| Warm | USB stick(s) | `/mnt/astrobackup/starcam/night/<night>/` | Browsable directory tree + `MANIFEST.sha256`. ASTROBACKUP (58 GB) is the first stick; ASTROBACKUP2 (32 GB) is the second. |
| Cold | S3 Deep Archive | `s3://astro-berrylands-eu-west-1/cold/starcam/night/<night>/starcam-night-<night>.tar` | One uncompressed tar per night. sha256 in S3 object metadata + `.sha256` sidecar in STANDARD. |

R2 was considered but rejected — see [feedback-r2-vs-s3](~/.claude/projects/-home-peter-astro/memory/feedback-r2-vs-s3.md): R2 is reserved for large mp4s; S3 is the default for archive.

## Squashed frame format

Each night is reduced to two derived per-frame products before
shipping to cold storage:

| Source | Output | N | Cadence | Tool |
|---|---|---:|---|---|
| `HH/` raw Bayer (2592×1944, 12-bit in uint16) | `HH-sum8/` | 8 | one summed frame ≈ every 32 s | `bin/pair-sum --n 8` |
| `HHb/` binned (1296×972, 2×2 sum-bin, uint16) | `HHb-sum2/` | 2 | one summed frame ≈ every 6 s | `bin/pair-sum --n 2` |

Output is uint32 (BITPIX=32) — lossless for sums up to ~16 of 12-bit
raw values. Output filenames are `HH-MM-SS.fits.fz` (UTC) taken from
the first source frame, so directory listings are time-sortable and
human-readable. Full source provenance is preserved in the FITS header:

```
PAIRED   = T
NSUMMED  = N
EPOCH1..N    = <ms>           source epoch_ms per frame
DATEOBS1..N  = '...'          source DATE-OBS per frame
SRCFL1..N    = '...'          source filename per frame
EXPTIME      = <sum>          combined exposure (s)
DATE-OBS     = (DATEOBS1)     first frame, for sortability
HISTORY      pair-sum f1 + f2 [+ ...]
```

Typical compression: raw → sum8 ≈ 0.20× raw size. binned → sum2 ≈
0.67× binned size. Combined squashed deliverable ≈ 0.17× original
raw bytes.

## Sticks vs Glacier

USB sticks are first-call cold storage (we already have them); Glacier
Deep Archive is the durable second copy. Costs roughly $0.07/year per
night at Deep Archive pricing. We never plan to egress — backfill from
this means "when our software improves, re-thaw and rerun".

Sticks are cheap-and-rubbish hardware; treat each as one copy. Stick
contents are tracked per-night in `whereisallthedata.csv`. Each night
on a stick has a `MANIFEST.sha256` written and verified at copy time.

## Unsquashed nights kept for comparison

To validate the squashed pipeline against the raw pipeline, we keep
full raw + binned for a subset of nights on puppy. The plan is:

1. Run the existing nightly-cam pipeline on the **raw** night → known-good outputs.
2. Run the same pipeline on the **squashed** night (sum8 / sum2 frames) → comparison outputs.
3. Compare derot stacks, plate solutions, pole fits, brightness curves, frame counts.

If the squashed results are scientifically equivalent, future
captures can be squashed at acquisition time (or shortly after) and
we keep ~17× less data per night.

**Nights to keep raw + binned on puppy** (the "ground truth" set):
- `2026-05-23` — darkest night (darkest-hour median 13), clearest sky
- `2026-05-24` — bright reference, normal night
- `2026-06-04` — recent, dark (median 19), short night

These three span the brightness range without burning the whole 188 GB
of remaining raw data. The other puppy nights can be squashed in place
once the comparison passes.

## Naming convention

Suffix rules for derived directories:

- `HH/` — raw per-frame Bayer (epoch_ms-named)
- `HHb/` — binned per-frame (sequential 0001…)
- `HH-sumN/` — pair-summed raw, N source frames per output
- `HHb-sumN/` — pair-summed binned

Lowercase letters chain in order (`b` = binned, `-sumN` = summed by
N). Future transforms add new suffixes; `-sum4`, `-sum2` etc. are all
products of the same `bin/pair-sum` tool.

## Per-camera scoping

Cold-storage paths include camera + mode:

- Stick: `/mnt/astrobackup/<camera>/<mode>/<night>/`
- S3: `s3://astro-berrylands-eu-west-1/cold/<camera>/<mode>/<night>/`

`<mode>` is `night` (long-exposure dark-sky) vs `day` (short-exposure
sun/moon/twilight). All current starcam data is `night` mode.

## Status

See `whereisallthedata.csv` for the live per-night inventory across
hosts and tiers (squashed sizes, stick presence, Glacier presence,
source-deletion state).
