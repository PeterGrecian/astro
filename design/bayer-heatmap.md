# Bayer heat-maps — reading a frame at the photosite

*Written 2026-08-20, back-filling the doc `bayer_heatmap.py` cited from
2026-08-01 but which was never written. The code lived unversioned in
muppet's home dir until it was folded into `astro/bayer.py` + `bin/bayer-*`.*

## Why look at the mosaic at all

Every tool above the capture layer works in demosaiced or luminance space.
Both average over the 2×2 Bayer cell — and that average is exactly what
hides undersampling.

On these cameras a star's PSF is comparable to the pixel pitch. A source
therefore lands on **one Bayer phase** and simply never illuminates the
photosites of the other colours a cell away. Demosaic that and you get a
plausible-looking coloured blob that is mostly interpolation. Look at the
raw mosaic instead and you see the truth: a checkerboard, with real
measurements on one sublattice and sky on the others.

This matters to the map because sub-pixel reconstruction feeds on exactly
this structure. The inter-frame dither moves a source across the mosaic
between exposures, so different frames sample different phases of the same
PSF. That is signal, not noise — but only if you can see it.

## The parity trap

`bayer_channel()` and everything built on it take **global, uncracked**
pixel coordinates. Parity is a property of the sensor and the capture
orientation, not of your crop; take a crop starting at an odd row and every
colour flips.

The pattern names the top-left 2×2 read row-major. An `S` prefix means
"sensor", not a colour, and is stripped:

| Sensor | Pattern | Used by |
|---|---|---|
| IMX708 | `RGGB` | astrocam v3s, eclipticam v3w |
| IMX219 | `SBGGR` → `BGGR` | astrocam v2 |
| OV5647 | `SGBRG` → `GBRG` | starcam, eclipticam v1 |

**A 180° rotation swaps the diagonal.** `StreamingConfig.rotation_180`
rotates in capture (`bayer[::-1,::-1]`), so an RGGB sensor stored rotated is
`BGGR` in stored coordinates — while `BAYERPAT` in the header still names
the sensor. Get this backwards and a red star reads blue, and an "empty red
channel" is really an empty blue one.

Do not trust the keyword. `bin/bayer-parity` settles it empirically: it sums
flux by global `(y%2, x%2)` phase on a real star and names the colour each
phase would carry under both hypotheses. It reports INCONCLUSIVE when the
two agree — which they do whenever the green phases dominate, since both
hypotheses put G on the same two cells. Pick a star where R and B differ.

## Per-channel sky is not optional

The four phases **do not share a background**. They differ in spectral
response and in black level. Measured on astrocam's IMX708 (2026-07-31,
frame 1785550053740), whole-frame medians:

| phase | colour | median | std | max |
|---|---|---|---|---|
| (0,0) | R | 85.0 | 7.7 | 716 |
| (0,1) | G | 114.0 | 17.7 | 1017 |
| (1,0) | G | 114.0 | 17.7 | 1015 |
| (1,1) | B | 94.0 | 10.7 | 1023 |

Red's sky sits **29 ADU below** green's. Subtract a median taken across all
four phases at once and red comes out **negative** on a real star:

```
star at (4343, 698), 8x8 box
  mixed sky (87):        R  -5    G  35    B  21     <- "red is dead"
  per-channel sky:       R  +7    G  35    B  28     <- red is alive, just weak
```

That artefact is precisely the "dead channel" signature the 2026-08-01
scripts were written to investigate, and those scripts had the bug. Use
`local_sky_by_channel()`, which is now the default in every tool here.

The independent check is `bayer-channels --stats`: a dead channel shows
near-zero std, a stuck value and no bright tail. Red's std is 7.7 with a
tail to 716 — alive. It never saturates anywhere in the frame while G and B
both reach 1023, which is a real and separate finding about the red
response to an urban sky.

## Assume-white, and why it is capped

Removing the sensor's 2× green weighting makes the PSF shape legible, but
naive white balance on a background-subtracted patch divides by a channel
mean that may be ~0. On a red star the blue channel is genuinely near-empty,
and balancing it produced a gain of **×447** that detonated blue noise into
four huge false-bright cells.

`assume_white()` has two guards, and both are load-bearing:

- **`min_signal`** — below this fraction of G the channel is *genuinely
  empty* (a real colour, not a calibration problem), so leave it at gain 1.0
  and let it stay dark.
- **`max_gain`** — a neutral star needs gains ~1.0; only near-empty channels
  ever reach the cap, and capping them is the correct behaviour.

`assume_white_rgb()` is the same logic on already-demosaiced planes.

For a rectangle of mostly sky, `bin/rect-heat`'s grey-world balance is the
right assumption instead: it scales R and B so the *rectangle average* is
neutral. The two answer different questions — grey-world reveals colour
structure against the background, assume-white reveals the PSF.

## ADU scale

These tools assume 10-bit LSB-aligned raw (0..1023), which is what the whole
archive is since the 2026-08-20 repack (`bin/repack-msb`). A frame carrying
`RAWSHIFT` in its header has been converted; astrocam frames never needed it
(Pi 4 / VC6 already LSB-aligns). The fixed thresholds in these tools —
"20 ADU above sky is a candidate star", `join-trail --threshold 12` — are
10-bit numbers and would be meaningless against MSB-aligned data.

## The tools

| Tool | Question |
|---|---|
| `bayer-heatmap` | what does this PSF look like at the photosite? `--strip` for a filmstrip across frames |
| `bayer-parity` | which phase carries the flux — is the stored pattern the header's, or rotated? |
| `bayer-channels` | `--stats` dead-or-undersampled, `--at` one source, `--follow` across frames |
| `join-trail` | N frames' streaks joined into the arc actually traced; `--rgb` for colour |
| `rect-heat` | a splay-probed rectangle at ADU level, raw and grey-world balanced |

`bayer-channels --follow` emits `frame_id,x,y` that feeds `bayer-heatmap
--strip`, so following a star and rendering its filmstrip is two commands.

## Still open

- **`splay` never got the feature.** `bayer_heatmap.py` described itself as
  the reference implementation for one. Rendering a Bayer heat-map from a
  splay probe rectangle, in-place, is still the natural home for this.
- **Parity is unconfirmed for IMX219 and OV5647.** Only the IMX708/RGGB path
  has been checked against a real star.
