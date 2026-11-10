---
id: 2026-11-05-fireworks
title: Fireworks!
category: fireworks
confidence: confirmed
date: 2026-11-05
time: "19:40–20:30 GMT"
camera: eclipticam
night: 2026-11-05
summary: >-
  Bonfire Night from the wide ecliptic camera: fifty-one one-minute exposures
  played at twenty frames a second, as a local display fills the sky with light
  and smoke. Two nights later the HQ camera caught the edges of Saturday's
  displays.
# Media are build artefacts on muppet (paths relative to the host that publishes):
image: ~/tmp/fireworks/poster-fireworks-v3w-2026-11-05-crop.jpg
video: ~/tmp/fireworks/fireworks-v3w-2026-11-05-20fps-crop.mp4
figures:
  - image: ~/tmp/fireworks/hq16-1107-crops/crop_175307.jpg
    caption: "Saturday 7 November, 17:53: a burst lights the haze across the bottom of the frame for one minute."
  - image: ~/tmp/fireworks/hq16-1107-crops/crop_192457.jpg
    caption: "19:24: a single-minute burst just above the bottom-left edge."
  - image: ~/tmp/fireworks/hq16-1107-crops/crop_193756.jpg
    caption: "19:37"
  - image: ~/tmp/fireworks/hq16-1107-crops/crop_194255.jpg
    caption: "19:42"
  - image: ~/tmp/fireworks/hq16-1107-crops/crop_200053.jpg
    caption: "20:00"
  - image: ~/tmp/fireworks/hq16-1107-crops/crop_200753.jpg
    caption: "20:07"
source:
  # v3w clip: one 60 s sub per frame, no stacking, one fixed asinh stretch;
  # privacy: top 1064 binned rows (privacy.json), and the left 512 and right
  # 160 binned px cut because the window glass reflects the lit room there.
  render: scratch/fireworks/render.py v3w 2026-11-05 19:40 20:30 OUTDIR 512 160
  encode: ffmpeg -framerate 20 -pattern_type glob -i 'v3w_*.jpg' -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart
  poster: the 19:52 frame
  hq16_crops: before | burst | after strips, 640x360 panels, approx 1 deg bar (astro-science, 2026-11-08)
---

# Caption

Bonfire Night, Thursday 5 November, seen by the wide ecliptic camera between
19:40 and 20:30 GMT. Every frame of the video is a single one-minute exposure,
with nothing stacked, so each second of video is twenty minutes of sky. The
display ran from about 19:50 to 20:21. At its height, 19:52 to 19:53, the frames
saturate and lit smoke fills the view. The whole clip shares one fixed colour
stretch, so the bursts brighten against a steady sky rather than being evened
out frame by frame. The clock and a 10 degree scale bar (true at the centre of
the field) are burned in.

Two nights later, on Saturday 7 November, the HQ camera (a 16 mm lens with a
field about 22 by 17 degrees, aimed at the ecliptic) caught only the edges of
the weekend's displays. Each strip below shows the minute before, the burst,
and the minute after. The HQ camera did not see Thursday's display at all: it
was outside its field.

# Reasoning

A burst of light at the horizon could be many things, but these are pinned by
the date and the clock: Bonfire Night, in the hours when local displays run.
The smoke gives it away in the wide view, lit from below and lingering in the
frames after each burst. In the HQ camera every burst lasts exactly one
exposure and sits at the bottom edge of the frame, low over the rooftops, where
a firework would be.

# Evidence

- 5 November, 19:50–20:21 GMT: the hours of a Bonfire Night display
- frames saturate at 19:52–19:53 and lit smoke persists into the following subs
- HQ16 bursts: single-sub, at the bottom border (low altitude), 7 November evening
