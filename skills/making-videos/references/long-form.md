# Long-form: videos over about 60 seconds

For a video over about 60 s (up to the 3 min cap), lock the scene kit first, let subagents build scenes in
parallel from the kit only, then assemble, render once, and verify the assembled MP4. Under about 60 s,
build the scenes yourself in sequence; the overhead of parallel work does not pay off.

Contents:
- Why the kit is locked first
- Before dispatching
- What each subagent receives
- What a subagent must not do
- Assembly, render and verify
- Render notes for long videos

## Why the kit is locked first

Published multi-agent video work found style drift when the shared style lived in prompts: in one Remotion
project the same role came out at fonts from 14 to 19 px until the visual language moved into a shared code
kit ([Roboto Studio](https://robotostudio.com/blog/how-to-use-remotion-agent-skills-with-claude-code)).
Per-scene workers also lose shared context ([Bleu](https://docs.buildbleu.com/blog/using-llms-to-generate-educational-videos-with-manim/)),
so each one gets everything it needs in its brief rather than discovering it.

## Before dispatching

Check these in order; stop and fix before any subagent starts.

1. The storyboard is approved and the scene kit in `<project>/kit/` is locked ([storyboard.md](storyboard.md)). A kit
   change after this point invalidates every scene, so make it yourself and re-brief.
2. Narration, if on, is already built: the voice track exists and Whisper has measured each word's start
   ([audio.md](audio.md)). Scenes are timed to those measurements.
3. The project skeleton exists in `<project>/scenes/`: `index.html` with the root composition, one host
   `<div>` per scene (`data-composition-id`, `data-composition-src="compositions/<id>.html"`, `data-start`,
   `data-duration`) and the audio element. You own this file.
4. Scene ids are final and short (`s1`, `s2`, ...). Subagents prefix every element id with the scene id so
   ids stay unique across the assembled page.
5. `python3 "$SKILL_DIR/scripts/hf.py" --project "<project>" -- lint` passes on the skeleton.

## What each subagent receives

Dispatch all scene subagents in one message so they run in parallel. Write each brief to be complete on its own:
the subagent has no conversation history.

- Its storyboard block: scene id, start and duration, on-screen text, narration lines, sources, motion roles.
- Absolute paths to the kit: tokens (the `:root` block to paste inline), motion roles, components.
- Its narration onsets in scene-local seconds: each word start minus the scene's start, because a scene's
  timeline starts at 0 when its host starts.
- Absolute paths to the references it needs: [motion.md](motion.md) and [hyperframes.md](hyperframes.md), plus
  [3d.md](3d.md) only for a 3D scene.
- The output path: exactly one file, `<project>/scenes/compositions/<scene-id>.html`.
- Any footage or assets that scene uses, by path under `<project>/assets/`.
- The hand-back: reply with the file path and a list of every kit token, role and component used.

## What a subagent must not do

State these in every brief.

- Do not invent a colour, font, size, easing or duration. Use kit tokens and named motion roles; if the
  scene needs something the kit lacks, say so in the hand-back and use the nearest kit value.
- Do not edit another scene, `index.html`, the kit, the audio or the storyboard.
- Do not render, run verify, or call any cloud service. Run only `hf.py -- lint` on the scene's project; the
  orchestrator runs the browser checks once, because one Chrome-heavy tool at a time is safer on a dev Mac.
- Do not use the seek-unsafe patterns in [motion.md](motion.md): `play()`, nested `add()` of timelines, `from`,
  `repeat: -1`, ScrollTrigger.
- Do not link a stylesheet for fonts. Inline the kit's `:root` tokens inside the scene's `<template>`.

Each scene file keeps its timeline self-contained: one paused GSAP timeline, tweens placed at absolute
seconds on that scene's own clock (never `+=` or `<` positions), registered on `window.__timelines` under
the scene's composition id, and no reference to elements outside the file.

## Assembly, render and verify

The orchestrating agent assembles and renders; subagents never do.

1. Read each hand-back and diff its used tokens against the kit. Send a fix request to the same subagent for
   any value outside the kit.
2. Run `python3 "$SKILL_DIR/scripts/hf.py" --project "<project>" -- lint`, then `check --json` from
   `scenes/`. `check` has a hard 120 s whole-audit deadline since 0.8.153, so on long films slice it with `--range a,b`
   instead of one run.
3. Look at seams: snapshot a few frames on each side of every scene boundary
   (`snapshot --at ...`) and fix jumps in position, scale or colour. Carry any shared element as described in [motion.md](motion.md).
4. Render once for the full video, in one pass, with the options below.
5. Verify the assembled MP4, never single scenes or snapshots. Fonts, voice sync, loudness and title-safe
   are properties of the whole file; a per-scene pass hides seam errors. See [review.md](review.md).
6. A failed check goes back to the scene that owns the failing time range (use the scene list to find it),
   then re-assemble and re-render. The 3-attempt cap in [review.md](review.md) counts whole-video attempts.

## Render notes for long videos

All commands go through `hf.py`; environment variables pass through to the render. Numbers are from the
HyperFrames CLI docs for version 0.8.186; confirm flags with `python3 "$SKILL_DIR/scripts/hf.py" -- render --help`
because the pinned version is 0.8.185.

- Run one long render at a time. The maintainers' own long-form gates run sequentially.
- Workers: each worker is a separate Chrome of about 256 MB. Set `--workers N` explicitly rather than `auto`
  for long WebGL or Three.js scenes; `auto` put WebGL compositions of 900 frames or more (30 s at 30 fps) on one
  worker in a reported case. Run `benchmark` before assuming more workers is faster: in one test on a trivial
  10 s scene, 4 workers beat 1 worker, and that does not generalise.
- Segmented capture for long renders (mp4 and mov): set `HF_SEGMENTED_CAPTURE=true`; `HF_SEGMENT_FRAMES`
  defaults to 3000 frames (min 30). Each segment is encoded separately and joined, and `--resume` reuses
  finished segments after a failure. It restarts the browser at segment boundaries, which avoids Chrome losing its
  target after tens of thousands of frames. Known issue: a segmented render can fail on a flat frame that a
  one-pass render recaptures; if so, fall back to a one-pass render.
- Disk: multi-worker renders on macOS write raw frames to disk, about width x height x 4 bytes per frame
  (roughly 15 GB per minute at 1080p30). Check free space first; doctor's frames cache fails under 2 GB free.
  Run `clean --dry-run` and then `clean` after a killed render.
- Memory: keep source footage near delivery size; large source videos grew renderer memory on long renders.
- Run a long render in the background and read its log, rather than blocking a foreground call. A render
  that finishes prints `Render complete`; one that fails prints `Render failed`.
- After rendering, confirm the file is non-empty and that `ffprobe` duration equals the root `data-duration`
  before verify. The capture mode line in the render summary (macOS) tells you whether it fell back to screenshot capture;
  see [hyperframes.md](hyperframes.md).
