# Tech spec: `explaining-features`

**Status**: Authored. Logic spec: [logic.md](logic.md).

All paths are relative to the repo root unless they start with `~`. Line numbers are as of `c5493a5`; trust the symbol over the number.

## Architecture

One new skill and four independent changes. No shared code passes between them; the new skill composes the others by naming them, and hands off through files.

| Unit | Files | Logic anchor |
|---|---|---|
| New skill | `skills/explaining-features/**`, `tests/test_explaining_features_*.py`, `README.md` | [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow) |
| Richer recordings | `skills/making-videos/scripts/record.py`, `references/gather.md` | SC-26 in [Behavior](logic.md#behavior-and-scenarios) |
| No-stops setting | `skills/making-videos/scripts/studio.py`, `SKILL.md`, `references/{storyboard,brand,review}.md` | SC-25 |
| Hover action | `skills/using-apps-like-a-user/scripts/{likeuser.py,_effects.py,_web.py}`, `SKILL.md` | SC-27 |
| Inline media | `skills/writing-html-artifacts/scripts/htmlkit/{assemble.py,kitcheck.py}`, `SKILL.md`, `references/templates.md` | SC-28 |
| Media check in verify | `skills/writing-html-artifacts/scripts/verify/verify.mjs`, the note in `htmlkit/assemble.py`, `references/design-reference.md` | SC-28's "captions on" can't be claimed for a video nothing decoded, so this extends it |

Technologies: Python 3 stdlib for skill scripts, Node and Playwright for recording and page verify, ffmpeg for media, `playwright-cli` 0.1.22 for the web driver.

## Folder layout

Resolves the logic spec's deferred layout question; recorded in its [amendments](logic.md#status--amendments).

`CONFIG:`
```
~/Studio/explainers/<date>-<slug>/
  evidence.md            the ledger
  <slug>.src.html        page source; media paths are relative to it
  media/                 screenshots, posters, and the MP4s and captions the page inlines, as rendered
  harness/               project-specific scripts, plus a README saying they aren't guaranteed to run
~/Studio/videos/<date>-<slug>/   the film project, owned by making-videos; absent when there's no film
~/Studio/videos/<date>-<slug>-code-tour/   the code-tour project, with tour.json; absent when there's no tour
<repo>/.quirk/html/<slug>.html   the built page
```

A clip-per-behavior run makes one `making-videos` project per clip, named `<date>-<slug>-<behavior>`. This avoids any change to `verify.py`, which keys scenes and beats on the MP4 suffix (`skills/making-videos/scripts/verify.py:82,177,725`) and can't pick another scenes folder.

## Code references and contracts

### Richer recordings (`record.py`)

Implements SC-26 in [Fixes to the existing skills](logic.md#fixes-to-the-existing-skills). Anchors: `ACTIONS` :53, `NODE_SCRIPT` :60, `runStep` :71, `validate_steps` :171, `render_script` :249, `_convert` :268, `_cmd_record` :297, `build_parser` :358. Known-good capture to port: `~/Studio/videos/2026-10-30-add-project-button/harness/record.ts` lines 8-20 and 23-50.

`CONTRACT:`
```
step actions added:
  hover  {selector|text, ms?}
  move   {x, y, ms?}
  press  {key, ms?}
  drag   {from: {selector|text|x,y}, to: {selector|text|x,y}, ms?}
new flag: --scale N   integer 1..3, default 1; anything else exits 2
result JSON: {webm, mp4, duration_s}; webm is null when scale > 1
```

- **Default capture is unchanged.** With `--scale 1` and no `hover`, `move` or `drag` steps, the generated script keeps `recordVideo` with `showActions`, and every existing test stays green unedited. Adding cases is fine; changing an existing assertion means this rule was broken.
- **`--scale` above 1 uses the screencast path:** launch with `--force-device-scale-factor=<scale>` and `--window-size=<w>,<h>`, `newContext({viewport: null})`, `Page.startScreencast` with max size equal to size × scale, ack every frame, and write frames plus an ffmpeg concat list with real durations under `assets/recordings/.frames-<stamp>/`. `_convert` takes that list. The folder is deleted after a successful conversion and kept on failure.
- **Frame size is asserted, not assumed.** After conversion, ffprobe must report width and height equal to size × scale (even-rounded); otherwise exit 1 and name both sizes. This is the check that was missing when `recordVideo` put a 1x page in the corner of a 2x canvas.
- **Drawn pointer:** injected with `addInitScript`, `pointer-events: none`, moved only by real `mousemove` events. It's on when scale is above 1 or any step is `hover`, `move` or `drag`, and `showActions` is off in those runs so there's never a second cursor.
- **In pointer mode, pointer steps glide** with real `mouse.move` calls, including the move before a `click`. Selector and text steps resolve to the element's bounding-box center.
- Step values stay JSON data embedded by `render_script`, never code. `validate_steps` rejects a `drag` missing an endpoint, a `move` missing `x` or `y`, and an empty `key` with exit 2 naming the step.

### No-stops setting (`making-videos`)

Implements SC-25 in [Fixes to the existing skills](logic.md#fixes-to-the-existing-skills). Anchors: `_build_brief` in `scripts/studio.py:83`; stop prose at `SKILL.md:8,38,43,46,51`, `references/storyboard.md:3-4`, `references/brand.md:3-4,72-73,97-99`, `references/review.md:3,22,143-146`.

`SCHEMA:`
```
brief.json: "stops": "both" | "none"    default "both"; any other value fails project new
```

- `SKILL.md` states that with `stops: none`, steps 4 and 7 write what they normally show and don't wait. `review_page.py` already runs with no approval, so no script gate changes.
- Always-on rules still hold under `none`: 3 failed `verify` attempts still stop looping, and versions are still never overwritten.
- **A brand stays unconfirmed under `none`.** `brand save --confirm` means a person approved it, and nobody did. The storyboard records this.
- Keep every string in `REQUIRED_STRINGS` (`tests/test_making_videos_skill.py:20-32`).

### Hover action (`using-apps-like-a-user`)

Implements SC-27 in [Fixes to the existing skills](logic.md#fixes-to-the-existing-skills). Anchors: `ACTION_KINDS` `likeuser.py:84`, `POINT_KINDS` :88, `_parse_act` :1303, `_gate_subjects` ~:1423, `_act_perform` ~:1581; `WebDriver._plan` `_web.py:~337`; `diff` and `classify` in `_effects.py`; `SCREEN_HASH_THRESHOLD` `_effects.py:23`.

- `hover` joins `ACTION_KINDS`, takes `--ref` or `--x --y` (coordinates still need `--target-name`), and plans to `["hover", ref]` or `["mousemove", x, y]`. `_parse_act` requires a target for it, the same way it does for `POINT_KINDS`.
- **Native returns `unsupported_action`** from the existing fallthrough in `_native.py`, surfacing as `ERROR`. `SKILL.md` says hover is for web and Electron renderers.
- **Hover isn't gated.** It can't commit anything. Today `_gate_subjects` returns the target's name for every kind but `press` and `hotkey`, so add an early return of `[]` for `hover`. This applies on third-party apps too.
- **The 8x8 hash can't see a hover** (`_effects.py:5-6` says so). For `hover` only, `screen` is decided by a new pixel comparison of the before and after screenshots.

`CONTRACT:`
```
_effects.pixels_changed(before: Path, after: Path) -> float
    fraction of pixels whose luma differs by more than FINE_LUMA_DELTA
    raises ValueError on undecodable input or mismatched dimensions
_effects.FINE_LUMA_DELTA = 16
_effects.FINE_SCREEN_THRESHOLD = 0.0001   fraction above which hover counts as a screen change
classify(...) gains fine_changed: Optional[bool] = None; when not None it replaces the hash result for "screen"
```

- At 1280x720 that threshold is 92 pixels, so a 26px square changing color counts and a 2x16px caret doesn't. Confirm both with a live test. If a before screenshot is missing or withheld, `screen` doesn't count, so a hover can come back `NO_EFFECT` but never a false `OBSERVED`.
- Other action kinds keep the hash path untouched.
- **The pointer has to stay put through the observe calls.** The survey couldn't confirm this, so a live test decides it. If `snapshot` or `screenshot` resets the pointer, stop and surface it: that's a feasibility problem for SC-27.

### Inline media (`writing-html-artifacts`)

Implements SC-28 in [Fixes to the existing skills](logic.md#fixes-to-the-existing-skills). Anchors: `build_tier1` `htmlkit/assemble.py:397`, the `render(sidecar)` closure ~:490 (called twice, so cache encoded bytes), `_load_data` :186 and its containment test :197-201 (factor out and reuse), `delivery_note` ~:712, `SIZE_FAIL` `htmlkit/checks.py:31`.

`CONTRACT:`
```
Markup: add data-inline to <img>, <video>, <source> or <track>; src and poster hold source-relative paths.
Allowed: .png .jpg .jpeg .webp .gif .mp4 .vtt .srt
Build output: each path becomes a data: URI, data-inline is removed, and .srt converts to WebVTT.
Captions on: the first inlined <track> in a <video> gets the default attribute if none has it.
Exit 2 naming the path: missing file, disallowed type, or a path outside the source folder and project dir.
```

- Inlining happens in `render()`, before `_substitute`, so `size` and `external-refs` see final bytes. It's independent of `_Data`, so **media never becomes a sidecar**: over 10 MiB fails `size`.
- Markup without `data-inline` behaves exactly as today.
- `delivery_note` adds "embedded media" as a reason for the over-2 MB warning.
- **`q-grid` figures:** a `figure` that's a direct child of `q-grid` with no `data-span` produces a build warning through `kitcheck.check_html_warnings` (`kitcheck.py:2488`) naming the fix. That function returns early unless the text has `q-flow`, `q-schema` or `q-sequence` (:2491), so the guard has to let `q-grid` through, and pages without those elements must otherwise warn exactly as before. No change to `vendor/kit/1.0.0/kit.css`: the kit is checksummed and pinned, and rebuilding old pages shouldn't reflow them.

### Media check in page verify

Extends SC-28 in [Fixes to the existing skills](logic.md#fixes-to-the-existing-skills). Anchor: `scripts/verify/verify.mjs`, the per-run page block ~:200-240. Today nothing checks that a video decodes, so a broken embed passes.

`SCHEMA:`
```
report.json checks.media: {passed: bool, details: [string]}   present only when the page has a <video> or <img>
```

- **The key is absent on a page with no media,** so `tests/test_html_verify.py:315,363`, which pin the exact check set for a media-free page, stay unedited.
- The check runs once, in the first of verify's runs, because the four runs load the same bytes and `VERIFY_TIMEOUT_S` is 180 s.
- For each `<video>`: wait for `loadedmetadata`, 15 s at most. An error event or a timeout fails the check. `videoWidth` must be above 0.
- For each `<img>`: `naturalWidth` above 0.
- **A browser that can't play H.264** (`canPlayType('video/mp4; codecs="avc1.42E01E"')` empty, as with bundled Chromium) doesn't fail and doesn't count as checked: `passed` stays true and `details` says the video wasn't checked.
- The note builder in `htmlkit/assemble.py` (~:668) prints `details` only for failed checks. It must also print `media` details when `passed` is true, or the unchecked case disappears from the delivery note.
- `references/design-reference.md:288` lists the verify checks, and gains `media`.

### The new skill

**Every scenario SC-1 to SC-24 in [Behavior and scenarios](logic.md#behavior-and-scenarios) and every entry in [Decisions Locked](logic.md#decisions-locked) is binding on `SKILL.md` and its references, as written there.** This section adds only what those don't settle. Read the logic spec in full before writing the body.

`CONFIG:`
```
skills/explaining-features/
  SKILL.md                       under 300 lines
  references/{evidence.md,capture.md,page.md}
  scripts/verify_outcome.py
  scripts/code_tour.py
  scripts/leftovers.py
  evals/trigger-evals.json       at least 12 true and 12 false
  test-pressure-{1,2,3,4}.md
```

- **Frontmatter:** `name` and `description` only. The description starts "Use when", is under 1024 characters, and covers "walkthrough", "explain this feature", "feature explainer" and "show what this PR does". It routes a video-only request to `making-videos`.
- **Sub-skills are named, not pathed.** `SKILL.md` marks `quirk:making-videos`, `quirk:writing-html-artifacts` and `quirk:using-apps-like-a-user` as required sub-skills and says when each is invoked. Its own scripts use `SKILL_DIR`, never `CLAUDE_PLUGIN_ROOT`.
- **`using-apps-like-a-user` runs `--unattended`,** as that skill requires when another skill calls it. A `blocked` verdict on the main behavior is the SC-12 stop.
- **Film handoff:** `stops: none` in the brief unless the user asked for review. `--scale 2`.

`SCHEMA:`
```
evidence.md, a Markdown table with these columns, one row per behavior:
  Behavior | Claim | Result | How checked | Proof
Result is one of: Pass, Partly, Unit test only, Not proven, Failed
```

`making-videos` keeps its own `sources.md`; each script line there cites a ledger row and doesn't restate the proof.

`CONTRACT:`
```
verify_outcome.py --verify FILE [--mp4 NAME]
  stdout: {"outcome": "ship"|"ship_disclosed"|"omit"|"halt"|"retry", "failed": [names], "detail": str}
  exit: 0 outcome produced; 2 unreadable input, a run missing, or several MP4s and no --mp4
  The first rule that matches decides:
    1. ship:           the run passed
    2. halt:           outside_calls failed in the run's current checks, even before the 3-attempt stop,
                       because the call has already happened. verify rereads the whole append-only
                       calls.jsonl on every attempt, so a later attempt can't clear an earlier failure.
    3. retry:          the run failed and its stop flag is false
    4. omit:           any failed check other than sync and loudness, an unknown check name included,
                       or no failed check named at all
    5. ship_disclosed: only sync or loudness failed
```

`CONTRACT:`
```
leftovers.py --explainer DIR
  stdout: {"yours": [{"pid", "command"}], "check_by_hand": [{"pid", "command"}]}
  yours: the process's HOME is DIR or under it; check_by_hand: only its working directory is
  never lists itself or its parent; never stops anything; an open file alone never lists a process
  exit: 0 the scan ran, whatever it found; 2 usage or DIR missing; 3 ps or lsof missing or failed
```

`references/capture.md` holds: the private-instance and seeded-data rules, theme and persisted-state resets between takes, the parent-commit build, the frame-sampling command (one frame every 3 s plus every screenshot), the search of page source, alt text and captions for the home directory and username, and label timing. Label timing uses the existing `making-videos` beat flow with no new tool, and any correction script gets run on a copy first, since a bad render costs a `verify` attempt. `references/page.md` holds: the section outline, reader variants, no "I", the staging caption with a worked example, reasoning that names its source, the dated-record line, and the budget arithmetic.

Pressure scenarios follow the layout in `skills/using-apps-like-a-user/test-pressure-1.md`:

- `test-pressure-1.md`: the film's text is hard to read after 3 `verify` attempts, and it looks fine otherwise (SC-17).
- `test-pressure-2.md`: a not-proven behavior would make a better film, and the summary reads better without the gap (SC-19, SC-20).
- `test-pressure-3.md`: the user said to just finish, and one frame shows a real path (SC-18), plus a broken main behavior late in a run (SC-3).
- `test-pressure-4.md`: verification is blocked on the main behavior while the code reading looks conclusive (SC-12), plus a design reason with no source (SC-22).

### Page size opt-out (`writing-html-artifacts`)

`CONTRACT:` a tier-1 source header may carry `"size_limit": "none"`. It's the only accepted value, and any other value is a `SourceError` (exit 2). The build records it in the built file's `quirk-html-artifact` header, and `run_checks` in `htmlkit/checks.py` reads it from there, so `quirk_html.py check FILE` and a rebuild agree. With it set, a page over `SIZE_FAIL` gets no `size` failure and still gets the `SIZE_WARN` warning. Without it, behavior is unchanged byte for byte. The data-sidecar rule at `assemble.py:651` doesn't change, and inlined media still never becomes a sidecar. `build-app` (tier 2) doesn't take it.

### Code tour (`explaining-features`)

`scripts/code_tour.py` is stdlib-only and runs on Python 3.9, because `pygments` and the video venv aren't promised. Its tokenizer colours comments, strings and keywords and can never change the text. It prints one JSON object on stdout, with diagnostics on stderr, and never prompts.

`SCHEMA:` `$P/tour.json`, written by the agent:
```
{"repo": "<absolute repo path>", "commit": "<sha or ref>", "title": "<first-frame title>",
 "scenes": [
   {"map": [{"name": "Worktrees plugin", "file": "WorktreesSection.tsx"}, ...],     // 2 to 4 nodes
    "lines": [{"text": "<narration>", "source": "<file:line, commit or spec>", "lit": [1, 2]}],   // lit: node indexes, optional
    "label": "<optional bottom label>"},
   {"stop": "PLUGIN", "path": "plugins/x/WorktreesSection.tsx",
    "rows": [528, 529, {"skip": "folder-plus icon", "from": 530, "to": 533}, 534, 535],
    "lines": [{"text": "<narration>", "source": "<...>", "highlight": [529]}],
    "label": "<optional bottom label>"}
 ]}
```

`CONTRACT:`
```
code_tour.py lines --project P
  writes P/assets/lines.json, one clip per narration line, ids l01, l02, ... in order, with start_s 0
  validates tour.json first; never touches git
  stdout: {"lines": N}
code_tour.py build --project P
  needs P/scenes/index.html (hf.py init) and P/assets/voice/<id>.wav for every line
  reads code with `git show <commit>:<path>` and resolves the commit with `git rev-parse --verify --end-of-options`
  times scenes from measured wav lengths: 0.3 s lead, 0.35 s between lines, 0.8 s between scenes,
  2.5 s hold at the end, every clip start and scene boundary on a 1/30 s frame
  rewrites lines.json with real start_s, writes scenes/compositions/*.html, scenes/index.html body,
  copies wavs to scenes/assets/voice/, writes P/beats.json, P/sources.md, P/storyboard.md, P/kit/kit.md,
  then runs the same comparison as check before it exits
  stdout: {"scenes": N, "beats": N, "film_s": X, "stops": [{"stop", "rows"}]}
code_tour.py check --project P
  compares every code line on screen in scenes/compositions/*.html with `git show <commit>:<path>`
  stdout: {"commit", "checked": N, "mismatches": [{"scene", "line", "screen", "source"}]}
exit: 0 ok; 1 a tour that can't ship, naming what and where (below); 2 usage, bad tour.json, or a missing
      input, with the command that makes it; 3 git missing
exit 1 cases:
  a commit that doesn't resolve, or a path or line that doesn't exist at it
  a mismatch, or a checked count of 0, because a check that saw nothing proves nothing
  characters removed by dedent that aren't whitespace
  a stop over MAX_ROWS rows after wrapping: 14, or 13 with a label
  a film of 90 s or more
  a narration line with no source, or a highlight naming a line the stop doesn't show
```

Details that the prototype paid for, at `~/Studio/videos/2026-10-31-add-project-code-tour/harness/build_scenes.py`:

- **Layout:** 1920x1080, code at 36 px on 52 px rows, 72 cells per row, where a wide East Asian character is 2 cells, longer lines wrapped at the last space and counted as extra rows, with a hard break only for an unbroken run over 72 cells. A title is at most 54 cells and a label 72, so a title never takes a fourth line and a label never a third. Tabs are expanded to 4 spaces, in `build` and `check` alike. Dedent is the common leading whitespace of the rows the stop shows. Every text box stays inside x 96..1824 and y 54..1026.
- **Comments on screen:** hyperframes lint reads a literal `/*` in markup as a stray CSS comment, so comment delimiters are written with `&#47;`, which the check's HTML parser reads back as `/`.
- **Highlight:** a band with an accent bar on each highlighted row and the other rows dimmed to 0.72, as a 0.2 s `power2.out` tween that starts on its line's clip start, because a real render measured the first word about 40 ms after that and a tween one frame earlier landed over the 1-frame limit. Each `beats.json` entry's region is the accent bar, `[98, y, 8, height]`, because the band alone stays under the detector's 24-level change threshold. Its `word` is the line's first word, `baseline_s` is the later of 0.5 s before the beat and 0.05 s after the scene starts, and `detector` is `changed`.
- **Tokens:** ground #101114, surface #16171b, selected #2c3050, border #24262c, text #eceef2, muted #9aa0ab, accent #9aa6ff, string #c6cbe8, inlined in every composition. Fonts come from the display and mono roles of the product's `brand.json`, falling back to Inter and JetBrains Mono per role, because `verify.py` requires the brand's families. A family HyperFrames doesn't bundle has its files copied to `scenes/assets/fonts/` and an inline `@font-face`. `build` exits 1 on a family it can't load or a brand family outside those two roles, and 2 on a name unsafe for CSS or a file outside the brand folder. Longhand `font-family` only.
- **Seek-safe GSAP:** `fromTo` with `immediateRender: false` on stacked tweens, `gsap.set` for start states, positions relative to the scene, and hosts, roots and timeline keys all named by scene id. `index.html` keeps the scaffold's head, which loads GSAP.
- **`storyboard.md`:** a header, a numbered Script with one item per scene, and a Scenes table whose Time cell opens with the start second, so `verify.py` and `review_page.py` find the scenes.

`references/code-tour.md` holds when to propose a tour, what counts as a source file, how to pick stops and lines, the sourcing rule, the run's commands in order, and the caption. The tour project is `<date>-<slug>-code-tour`, with the same product as the film, `stops: none`, `narration: true` and `cloud_allow: []`.

## DO-NOT-CHANGE fences

- **`skills/making-videos/scripts/verify.py`:** the 3-attempt rule and the sync threshold are the skill's honesty. A crash in an agent's own script isn't a reason to relax them.
- **`skills/writing-html-artifacts/vendor/kit/1.0.0/**` and `vendor/libraries.json`:** checksummed and pinned; old pages rebuild against them.
- **The `SCREEN_HASH_THRESHOLD` path in `_effects.py` for existing actions:** tuning it changes what every existing `OBSERVED` means.
- **The `SIZE_FAIL` and `SIZE_WARN` constants:** every page that doesn't opt out keeps both limits, so a page opts out through its source header (SC-37) and the constants never move. `SIZE_WARN` applies to every page, opted out or not.

## Always / Ask / Never

- **Always:** keep default behavior of each existing skill byte-for-byte for callers not using the new option. Print one JSON object on stdout from new scripts, with diagnostics on stderr. Never prompt interactively from a script.
- **Ask:** anything that contradicts [Decisions Locked](logic.md#decisions-locked).
- **Never:** build a sibling skill's path in `SKILL.md` prose; write outside `~/Studio` and the repo's self-ignoring `.quirk/` during a run; stop a process by name or pattern, because that can hit the user's own instance of the same app; send anything to a cloud service a brief didn't name.

## Cross-cutting

- **Security:** media paths reuse `_load_data`'s containment, so a source can't inline a file from outside its folder or project. Recording steps stay data. Footage is seeded-only and frames get checked, per [Decisions Locked](logic.md#decisions-locked).
- **Rollback:** each change is additive and opt-in. Removing `skills/explaining-features` and the README line undoes the new skill.

## Testing strategy

- `tests/test_making_videos_record.py`: new actions, validation failures, script text per mode, and the frame-size assertion. Existing tests unedited.
- `tests/test_making_videos_studio.py`, `tests/test_making_videos_skill.py`: `stops` default, value and rejection; doc strings.
- `tests/test_using_apps_like_a_user_{cli,web,effects,fixtures}.py`: hover plan per surface, native refusal, no gate on a "Delete" target, `pixels_changed` with crafted PNGs. **A live hover test in `TestLive` with a new `web_hover` scenario must show `OBSERVED` on a real CSS-only hover and `NO_EFFECT` on a dead control:** per the project's review experience, a negative that can't fail proves nothing.
- `tests/test_html_builder.py`, `tests/test_htmlkit_core.py`: inlining each type, `.srt` conversion, containment and missing-file exits, over-10 MiB failure with no sidecar, the `q-grid` warning. `tests/test_html_verify.py`: a valid video passes, a corrupt one fails when H.264 is available, and the unchecked path reports itself.
- `tests/test_explaining_features_skill.py`, modeled on `tests/test_making_videos_skill.py`: frontmatter, body under 300 lines, links resolve, references linked, balanced evals, required honesty strings. `tests/test_explaining_features_scripts.py`: every `verify_outcome.py` outcome and an unknown check; `leftovers.py`. `tests/test_explaining_features_code_tour.py`: each `code_tour.py` exit 1 case against a temporary git repo, timing on frames, and the check failing on a changed line.

`COMMAND:`
```
python3 -m pytest tests/test_making_videos_*.py tests/test_using_apps_like_a_user_*.py tests/test_html_*.py tests/test_htmlkit_*.py tests/test_explaining_features_*.py tests/test_adhd_skill.py -q
```

`tests/test_adhd_skill.py:155` checks the README skill count, which goes to 31.

Acceptance is in [Done when](logic.md#done-when). No trigger-eval runner exists in the repo, so the eval run is a separate step after the review loop, with its method stated in the result. The loaded plugin resolves from the installed path, not this worktree (TEST-2 in `TEST_BACKLOG.md`), so the blind remake's agent reads the skills from this worktree's paths and its prompt says so.

## Non-goals

Anything in the logic spec's [Scope and non-goals](logic.md#scope-and-non-goals), plus: a `q-video` kit element (it would touch the catalog, checksums and generated docs for what an attribute does); native hover; a script that checks a ledger or page for honesty, which stays with pressure scenarios and review.
