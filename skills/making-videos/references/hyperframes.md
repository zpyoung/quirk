# HyperFrames: authoring rules and wrapper recipes

Run every HyperFrames command through `hf.py`, build scenes by the rules below, and read the render log before you trust an MP4.

Contents:
- [Wrapper rules](#wrapper-rules)
- [Project setup](#project-setup)
- [Authoring rules](#authoring-rules)
- [Fonts](#fonts)
- [Recipes](#recipes)
- [Lint and check warnings seen in the trials](#lint-and-check-warnings-seen-in-the-trials)
- [Audio in the composition](#audio-in-the-composition)
- [macOS capture mode](#macos-capture-mode)

Commands below assume `P` is the video project folder (`~/Studio/videos/<date>-<slug>`), `V` is the version folder (`$P/v1`), and `SKILL_DIR` is the directory holding SKILL.md.

## Wrapper rules

`hf.py` is the only way to run HyperFrames, because it fixes what went wrong in the trials. Never call `npx hyperframes`, `pnpm dlx hyperframes` or a global `hyperframes` yourself.

- It runs the pinned version (0.8.185) with `pnpm dlx`, so a render made today matches one made next month.
- It sets `HYPERFRAMES_NO_TELEMETRY=1`, `DO_NOT_TRACK=1` and `HYPERFRAMES_SKIP_SKILLS=1`, so `init` installs nothing global and no usage data leaves the machine.
- It removes every cloud key (Gemini, Google, provider keys) from the child's environment. A key in your shell is never permission to use it.
- It appends `--describe false` to every `snapshot` and refuses `--describe true` (exit 2): describing sends frames to Gemini.
- Output and exit code are the child's, unchanged. Pass `--project "$P"` so each call is logged to `calls.jsonl` for the review page.
- Exit 3 means `pnpm` is missing; run `doctor.py check` for the fix.

Do not run `hyperframes usage`, `feedback`, `skills update` or `cloud`/`lambda`/`cloudrun` commands. They call accounts or write outside the project.

## Project setup

Create the HyperFrames project at `$P/scenes/`. Pass the absolute path, because `hf.py` does not change directory.

```bash
python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- init "$P/scenes" --non-interactive
```

- Add `--resolution portrait` or `--resolution square` for 9:16 and 1:1; the default is 1920x1080. Each aspect is its own project folder and its own layout pass. Name the folders `scenes/` (16:9), `scenes-9x16/` and `scenes-1x1/`, for example `init "$P/scenes-9x16" --resolution portrait`. Verify scans every `scenes*/` folder for fonts, and a `*-9x16.mp4` or `*-1x1.mp4` also needs its matching folder to pass. Everything below uses `scenes/`; for another aspect, swap in that folder and name the MP4 and check files to match.
- The scaffold writes `index.html`, `hyperframes.json`, `meta.json`, `package.json`, `CLAUDE.md` and `AGENTS.md`. Delete `scenes/CLAUDE.md` and `scenes/AGENTS.md` right after `init`: they tell you to install skills globally, run `npm run dev` and start preview servers, which this skill forbids.
- `index.html` is the root. Scene files go in `compositions/*.html`; media and fonts go in `assets/`. Asset paths are root-relative (`assets/...`) even inside a scene.
- The scaffold loads GSAP from jsdelivr, a network fetch at render time. Leave it in place unless the machine is offline.

Replace the scaffold's root with one host `<div>` per scene. This is the whole pattern, shown for two scenes (add the `:root` token block from [Fonts](#fonts) to the head):

```html
<!-- scenes/index.html -->
<div id="root" data-composition-id="main" data-start="0" data-duration="7.6" data-width="1920" data-height="1080">
  <div id="s1" class="clip" data-composition-id="s1" data-composition-src="compositions/s1.html"
    data-start="0" data-duration="3.8" data-track-index="1" data-width="1920" data-height="1080" style="z-index: 1"></div>
  <div id="s2" class="clip" data-composition-id="s2" data-composition-src="compositions/s2.html"
    data-start="3.8" data-duration="3.8" data-track-index="1" data-width="1920" data-height="1080" style="z-index: 1"></div>
</div>
<script>
  window.__timelines = window.__timelines || {};
  const tl = gsap.timeline({ paused: true });
  window.__timelines["main"] = tl;
</script>
```

```html
<!-- scenes/compositions/s1.html -->
<template>
  <style>/* :root tokens, then #root and #s1-* rules */</style>
  <div id="root" data-composition-id="s1" data-width="1920" data-height="1080">
    <div id="s1-title">...</div>
  </div>
  <script>
    const tl = gsap.timeline({ paused: true });
    tl.fromTo("#s1-title", { opacity: 0 }, { opacity: 1, duration: 0.4, ease: "expo.out" }, 0.2);
    window.__timelines["s1"] = tl;
  </script>
</template>
```

- `class="clip"` makes the host a timed element: it shows over `[data-start, data-start + data-duration)` and is absent outside it. Without it the scene is on screen the whole film.
- `data-composition-src` mounts the scene file. The host id, its `data-composition-id`, the scene file's root `data-composition-id` and the `window.__timelines` key are all the scene id.
- `data-track-index` is a Studio lane number only; paint order is CSS `z-index`. Set `z-index` on hosts that overlap in time so the incoming scene paints above the outgoing one.
- The root's `data-duration` is the film length and must cover the last scene's end.

## Authoring rules

A render seeks a paused timeline one frame at a time, so anything that depends on a clock or the network breaks it. [Determinism](https://hyperframes.heygen.com/concepts/determinism).

- Banned: `Date.now()`, `requestAnimationFrame`, `setTimeout`/`setInterval`, unseeded `Math.random()` (use a seeded PRNG such as mulberry32), fetches during render, `repeat: -1` (use a finite count). Lint catches `Math.random()` but not the timers or `repeat: -1`, so check by eye.
- Every timed element has `class="clip"`, `data-start` and `data-duration` in seconds. It shows over `[start, start + duration)`, so a state that lands exactly on the end is never rendered.
- The root's `data-duration` is the video length. Overrun is cut; an early end holds the last frame.
- Each composition builds one paused GSAP timeline and registers it last: `window.__timelines["<data-composition-id>"] = tl`. The key must equal the composition id. If you build inside an async callback, register at the end of it, or the render is blank.
- Host div id, scene root id and timeline key are identical. A mismatch makes every render wait 45 s per scene and then show static frames.
- A scene file puts its styles, markup and script inside `<template>`; anything outside it is dropped. Style the scene root as `#root`. Prefix element ids (`#intro-title`) because ids must be unique across the assembled page.
- A still composition with no timeline gets `data-no-timeline`, or every render waits 45 s.
- Place tweens at absolute seconds: `tl.fromTo(el, {...}, {...}, 2.4)`.
- Keep every text box inside the outer 5% margin: x 96..1824 and y 54..1026 at 1080p, scaled for other sizes. The `check` caption-zone bands test element boxes, not glyphs, so a centred text box spanning the full width fails the left and right bands even when the letters sit well inside. Give wide text a `max-width`.
- Animate transforms and opacity, not `left/top/width/height`. Never tween `display`, `visibility` or `autoAlpha` on a `.clip`; animate a child.
- Media: never `play()`, `pause()` or set `currentTime`. A `<video>` needs `muted` or `data-has-audio="true"`. Animate a wrapper `<div>` to move a video, and time the video or its wrapper, never both. No `crossorigin`.
- A start state belongs in the `fromTo`, not in CSS. Text built by script requests its font late; call `document.fonts.load('700 64px "Face"', text)` before measuring it.

The GSAP rules for seek-based rendering (no `play()`, no nested scene timelines, `fromTo` not `from`, no ScrollTrigger, `immediateRender: false` on stacked tweens, `gsap.set` instead of `tl.set(..., 0)`) are in [motion.md](motion.md).

## Fonts

Inline the brand's `:root` tokens in every composition and never link a stylesheet for them. Fonts declared only in a linked stylesheet render as system fonts in the MP4 while `check`, snapshots and preview all look right (trials t1 and t7). The renderer injects `@font-face` only for families it sees inline.

```html
<style>
  :root {
    --ground: #f2efe8;
    --ink: #16171a;
    --accent: #1e7a52;
    --font-display: "Outfit", sans-serif;
    --font-mono: "IBM Plex Mono", monospace;
  }
</style>
```

- Put the block in `index.html` and repeat it inside the `<template>` of each scene file. Use the tokens as `var(--font-display)`.
- Bundled families need no `@font-face`: Inter, Montserrat, Outfit, Nunito, Oswald, League Gothic, Archivo Black, Space Mono, IBM Plex Mono, JetBrains Mono, EB Garamond, Playfair Display, Source Code Pro, Noto Sans JP, Roboto, Open Sans, Lato, Poppins.
- Any other family needs an inline `@font-face` in the file that uses it (`src: url('assets/fonts/x.woff2')`, or `src: local('Exact Name')` for an installed font), or lint fails `font_family_without_font_face`.
- Keep font files in `assets/fonts/`. Blender is stricter about formats than Chrome; see [3d.md](3d.md).
- Proof is in the render log. Search it for `Injected deterministic @font-face rules for N requested font families`. `verify.py` fails when the line is missing or N is below the number of families in `brand.json`.
- The compiler fetches bundled families from Google Fonts into `~/.cache/hyperframes/fonts/` on first use. That is an outbound request for a public download, not an API call.

## Recipes

Run in this order: lint, check, snapshot while building, then render, then verify (see [review.md](review.md)). Create `$V` with `studio.py version new` first.

1. Lint. Fix every error before anything else; `check` skips its browser audit when lint has errors, and an empty section is not a clean one.

   ```bash
   python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- lint "$P/scenes"
   ```

2. Check, four runs for verify. `verify.py` needs one `check --json` run per edge band, each labelled by band (`top`, `bottom`, `left`, `right`), to prove no text sits in the outer 5% of the frame. Every run also carries the contrast audit, so these four files cover contrast too. Do not pass `--no-contrast`.

   ```bash
   for spec in "top|x0=0;y0=0;x1=1;y1=.05" "bottom|x0=0;y0=.95;x1=1;y1=1" \
               "left|x0=0;y0=0;x1=.05;y1=1" "right|x0=.95;y0=0;x1=1;y1=1"; do
     band="${spec%%|*}"; zone="${spec#*|}"
     python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- check --json \
       --caption-zone "${zone};severity=error;seek=.05,.15,.25,.35,.45,.55,.65,.75,.85,.95,1" "$P/scenes" > "$V/check-${band}.json"
   done
   ```

   The geometry is fractions of the canvas: each band is 5% deep along one edge. `severity=error` makes a collision a finding verify counts. The flag defaults to `seek=1`, which samples only the last moment of the film (text that sits in a band from 2 to 3 s of a 6 s film passes), so keep the `seek=` list: it samples eleven instants across the film as fractions of its duration.
   Read the result, not the exit code. `check --json` exits 1 on any error, and the evidence is in `layout.findings` and `contrast.findings` in the JSON; a clean run has both arrays empty (and the file is much smaller). Findings seen in the trials:

   - `caption_zone_collision`: see the table below. A text box counts, not its glyphs.
   - `text_occluded` and `content_overlap`: one layer covers another, usually an opaque incoming scene over content that has not left yet. Fade or remove the outgoing layer before the opaque one arrives, or overlap with a transparent incoming root ([motion.md](motion.md#scene-transitions)).
   - `film_silent`: a warning that suggests adding a music bed. It is expected when the brief asked for silence; ignore it.

   `check` also writes snapshot artifacts under `scenes/.hyperframes/`, inside the project; leave them there.

   Move flagged text out of the band. Do not add `data-layout-allow-caption-zone` to silence verify; that attribute is for deliberate lower-thirds.
   The audit has a hard 120 s limit, so on a long film `check_runtime_failure` can be the limit and not a bug in your scenes.

3. Snapshot, only to look at your own work while building. The wrapper forces `--describe false`. Snapshots are never review evidence; review frames come from the MP4. Look at one snapshot of every new scene before moving on: lint passes CSS that fails to parse (a stray `{{` left by a template gives tiny, unstyled text), and a snapshot is the only thing that catches it. Files land in `scenes/.hyperframes/artifacts/snapshots/<run-id>/`.

   ```bash
   python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- snapshot --at 0,1.5,4 "$P/scenes"
   ```

4. Render into the version folder and save the log. Verify reads `$V/render.log` for the font line, so redirect both streams.

   ```bash
   python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- render --quality delivery --workers 2 \
     --output "$V/<slug>-16x9.mp4" "$P/scenes" > "$V/render.log" 2>&1
   ```

   - Quality: `draft` while iterating, `delivery` for the version you verify. `looks` is the default (CRF 16).
   - Workers: use `--workers 2`; each worker is a separate Chrome (about 256 MB). The trials ran 10 s films in 9 to 17 s.
   - Name MP4s `<slug>-16x9.mp4`, `-9x16.mp4`, `-1x1.mp4`. `verify.py` takes the only MP4 in the version folder, so keep one per verify run or pass `--mp4`.
   - Afterwards confirm the file is non-empty and `ffprobe` duration equals the root `data-duration`.

5. Capture a URL as a source, never as the final scenes. Run it from the assets folder so the output lands there; it needs direct internet and ignores proxies.

   ```bash
   (cd "$P/assets" && python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- capture https://example.com -o capture --skip-vision --json)
   ```

   `--skip-vision` is required: it skips the AI image captioning. Read the `dropped` object in the JSON, and retry into a new `-o` if `BLOCKED.md` appears.

6. Audio analysis, one file per call.

   ```bash
   python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- audio "$P/assets/voice/a.wav" --only loudness,onsets,silence,envelope --hop-ms 10 --json
   ```

The preview server (`preview --background`) is for looking, not for review. Stop it with `preview --stop` when done.

## Lint and check warnings seen in the trials

| Code | Meaning and fix |
|---|---|
| `gsap_timeline_set_initial_hide` | An initial hidden state set with `tl.set(..., 0)` does not render at frame 0. Use `gsap.set(...)` instead. |
| `first_frame_empty` | Frame 0 paints only the background; it becomes the social thumbnail. Put the first element on screen at 0 s, or start a fade at 0.3 opacity instead of 0. |
| `text_below_floor` | Text under 2.6% of the short side (28 px at 1080) held 0.5 s or more. Raise the size; chrome like a fake URL bar can take `data-layout-ignore`. |
| `contrast_aa_failure` | Text fails WCAG AA at a sampled instant. A word still mid-entrance can trip it: start entrances from a colour that already passes (`--muted`, not `--rule`). A finding at one sample during an entrance that settles within about 0.15 s is informational, but verify still counts it, so fix it. |
| `line_unread` | A reading-size line is on screen under its floor (0.4 s for 1 to 2 words, then about 0.3 s per extra word). Hold it longer; the final line needs 2 s. |
| `caption_zone_collision` | An element box inside a `--caption-zone` band. Move it out of the outer 5%, or narrow a full-width text box with `max-width`. |
| `text_occluded` | Text hidden behind another layer at a sampled instant. Fade or remove the outgoing layer before the opaque incoming one covers it. |
| `content_overlap` | Two layers' content overlaps. Same cause and fix as `text_occluded`. |
| `film_silent` | The film has no audio. Expected when the brief asked for silence; ignore it. |
| `non_deterministic_code` | `Math.random()` in a composition. Use a seeded PRNG. |
| `font_family_without_font_face` | A non-bundled family without an inline `@font-face`. |
| `missing_data_no_timeline` | A still composition without `data-no-timeline`. |

Per-letter spans count as separate words in the checker; set a name as one line.

## Audio in the composition

Narration clips are `<audio>` elements with an `id` (one without an `id` is left out of the mix), placed with `data-start` and trimmed with `data-duration`.

- Equalise clips with `data-volume` (1 = 0 dB, up to 3.98). Measure each clip's loudness with the audio recipe above, then set the gain that brings it to the target in [audio.md](audio.md). The trial needed 1.84 to 2.09.
- End the clip's `data-fx-chain` with a limiter. The attribute is JSON with its quotes written as `&quot;`:

  ```html
  <audio id="vo-a" src="assets/voice/a.wav" class="clip" data-start="0.4" data-duration="3.2" data-volume="1.9"
    data-fx-chain="{&quot;version&quot;:1,&quot;nodes&quot;:[{&quot;type&quot;:&quot;limiter&quot;,&quot;id&quot;:&quot;n1&quot;,&quot;params&quot;:{&quot;limit&quot;:-1.5}}]}"></audio>
  ```

- The renderer may still log `Audio lowered by 1.1 dB to stay under -1 dBTP`. That is harmless.
- Do not also tween `volume` with GSAP on a clip that has `data-volume`; lint flags it.
- Time visuals to the measured word onsets from `voice.py align`, and put each beat on the frame before its word, because a tween shows nothing on its start frame.

## macOS capture mode

Renders on macOS use `drawelement` or `screenshot` capture, not the deterministic BeginFrame mode, and the log says so with only a warning. Read the render summary's second line (for example `drawelement capture · hardware gpu`). The multi-worker render above uses screenshot capture. This is expected on this machine; it is why frames for review must come from the finished MP4 and why you watch the render before declaring it done. `--docker` pins Chrome and fonts if exact pixels ever matter, but it is not part of this skill's flow.

Frames for review come from the MP4, never from snapshots or preview. `verify.py` decodes them.
