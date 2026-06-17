# Splay & web player — shared conventions

The pip-Splay (CPU, pygame, plugin-extensible) and the web advanced
video player on `petergrecian.co.uk` are different runtimes against
different workloads (stills/plugins vs pre-rendered video). They
share *vocabulary* so muscle memory transfers, not code.

Drafted 2026-06-17 from a conversation pinning down the gaps between
the two. Future Splay-GL (Christmas project) inherits these. The
web player is brought into line where it currently diverges.

## Principles

- **Same key = same idea everywhere.** Where an action exists in
  both runtimes it uses the same key. Where it only exists in one,
  the key in the other is free for a runtime-specific use.
- **Conventional over clever.** `Space` = play/pause. `←/→` = step.
  These are universal; we don't reinvent.
- **HUD shows what applies here.** Pressing `h` shows the help
  overlay for the *current* runtime + mode, not the union of every
  key in this doc. Stills don't list `Space`; video doesn't list
  `s` for frame-select.
- **Default to loop.** A sequence that reaches its end without
  explicit user action plays again. Single-pass requires an opt-out.

## Keybindings

Sorted by category.

### Transport (video + frame-sequence playback)

| Key | Action |
|---|---|
| `Space` | play / pause |
| `,` | play **backward** |
| `.` | play **forward** |
| `←` | step one frame back |
| `→` | step one frame forward |
| `<` (shift-`,`) | pace slower (geometric: 1× → ½× → ¼×) |
| `>` (shift-`.`) | pace faster (geometric: 1× → 2× → 4×) |
| `u` | cycle loop mode (loop / once / pingpong) |

Pace is a *setting* independent of play state — pressing `p` while
paused changes the next play's speed. Discrete steps `¼× ½× 1× 2×
4×`; `p`/`P` clamp at the extremes. Default = 1×.

Loop mode default = **loop**. A sequence that reaches its end plays
again without user action.

### Source switching (multi-stream)

| Key | Action |
|---|---|
| `↑` | previous source (cycle) |
| `↓` | next source (cycle) |
| `1`–`9` | jump to source N |

Source switches preserve playhead position. The playhead's *meaning*
is the alignment rule (see "Multi-stream alignment" below).

### Stills mode (Splay only)

| Key | Action |
|---|---|
| `s` | select current frame |
| `d` | deselect current frame |
| `l` | toggle list mode (all / selected only) |
| `a` | cycle sort (name / mtime / load order) |
| `w` | wipe between two most recently shown |
| `p` | pixel probe — cycle off → snapshot → live |
| `m` | toggle hot-pixel mask (shift-`m` toggles highlight) |

`l` = list mode is Splay's existing meaning. Video loop mode lives on
`u` to avoid stepping on Splay's pre-existing `l` / `p` / `m`.

### Clip marks (video only)

| Key | Action |
|---|---|
| `[` | mark current position as clip in |
| `]` | mark current position as clip out |
| `+` | add new clip at playhead |
| `-` | delete clip containing playhead |

### Display

| Key | Action |
|---|---|
| `h` | toggle HUD / help overlay |
| `f` | toggle fullscreen |
| `t` | toggle thumbnail / piano-roll strip |

### Quit (Splay only — web tab closes)

| Key | Action |
|---|---|
| `q` | quit |
| `Esc` | close HUD if open; otherwise quit |

## Frame-sequence playback (new in Splay)

Splay grows the ability to play a directory of stills as a
sequence, frame-by-frame, with the transport keys above.

- **Loading**: `splay <dir>` loads stills. If the count is large,
  uses mmap (kernel page cache) rather than pre-loading; first
  pass warms the cache, subsequent passes are RAM-fast.
- **Playback rate**: per-source default 60 fps. `p`/`P` step through
  the discrete set above. `,`/`.` set direction; `Space` toggles
  play/pause without changing direction.
- **Real-time mode** (future, `T`): each frame held for its actual
  capture cadence instead of constant fps. Useful where frame
  cadence is meaningful (1/min astronomy → played at 1/min is
  unwatchable; played at 60fps a night fits in a minute).

This collapses the still vs video distinction inside Splay —
stills are video at very low cadence, video is stills with extra
metadata.

## Multi-stream model

Splay grows the ability to load several sequences at once and
switch between them at the same playhead:

- **Loading**: `splay --sources A B C` (or `--sequences` — bikeshed)
  loads three sources. The first is what's showing; `↑/↓` cycles.
- **Alignment**: when switching from source A to source B, the
  playhead position transfers by:
  1. **timestamp** if both sources have per-frame timestamps
     (FITS DATE-OBS, epoch_ms filenames, mp4 PTS) — the same moment.
  2. **fraction** otherwise — frame at 30% of A → frame at 30% of B.
- **Wipe between streams**: pressing `w` enters wipe mode; a
  vertical divider appears mid-screen. Mouse drag (or `←`/`→` for
  keyboard) moves the divider. Left half = current source, right
  half = previous source, at the aligned playhead position.
- **Out of wipe**: another `w` exits.

## Piano roll

Splay and the web player share a horizontal time strip below the
image. Modes:

- **Single-source**: one row, position along X = time, playhead =
  vertical line. Optional brightness pegs (height = brightness)
  or thumbnails (sparse, every Nth frame).
- **Multi-stream**: one row per loaded source. Same X axis (time,
  aligned). Playhead crosses all rows. Source rows are clickable
  to switch + seek in one move.
- **Clip overlays** (video): clip bands rendered along the active
  source's row.

`t` toggles the strip on / off.

## HUD content rules

The `h` overlay shows only the keys that apply to the current
runtime + mode + loaded sources. Examples:

- **Splay-stills, one source**: select, deselect, list mode, wipe
  (between two stills), nav, sort, HUD, fullscreen, quit.
- **Splay-video, multi-stream**: transport, pace, loop mode, source
  switch, wipe (between streams), nav, HUD, fullscreen, piano roll
  toggle, quit.
- **Web player, video, multi-stream**: same as above minus quit
  minus stills-mode keys.

Don't show keys that don't apply. The HUD is contextual help, not
a reference card.

## Where each runtime diverges (and stays diverged)

- **Splay** — single-user, keyboard, local, plugin-extensible
  (`apps/distortion.py`, `apps/skymask.py`). Saves parameter state
  to JSON sidecars. No share-URL.
- **Web player** — multi-user, mouse-friendly fallbacks for every
  key, share-URL `?in=&out=&clips=` for stateless permalinking.
  No plugins. No save-to-disk.

The share-URL ↔ JSON-sidecar pair is a natural symmetry: both are
"capture the current view to come back to." A future iteration
could let Splay write a share-URL too (a `splay://` or local URL
that recreates the launch invocation). Not now.

## Web player changes to bring into convention

- `Space` (already): play/pause — keep.
- `←`/`→` (already): step — keep.
- `↑`/`↓` (already): source switch — keep.
- `1`–`9` (was source jump) → **0–4 zoom / brightness** (Splay convention).
  `0` fit, `1` 1×, `2` 2×, `3` darker, `4` brighter. Source jump
  dropped (cycle via `↑/↓` is enough at small N).
- `,`/`.`: speed up/down → **transport backward/forward**. Pace
  becomes `<`/`>` (shift `,`/`.`).
- `l` (loop mode) → **`u`**. Frees `l` for stills mode in Splay,
  and `m` for Splay's hot-pixel mask, and `p` for Splay's pixel
  probe.
- `[`/`]`/`+`/`-` (already): clip marks — keep.
- `h` (currently broken per TODO.md): fix HUD; render per the
  content rules above.
- `f` (already): fullscreen — keep. Add a button (TODO.md).
- `t`: add piano-roll toggle (new).

## Splay changes to bring into convention

- Add `Space` (play/pause), `,`/`.` (transport), `<`/`>` (pace),
  `u` (loop mode). These become live once frame-sequence playback
  lands.
- Add `↑`/`↓` (source switch). Live when multi-stream lands. No
  `1`–`9` source jump; Splay reuses `0`–`4` for zoom/brightness
  (already does for `0` `1` `2` `3` `4`).
- `t` already in Splay (thumbnail strip); semantics extend to
  piano roll when that lands.
- Existing `l` (list), `s` (select), `d` (deselect), `a` (sort),
  `w` (wipe), `p` (pixel probe), `m` (hot-pixel mask), `h`, `f`,
  `q`, `Esc` — keep as-is.

## Order of implementation

Suggested order, cheapest first:

1. **Web player HUD fix** + **`l`→`m` rebind** + **`,/.` rebind to
   transport, `p`/`P` for pace**. Pure web change, no Splay. Catches
   a documented bug + aligns the existing tool to the new convention.
2. **Splay frame-sequence playback** + **transport keys live**.
   Mid-effort. Validates the convention against the second runtime.
3. **Piano roll** (one row first, multi-row later). Visible win,
   modest code.
4. **Multi-stream + wipe** in Splay. Biggest, but the convention
   makes it tractable.
5. **Share-URL ↔ sidecar bridge** if it earns its keep. Defer.
