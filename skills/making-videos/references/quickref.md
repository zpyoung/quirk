# Quick reference for a repeat run

Read this instead of gather, brand, storyboard, motion, hyperframes, audio and review when **all** of these hold: the brand is confirmed, the video is one 16:9 cut, it is narrated with Kokoro, and it has no URL capture, app recording, 3D shot, music or cloud provider. If anything else comes up, open the full reference that covers it. This page holds the rules that broke real runs, not the reasoning behind them.

Contents: [Order of work](#order-of-work) · [Script and storyboard](#script-and-storyboard) · [Narration](#narration) · [Scene authoring](#scene-authoring) · [Motion and type](#motion-and-type) · [Beats](#beats) · [Render, verify, review](#render-verify-review)

## Order of work

1. `doctor.py check --need narration`, then `studio.py brand show --product <p>` to confirm the brand is confirmed.
2. Gather: read the code behind each claim and keep `$P/sources.md`, one line per claim with its file:line or URL. No source, no claim. For code videos, copy the files at the reviewed commit into `$P/assets/src/` once and quote from them, so line numbers match.
3. `studio.py project new --slug S --product P --brief-json FILE`, write `storyboard.md`, and stop for approval unless the user waived the stops.
4. Write `assets/lines.json`, then `voice.py say` → `align` → `captions --out "$P/v1/<slug>-16x9.srt"` (after `version new`).
5. Build the scenes by hand from the kit, or with the optional [code-walkthrough template](code-walkthrough.md) for a code video.
6. `studio.py version new`, render, `verify.py`, look at the frames, write `vN/review-notes.md`, run `review_page.py`, and stop.

## Script and storyboard

- Budget Kokoro `af_heart` at **2.8 words per second** (about 504 words for 180 s, 168 for 60 s), and subtract about 10% for pauses. Count words before you synthesize. The measured clip length is the truth: change the words, never the speed.
- The first frame carries the subject with no logo sting, works as a still, and has at least two visual beats in the first 5 s.
- One idea per scene, about 5-10 s for body scenes. On-screen text is labels and keywords, never the narration verbatim.
- `storyboard.md` order: header (title, product, length, aspects, narration, voice), Script as a **numbered list with one item per scene**, scene table, style frames, kit, flags. Each table row's Time cell **opens with the scene's start second** (`9.4-16.1`), because the review page and verify's stills read it.
- Hold times: a label holds at least max(1.2 s, characters / 13) after it stops moving, and the last line of the film at least 2 s.

## Narration

- `lines.json`: `[{"id", "text", "start_s"}]`, one sentence or two short ones per line. Spell out numbers and abbreviations ("thirty-seven one forty-six", "My S Q L").
- `say` levels each clip to -16 LUFS. Place clips at `data-volume="1"` with no fx chain, and never place `<id>.raw.wav`.
- Read `align`'s `mismatches` (heard words that differ from `lines.json`); open a `words.json` only for a listed clip. A wrong word that isn't a homophone (for example "Upsert" heard as "Absert") needs a phoneme patch: print espeak's phonemes with `~/.cache/quirk-video/venv/bin/python -c "from kokoro_onnx.tokenizer import Tokenizer; print(Tokenizer().phonemize('Upsert validates.', 'en-us'))"`, add `{"from", "to"}` to the brand's `pronunciations`, re-save it with `--confirm`, and run `say` and `align` again.
- `captions` fails with `cps_violations` when speech runs over 20 characters per second. Shorten or split the line, and never hand-edit the `.srt`.

## Scene authoring

- Every HyperFrames call goes through `hf.py`. `init "$P/scenes" --non-interactive`, then delete `scenes/CLAUDE.md` and `AGENTS.md`.
- Root `index.html` has one host per scene: `<div id="sN" class="clip" data-composition-id="sN" data-composition-src="compositions/sN.html" data-start data-duration data-track-index="1" style="z-index: 1">`. The host id, the scene root's `data-composition-id` and the `window.__timelines` key must all be the same, or every render waits 45 s per scene.
- A scene file puts style, markup and script inside `<template>`, styles its root as `#root`, prefixes every element id with the scene id, and registers its timeline last.
- Inline the brand `:root` block (colour tokens, `--font-*`, and `@font-face` for local brand files) in `index.html` **and** in every scene. Never link it as a stylesheet, and never use the `font:` shorthand with `var(--font-*)`; write `font-family`.
- Keep every text box inside x 96..1824 and y 54..1026, and give wide text a `max-width`. The audit tests element boxes, including content clipped by `overflow: hidden`, so hide rows that scroll out of a panel (`visibility: hidden`, flipped with `tl.set` at the scroll).
- Hard cuts between scenes are the default. An overlap needs a transparent incoming root.

## Motion and type

- Seek-safe GSAP: one paused timeline per scene; never `play()`, nested timelines, `from()`, `repeat: -1`, ScrollTrigger, `Date.now`, timers or unseeded `Math.random`. Set start states with `gsap.set` at build time. Give later `fromTo` tweens on the same property `immediateRender: false`. Place tweens at absolute seconds. Animate transforms and opacity only, and never tween `visibility` or `display` on a `.clip`. Colour tweens need literal hex values, not `var()`.
- Motion roles: enter 0.4 s `expo.out` with a 16-24 px rise, exit 0.25 s `power2.in`, on-screen move 0.35-0.6 s, stagger 0.05-0.08 s. Hold a landed title still.
- Frame 0 must not be empty. Start the first elements at opacity 0.3, not 0.
- Type: nothing under 28 px held over 0.5 s. Use at most three sizes, with contrast at least 4.5:1 (3:1 for 24 px and up). Start entrances from a colour that already passes contrast.

## Beats

- With narration on, `$P/beats.json` is required: `{id, word, clip, clip_start_s, expected_s, region: [x, y, w, h], baseline_s, detector: "changed", color: null}`. `expected_s` is the clip's `start_s` plus the word's `start`.
- Start each beat's tween **one frame (0.033 s) before** the word, with a fast-start ease (`expo.out`). Pick a region that changes only at the beat, and a `baseline_s` after any entrance in that region has settled; otherwise verify measures the early motion.
- Verify passes a beat within one frame. When it reports an offset, move that tween by the opposite amount and render again.

## Render, verify, review

```bash
python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- lint "$P/scenes"
python3 "$SKILL_DIR/scripts/studio.py" version new --project "$P"
python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- render --quality delivery --workers 2 \
  --output "$P/v1/<slug>-16x9.mp4" "$P/scenes" > "$P/v1/render.log" 2>&1
python3 "$SKILL_DIR/scripts/verify.py" --project "$P" --version v1
```

- Run a render of more than a minute in the background. A 164 s film rendered in about 80 s.
- Look at one snapshot per new scene before the render (`hf.py -- snapshot --at ...`), because lint misses CSS that doesn't parse. Snapshots are never review evidence.
- Verify counts failed attempts, and the third one stops the loop. Before spending one, run the four band checks yourself when layout changed (`hf.py -- check --json --caption-zone "<band>;severity=error;seek=.05,...,1"`) and read `layout.findings`.
- Common fixes:
  - `title_safe`: a text box sits in the outer 5%, often scrolled or clipped content.
  - `sync`: shift the tween by the reported offset.
  - `loudness`: multiply every clip's `data-volume` by the factor in the detail.
  - `fonts`: the tokens aren't inline, or the `font:` shorthand is used.
- Your own pass: open the contact sheet and the stills from the MP4. Check the brand faces (zoom into a heading), cut-off text, blank first and last frames, hold times, and claims against the storyboard.
- Write `vN/review-notes.md` (a verdict paragraph, then the things to check), run `review_page.py --project "$P"`, and give the user the `review.html` path, the verify result in one sentence, and what you saw. Notes become `v2`, and a version the user has seen is never rebuilt.
