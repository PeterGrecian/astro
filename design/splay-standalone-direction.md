# Splay standalone — direction notes

A Christmas project sketch (2026). Splay (= "(di)splay", not "still
player") becomes a **standalone, GPU-accelerated** viewer for astro
artefacts. The website player stays as it is for public visitors;
Splay is for the operator at a real machine with real hardware.

## Why two runtimes (not one)

- The web player is a known-good HTML5 video shell. Visitors don't
  need shader controls; pre-rendered mp4s are exactly what they
  want.
- Splay is for the operator: shader-driven stretch / LUT / stereo /
  live MCI / zoom. None of that needs to ship to a browser.
- Two codebases is more code, but each is idiomatic. A "one codebase
  via Electron/Tauri" attempt would compromise both — Electron
  carries a 60MB Chrome with it, and a thin webview Splay can't do
  the GPU work that's the whole point.

The bridge between them is **the JSON + S3 layer**, not code. See
`design/meta-conventions.md`.

## Target stack

Likely: **Python + moderngl + ImGui** (pyimgui or dear-pygui).

- Python because the rest of astro is Python — no separate build,
  same FITS / numpy / astropy paths, easy to call the existing
  `astro.process.bayer.bin2x2()` etc.
- moderngl over raw pyOpenGL because it's cleaner and modern OpenGL
  is what the GPU actually wants.
- ImGui for controls because it's instant-mode, fast to iterate,
  and doesn't impose a widget hierarchy. Suits the "tweak a slider,
  see it live" workflow.

Alternatives considered:
- **pygame + PyOpenGL** — fine, but pygame's event loop is awkward
  for tool-style apps. Better for games.
- **Qt + QtQuick + ShaderEffect** — industrial-strength but heavy.
  Reach for it if Splay grows into a serious editor.
- **Rust + wgpu + egui** — would be a learning project unto itself.
  Save for the version after.

## Inputs

Splay reads from S3 (canonical) or from local cache (faster).
Sources in priority:

1. **mp4** — for playback, what the website also shows. Frame-by-
   frame via PyAV or opencv.
2. **JPEG** — single-image artefacts (max.jpg, derot.jpg, thumb.jpg).
3. **FITS** — `astro.frames.list_night_frames` gives a sorted
   `(utc, path)` list; mmap'd reads via `astropy.io.fits.open(...,
   memmap=True)`. This is the path where Splay diverges most from
   the website — direct FITS access enables stretch / debayer
   control at full bit-depth, not just the 8-bit JPEG the website
   sees.

## Output

Mostly: just on screen. No file output beyond an optional "snapshot
as PNG" button. The point of Splay is *interactive exploration*; if
a particular set of knobs proves out, the operator codifies them as
a parametric `bin/astro-experiment` invocation that ends up on the
website for everyone.

## Shaders

First useful set:

- **asinh stretch** with slider for the asinh strength and lo/hi
  percentile bounds. The single most valuable interactive control
  on this kind of data.
- **LUT** (false-colour, magnitude). One uniform `sampler1D`,
  trivial.
- **Stereo display** — anaglyph and SBS for the photography
  stereo-viewer unification (TODO-other.md line 14). A single
  shader with mode selector.
- **Live MCI** — frame blending between two input textures by `t`.
  Cheaper than ffmpeg minterpolate; the operator can scrub through
  a sweep without rendering anything in advance.
- **Per-pixel mean / sigma / max overlay** — for diff-sweep-style
  exploration without rendering N variants. The current
  `--mean-mult K` and `--noise-floor-mult M` knobs become two
  sliders.

## Out of scope (initially)

- **No editing.** Splay is read-only — it doesn't write back into
  the astro pipeline. If you want a knob in production, you put it
  in `publish-night-cam` or `astro-experiment`.
- **No catalog overlay.** The Gaia catalog-match work (TODO.md
  parked section) is its own thing; Splay can grow it later.
- **No headless mode.** Splay is for a human at a screen. Anything
  scriptable lives in the CLI tools.

## Hardware ask

A discrete GPU with ≥4 GB VRAM. The IMX708 at full 4608×2592 is
35 MB per float frame, plenty of room for a buffer of N frames.
RTX 3050 or used 2060 / 4060 would all be overkill for the imagery
and useful for general work. Integrated Intel/AMD probably fine
too but with less headroom for stereo or multi-stream.

## Action now

- Capture this and `design/meta-conventions.md` so the Christmas
  project picks up cleanly.
- Maintain the JSON conventions (meta-conventions.md) immediately
  — they're load-bearing for the experiments machinery *today*,
  not just for Splay.
- Don't start any Splay code yet. The natural pull is to play with
  shaders; resist until the data layer is solid.
