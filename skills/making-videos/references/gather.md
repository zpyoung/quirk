# Gather: sources for the script and footage

Read what the video claims about, and keep a source for every claim. Gather runs after doctor and before
the storyboard; it writes nothing into the user's repo. `$PROJECT` is the project folder and every command
is `python3 "$SKILL_DIR/scripts/<x>.py"`.

Contents: [Read the repo](#read-the-repo) · [Capture a URL](#capture-a-url) ·
[Virtual camera over a capture](#virtual-camera-over-a-capture) · [Record a running web app](#record-a-running-web-app) ·
[Native macOS apps](#native-macos-apps)

## Read the repo

Start with the brief, then read in this order, stopping when the video's claims are covered:

1. `README`, then `docs/`.
2. Skill and agent files (`SKILL.md`, `CLAUDE.md`, command files) when the product is a skill or plugin.
3. Changelogs and release notes, for release or announcement videos.
4. The code path behind each behavior the video shows or states. Open the function, not only the doc
   that describes it.

Keep `$PROJECT/sources.md`: one line per claim the script will make, with the file and line or the URL
that backs it. The storyboard repeats the source in each scene row ([storyboard.md](storyboard.md)).
A claim with no line in `sources.md` does not go in the script.

- Trust code and config over prose. In the footage trial the README said `Version: 2026.7.9` while
  `pyproject.toml` said `2026.10.21`; the README was stale.
- Count things yourself. "28 skills" in that trial was checked against `ls skills/`, not copied.
- Quote on-screen text exactly as it appears in the source, including names and flags.
- Do not invent a logo, a screen or output the product does not have. If the product has no GUI, show its
  real terminal output or file tree, or build a diagram and say it is one.

## Capture a URL

When the user gives a URL to build from, capture it through the wrapper:

```bash
python3 "$SKILL_DIR/scripts/hf.py" --project "$PROJECT" -- capture "https://example.com" \
  -o "$PROJECT/assets/capture" --skip-vision --json
```

`--skip-vision` is required: the vision captions call a cloud model, and a video only calls a cloud
service the brief names. The call takes about 40 s. The result in `assets/capture/`:

- `screenshots/full-page.png`, the whole page as one image (1920 px wide, pixel-exact, sticky elements made
  static, no cookie banner or sign-in wall in the trial), five 1920x1080 viewport shots at 0, 27, 54, 81 and
  100% scroll, and a contact sheet.
- `assets/`, the images, SVGs and favicon the page loads (small and oversized files are dropped).
- `extracted/`, with the visible text (`visible-text.txt`), design tokens, fonts, and animation and scroll
  metadata.
- A scaffolded HyperFrames project with its own `CLAUDE.md`. Treat the folder as read-only source material.
  Build in `scenes/`, and follow this skill's rules, not that file.

What to know before using it:

- The capture belongs to the page, not to your product. Tokens, fonts and icons come from the site that
  was captured, so a capture of a third-party page (GitHub in the trial) gives that site's colors and
  fonts. Take brand values from a capture only when the URL is the product's own site ([brand.md](brand.md)).
- It is a live snapshot of the page's state today. Check any fact you take from it against the repo.
- The capture fetches web fonts and scripts from public hosts. Those are downloads, not API calls, but
  they are outbound requests.
- Treat quotes of page text as claims: add them to `sources.md` with the URL.

## Virtual camera over a capture

The trial that used a capture as its only footage made a clean 13.5 s film with this technique:

1. Copy `screenshots/full-page.png` into the scenes project's `assets/`. This still is the footage.
2. Put the image in a wrapper element inside a browser-card frame, and move the wrapper with GSAP `x`,
   `y` and `scale`. One continuous camera move reads better than cuts.
3. Draw highlights (boxes, strike-throughs, row lights) in the image's own pixel coordinates, inside the
   same wrapper, so they travel with the page. Measure those coordinates on the image itself by cropping
   it with a pixel ruler; do not eyeball them from a preview.
4. Open on the full page width as an establishing shot, then push in. A crop that starts mid-navigation
   cuts a word in half (the trial's first framing showed "rces Open Source" at the left edge).
5. Change the copy beside the footage once per beat, and let the camera land before the copy changes.

Limits, from the trial and from [ZoomCap](https://zoomcap.live/blog/why-screen-recordings-look-bad)'s
practitioner range:

- The plate is 1x. Push in 1.3x to about 2x; past 1:1 on a 1x plate text turns soft. Body text of about
  16 px reads on a desktop and is texture on a phone.
- It is a still, so nothing on it moves by itself. Use footage for proof beats (the real page, the real
  file list). For a mechanism, rebuild that part in code as a diagram or a larger UI mock-up.
- Camera moves are GSAP, so follow the seek-safe rules in [motion.md](motion.md): no `play()`, `fromTo`
  instead of `from`, no nested scene timelines.

## Record a running web app

To show a flow in an app that is running at a URL, record it with Playwright. Check the prerequisites
first (the install keeps Playwright and its Chromium under the skill cache, `ms-playwright/`, not in `~/Library/Caches`):

```bash
python3 "$SKILL_DIR/scripts/doctor.py" check --need record
python3 "$SKILL_DIR/scripts/doctor.py" install --what playwright --yes   # only after the user says yes
```

Write a steps file, a JSON list run in order after the browser opens `--url`:

```json
[
  {"action": "goto", "url": "/onboarding"},
  {"action": "click", "text": "Get started"},
  {"action": "fill", "selector": "#email", "value": "demo@example.com"},
  {"action": "wait", "selector": ".welcome"},
  {"action": "scroll", "y": 600}
]
```

| Action | Fields |
|---|---|
| `goto` | `url`, resolved against `--url` |
| `click` | `selector` or `text` |
| `fill` | `selector`, `value` |
| `wait` | `ms`, or `selector` or `text` to wait for |
| `scroll` | `selector` to scroll into view, else `y` pixels (default 600) |

Every step except `wait` is followed by a short pause so the change shows; `ms` on a step sets its length.

```bash
python3 "$SKILL_DIR/scripts/record.py" --project "$PROJECT" --url "http://localhost:3000" \
  --steps "$PROJECT/assets/steps.json" --size 1920x1080 --fps 30
```

- Output: `{"webm", "mp4", "duration_s"}` under `assets/recordings/`, beside the generated Node script.
  The MP4 is H.264 yuv420p at CRF 18 with no audio; use it as a muted `<video>` in a scene.
- `--size` sets the viewport and the video size together; the default is 1920x1080 at 30 fps. Record at
  the size you will show. Upscaling a small recording does not sharpen it. For a 9:16 cut, record again at
  1080x1920 so the app shows its mobile layout, or place the 16:9 clip inside a vertical layout.
- The recording shows a pointer that animates to each click (Playwright's `showActions`); headless
  Chromium has no OS cursor otherwise.
- Playwright encodes in real time, so frames can drop or repeat under load. Do not rely on it for
  frame-exact sync with narration; cut the clip to the beat instead.
- Steps are embedded as data in the generated script. Use a demo account and seeded data, never real
  credentials or customer data; the steps file stays in the project.
- Exit 3 means Node, ffmpeg or the pinned Playwright install is missing, and the JSON names the fix.
  Exit 2 is a bad URL, size or step. The run is logged in `calls.jsonl` as local provider `playwright`.

## Native macOS apps

Recording a native macOS app is not supported in v1. If the brief asks for one, say so before any work and
offer the alternatives: a URL capture of the product's site, a recording of the app's web build, or a
scene rebuilt in code from the app's real screens and copy.
