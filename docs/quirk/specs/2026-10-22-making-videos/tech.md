# Tech spec: `making-videos`

**Status**: Reviewed · tier gate fired: touches >3 source files across skill docs, scripts, and tests
**Logic spec**: [logic.md](logic.md)

Paths are relative to the repo root. "The skill dir" means `skills/making-videos/`.

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

```
skills/making-videos/
  SKILL.md                     pipeline router + always-on rules (< 300 lines)
  references/gather.md         sources: repo reading, URL capture, web-app recording
  references/brand.md          studio layout, brand extraction, brand.json
  references/storyboard.md     script craft, scene list, style frames, scene kit, stop 1
  references/motion.md         motion principles (general + software), seek-safe GSAP rules
  references/hyperframes.md    authoring rules, wrapper recipes, traps
  references/audio.md          narration, alignment, loudness, music, captions
  references/3d.md             Blender headless authoring, guard rules
  references/review.md         verify checks, review page, stop 2, notes loop, 3-attempt cap
  references/cloud.md          opt-in providers, licensing/attribution
  references/long-form.md      > ~60 s pieces, scene subagents from the locked kit
  evals/trigger-evals.json     trigger eval set
  scripts/_mv_common.py           shared: paths, pins, JSON emit, subprocess helpers   (stdlib)
  scripts/studio.py            studio/brand/project/version bookkeeping              (stdlib)
  scripts/hf.py                the HyperFrames wrapper                               (stdlib)
  scripts/doctor.py            tool check + consented installs                       (stdlib)
  scripts/voice.py             launcher for TTS/alignment in the cache venv          (stdlib)
  scripts/voice_worker.py      Kokoro + faster-whisper; runs only inside the venv    (venv deps)
  scripts/blender_render.py    headless Blender runner + guard                       (stdlib)
  scripts/bl_guard.py          runs inside Blender as a second --python script      (bpy)
  scripts/cloud.py             the only path to a cloud API; allowlist + call log    (stdlib)
  scripts/record.py            Playwright web-app recording → MP4                    (stdlib)
  scripts/verify.py            strict verify, writes verify.json                     (stdlib)
  scripts/media_worker.py      pixel/onset analysis for voice sync; runs in venv     (venv deps)
  scripts/review_page.py       writes review.src.html, builds review.html via writing-html-artifacts (stdlib)
tests/
  test_making_videos_skill.py      structure, links, evals, budgets, script paths, trap strings
  test_making_videos_studio.py     _common + studio
  test_making_videos_hf.py         wrapper env/args with a fake pnpm
  test_making_videos_doctor.py     probes with fake executables
  test_making_videos_voice.py      launcher contract; worker logic only if deps importable
  test_making_videos_blender.py    argv order, exit codes, guard parsing with a fake blender
  test_making_videos_cloud.py      allowlist, call log, no network (local HTTP stub)
  test_making_videos_record.py     generated script + argv with a fake node/pnpm
  test_making_videos_verify.py     each check's pass/fail on fixtures; ffmpeg-dependent tests skip if absent
  test_making_videos_review.py     page content from a fixture project
README.md                          skill count 28 → 29 and a "What ships" bullet
```

Technologies: Python 3.9-compatible, stdlib-only scripts for everything the plugin's CI imports
(`pyproject.toml:3`; `.github/workflows/test.yml:15` runs 3.9 and 3.12 and installs only pytest,
pygments and pyyaml). Heavy Python
(`kokoro-onnx`, `faster-whisper`, `numpy`, `soundfile`) lives only in the cache venv and is reached by
running `voice_worker.py` / `media_worker.py` with the venv's interpreter. External CLIs: `pnpm dlx
hyperframes@<pin>`, `ffmpeg`/`ffprobe`, `blender` (optional), `node` + Playwright installed into the
cache (optional), `uv` when present for venv creation.

## Code references

Back-link: [Decisions Locked](logic.md#decisions-locked).

| Path | Action | Anchor |
|---|---|---|
| `README.md:9` | `**28 skills**` → `**29 skills**`; add a "What ships" bullet for making-videos | enforced by `tests/test_adhd_skill.py:157-164`, `tests/test_simplifying_safely_skill.py:86-95`, `tests/test_using_apps_like_a_user_skill.py:139-152` |
| `skills/writing-html-artifacts/scripts/quirk_html.py:1,4-8,12,20-21,29-34,333` | pattern to copy: shebang, one-JSON-object stdout rule, exit codes, `from __future__`, sys.path bootstrap, `_Parser.error` | read only |
| `skills/writing-html-artifacts/SKILL.md:10` | pattern to copy: `SKILL_DIR` + `python3 "$SKILL_DIR/scripts/<script>.py"` | read only |
| `tests/test_writing_html_artifacts_skill.py:12-18,47-58,67-73,83-84,93-101` | patterns: constants, frontmatter keys, description rules, link resolution, no `CLAUDE_PLUGIN_ROOT`, trigger-eval schema | read only |
| `tests/test_stacking_prs_skill.py:321-329` | trigger evals: `skill_name` match, ≥12 per polarity | read only |
| `tests/conftest.py:37-44` | `run_script` subprocess helper | read only |
| `tests/test_html_app.py:77-107` | fake executable on PATH (`fake_env`) + `run_cli` | read only |
| `tests/stacking_prs_stubs.py:16-72` | argv-logging stub template | read only |
| `skills/stacking-prs/evals/trigger-evals.json:1-7` | eval file schema | read only |
| `~/orca/workspaces/quirk/vst-t2-voiceover/video-trial/tools/say.py:16-27` | Kokoro call, `PATCHES` phoneme map, `is_phonemes=True` | port into `voice_worker.py` |
| `~/orca/workspaces/quirk/vst-t2-voiceover/video-trial/tools/align.py:12-18` | decode with `ffmpeg -f s16le -ac 1 -ar 16000` (faster-whisper's PyAV decode fails) | port into `voice_worker.py` |
| `~/orca/workspaces/quirk/vst-t2-voiceover/video-trial/tools/sync_report.py:24-93` | beat detectors (`changed`, `green`), onset selection rules | port into `media_worker.py`; `BEATS` becomes `beats.json` |
| `~/orca/workspaces/quirk/vst-t*/**/NOTES.md` | trap evidence for references | read only |
| scratchpad `research/craft.md`, `research/toolchain.md` | cited best-practice findings for references | read only (paths given per task) |

## Contracts & interfaces

Back-links: [Data flow](logic.md#data-flow), [Key decisions and rationale](logic.md#key-decisions-and-rationale).

### Shared script conventions (every stdlib script)

- `#!/usr/bin/env python3`, `from __future__ import annotations`, Python 3.9 syntax only.
- Each command prints **exactly one JSON object** to stdout; diagnostics go to stderr.
- Exit codes: `0` ok, `1` check/operation failed (JSON explains), `2` usage error, `3` a required
  tool or venv is missing (JSON names it and the install command).
- Paths honor overrides so tests never touch `~`:

`CONFIG:`
```
QUIRK_STUDIO        default ~/Studio
QUIRK_VIDEO_CACHE   default ~/.cache/quirk-video
```

### `_mv_common.py`

`CONTRACT:`
```
HYPERFRAMES_VERSION: str = "0.8.185"
PLAYWRIGHT_VERSION: str            # pinned at implementation time from `pnpm view playwright version`
studio_root() -> Path; cache_root() -> Path; venv_python() -> Path   # <cache>/venv/bin/python
project_dir(name: str) -> Path      # <studio>/videos/<name>; name is the dated folder name
emit(obj: dict, code: int = 0) -> NoReturn   # one JSON object to stdout, then exit
run(argv: list[str], env: dict | None = None, timeout: float | None = None) -> CompletedProcess
log_call(project: Path, record: dict) -> None   # appends one line to <project>/calls.jsonl
PROVIDER_KEY_ENV: dict[str, str]   # provider -> env var; see cloud.py
SCRUB_ENV: tuple[str, ...]         # GEMINI_API_KEY, GOOGLE_API_KEY + every PROVIDER_KEY_ENV value
```
Errors: `run` raises `subprocess.TimeoutExpired` on timeout (callers convert it to a JSON error,
exit 1) and `FileNotFoundError` when argv[0] is missing (callers exit 3). `log_call` raises
`FileNotFoundError` when the project directory doesn't exist; it never creates one.

### `studio.py`

`CONTRACT:`
```
studio.py init                                   -> {"studio": str, "created": [str]}
studio.py project new --slug S --product P [--brief-json FILE]
                                                 -> {"project": str, "brief": str}   # folder <YYYY-MM-DD>-<S>, date added here
studio.py version new --project DIR              -> {"version": "v<n>", "path": str}   # never reuses a number
studio.py brand show --product P                 -> {"brand": {...} | null, "path": str}
studio.py brand save --product P --file BRAND.json [--confirm]
                                                 -> {"path": str, "confirmed": bool}
```
Invariants: a version folder is created empty and never deleted, renamed or replaced; scripts only
add files inside it, and only `verify.py` updates a file there (`verify.json`). `brand save` without
`--confirm` stores `"confirmed": false`; only `--confirm` flips it.

Errors (exit 1 with a JSON `error`): `project new` when the dated folder exists, when `--slug` isn't
`[a-z0-9-]+`, or when the brief's `length_s` is over 180 (the 3-minute cap; the message names the
cap); `version new` when the project doesn't exist; `brand save` when the file isn't valid JSON or
misses a required brand key (`product`, `colors`, `fonts`, `voice`). `--brief-json` fills defaults:
`narration` = `length_s > 20`, `aspects` = `["16:9"]`, `cloud_allow` = `[]`, `music.source` = `"none"`.

### `hf.py`: the wrapper

`CONTRACT:`
```
hf.py [--project DIR] -- <hyperframes args...>
  runs: pnpm dlx hyperframes@<HYPERFRAMES_VERSION> <args...>
  env:  HYPERFRAMES_NO_TELEMETRY=1, DO_NOT_TRACK=1, HYPERFRAMES_SKIP_SKILLS=1;
        removes every SCRUB_ENV variable unconditionally (HyperFrames never needs a cloud key;
        cloud.py is the only path to a provider)
  args: for `snapshot`, injects `--describe false` when absent and refuses `--describe true`
  out:  passes the child's stdout/stderr through unchanged; exit code = child's
```
`hf.py` is the one documented exception to the one-JSON-object rule, because agents need the raw
HyperFrames output (`check --json`, `render` logs). It never rewrites `~/.hyperframes/config.json`.
When `pnpm` isn't on PATH it prints one JSON error naming the doctor command and exits 3. With
`--project`, it appends a `calls.jsonl` record (`provider: "hyperframes"`, the subcommand) so the
review page lists what ran.

### `doctor.py`

`CONTRACT:`
```
doctor.py check [--need narration,3d,record]    -> {"ok": bool, "tools": [{"name", "ok", "version", "fix"}]}
doctor.py install --what tts|playwright --yes    -> {"installed": [...], "path": str}
```
`install` refuses without `--yes` (exit 2). The SKILL.md flow asks the user before passing `--yes`.
Blender, Node, ffmpeg and Chrome are never installed; their `fix` is the command to run. On non-macOS,
`check` returns `ok: false` with an "unsupported platform" tool entry.

### `voice.py` / `voice_worker.py`

`CONTRACT:`
```
voice.py say   --project DIR --lines LINES.json --voice V   -> {"clips": [{"id", "wav", "duration_s"}]}
voice.py align --project DIR --model small.en                -> {"words": [{"clip", "path"}]}   # <wav>.words.json
```
`voice.py` checks `venv_python()` exists (else exit 3 with the doctor command), then runs
`voice_worker.py` with it. Lines file: `[{"id", "text", "start_s"}]` (`start_s` is where the clip sits on the video timeline).

`CONTRACT:`
```
voice.py captions --project DIR --lines LINES.json --out FILE.srt [--burn IN.mp4 --burned OUT.mp4]
  -> {"srt": str, "burned": str | null}
```
`captions` is stdlib-only (no venv): it builds cues from each clip's `<wav>.words.json` offset by
`start_s`, at most 2 lines of 42 characters and 20 characters per second. `--burn` runs ffmpeg's
`subtitles` filter. The skill burns captions into 9:16 and 1:1 renders and writes a sidecar `.srt`
for 16:9. Pronunciation patches come from the brand
(`pronunciations`), applied at the phoneme level as `say.py:17` does. Models live under
`cache_root()`; `HF_HOME` points there.

### `blender_render.py` / `bl_guard.py`

`CONTRACT:`
```
blender_render.py --blend FILE --script PY --out DIR --frames A-B [--chunk N] [--alpha] [--fps N]
  argv built as:
    blender -b FILE --python-exit-code 1 --python PY --python <skill>/scripts/bl_guard.py -- --out DIR --frames A-B [--alpha]
  -> {"frames": int, "out": str, "clip": str, "guard": <guard.json>, "warnings": [str]}
bl_guard.py (runs inside Blender, after PY)  -> DIR/f_####.png and DIR/guard.json
  guard.json: {"default_scene": bool, "view_transform": str, "text_objects": [str],
               "mirrored_frames": [int], "edge_on_frames": [int], "frames_rendered": int}
```
The author's script only builds the scene; it does not import the guard. `bl_guard.py` then inspects the
scene, sets the output path in Python (the runner never passes `-o` or `-a`, whose order silently
redirects output), and renders the range. It skips the render when a check below fails.
The Blender binary is `$QUIRK_BLENDER`, else `blender` on PATH, else
`/Applications/Blender.app/Contents/MacOS/Blender`; none found exits 3 with the blender.org install
pointer. A missing ffmpeg also exits 3.

Fails (exit 1) when: `--blend` is missing (never falls back to the default scene); Blender exits
non-zero (the JSON carries the stderr tail); `guard.json` or a rendered frame is missing; the scene is
Blender's startup scene (`default_scene`: one mesh named `Cube` with the default `Camera` and `Light`,
or nothing besides cameras and lights); any render-visible text object faces away from the camera on a
rendered frame (`mirrored_frames` non-empty: the dot of the object's world +Z normal with the unit
vector from object to camera is negative). Text within `|dot| < 0.2` of edge-on
(`edge_on_frames`) and a `view_transform` other than `Standard` are `warnings`, not failures. The
classification maths takes plain data, so tests run it without `bpy`.
`--chunk N` renders frame ranges of N frames in separate Blender processes and merges their guard
results. Without `--alpha`, the PNG sequence is encoded to `clip.mp4` (`libx264`, `yuv420p`, `-crf 14`,
`+faststart`); with `--alpha` the frames are rendered RGBA with a transparent film, the PNG sequence is
kept, and `clip.mov` is ProRes 4444 (`yuva444p10le`). The frame rate is `--fps`, else
`$QUIRK_VIDEO_FPS`, else 30. The author script must tolerate the extra arguments after `--`
(use `parse_known_args`); `references/3d.md` documents this.

### `cloud.py`

`CONTRACT:`
```
cloud.py call --project DIR --provider P --method GET|POST --url URL [--json BODY] [--out FILE]
  -> {"status": int, "out": str | null, "bytes": int}
```
Providers accepted: `elevenlabs`, `openai`, `pexels`, `pixabay`, `freesound`. Refuses (exit 1) unless
`P` is in the brief's `cloud_allow`. The credential comes from the provider's env var and is sent in
that provider's documented header; it is never logged. Every call appends to `calls.jsonl`
(`ts, provider, method, host, path, status, bytes`). Generated-media providers are added to the
accepted list when the reference names them (see Ask).

### `record.py`

`CONTRACT:`
```
record.py --project DIR --url URL --steps STEPS.json [--size 1920x1080] -> {"webm": str, "mp4": str, "duration_s": float}
```
Runs a generated Node script with the cache's Playwright install. Steps: `[{"action": "goto|click|fill|wait|scroll", ...}]`.
Converts to MP4 with ffmpeg. Exit 3 when Playwright isn't installed.

### `verify.py`

`CONTRACT:`
```
verify.py --project DIR --version vN [--mp4 FILE] [--beats BEATS.json] [--check-json [BAND=]CHECK.json] [--render-log LOG]
  -> {"version", "mp4": str, "attempt": int, "passed": bool, "stop": bool, "checks": [CHECK...], "frames": {"sheet": str, "stills": [str]}}
  writes <project>/<vN>/verify.json (one run per MP4); exit 1 when this run has a failing check
```
Check sources (logic amendment 2026-10-22):

| Check | Source | Pass rule |
|---|---|---|
| `fonts` | static scan of the HTML in every `scenes*/` folder (`scenes/` for 16:9, `scenes-9x16/`, `scenes-1x1/` for the other layout passes): every `var(--font-*)` resolves in an inline `<style>`/`style=`, no stylesheet `<link>` defines `--font-*`; render log line `Injected deterministic @font-face rules for N requested font families` lists every brand family; a `*-9x16.mp4` / `*-1x1.mp4` also needs its matching folder to exist | all hold |
| `contrast` | `check --json` → `contrast.findings` | no `contrast_aa_failure`; `measured` = failing-finding count plus the worst ratio parsed from finding messages when present |
| `title_safe` | `check --json` run with `--caption-zone` error bands covering the outer 5% on each edge (the flag takes one band, so four `check` runs). Each band carries `;seek=.05,.15,.25,.35,.45,.55,.65,.75,.85,.95,1`, because the flag samples only `seek=1` (the last instant) by default | no text finding in any band |
| `loudness` | `ffmpeg -af ebur128=peak=true` on the MP4 | narrated: −17 ≤ I ≤ −15 LUFS and true peak ≤ −1.0 dBTP; silent: skipped |
| `sync` | `media_worker.py` over beats.json + `hyperframes audio --json` run once per clip (it takes one file per call) | every beat's first changed frame within ±1 frame of its word onset. Silent video: `skip` without beats or without the venv (detail says why). Narrated video: `fail` without beats ("narrated videos need beats.json (see audio.md)") and `fail` without the venv (detail names the doctor fix) |
| `blender` | each `guard.json` under the project | no default scene, no mirrored frames; skipped without 3D |
| `outside_calls` | `calls.jsonl` vs brief `cloud_allow` | every logged provider is allowed |

`CHECK` schema below. `verify.json` is per MP4:
`{"version", "passed", "runs": {"<mp4 filename>": {"attempts": [{"n", "ts", "passed"}], "attempt", "passed", "stop", "checks": [CHECK...], "frames": {...}}}}`.
A run reads and appends to its own `attempts` list, so a 16:9 and a 9:16 MP4 in one version count separately;
`attempt` is that list's length, and top-level `passed` is true only when every run passed. At
`attempt >= 3` with a failure, that run sets `"stop": true` and the skill goes to the review page instead
of rebuilding. A flat `verify.json` without `runs` is read as the run for the single MP4 present.
Errors: missing project or version → exit 2; missing MP4 → exit 1 with a `missing_render` error;
missing ffmpeg → exit 3. Frames: a contact sheet and stills decoded from the MP4 at the `--at` times the agent passes (settled instants per
scene; six evenly spaced stills when `--at` is omitted) into
`<vN>/frames/<mp4 stem>/`, for the agent's own visual review.

### `review_page.py`

Back-links: [Data flow](logic.md#data-flow) step 7, SC-11, amendment 2026-10-23.

`CONTRACT:`
```
review_page.py --project DIR
  -> 0 {"page": str, "source": str, "checks": {"passed": bool, "failures": [...], "warnings": [...]}}
  -> 1 {"error": str, ["page", "source", "checks"]}   # html skill missing, build failed, or static checks failed
  -> 2 {"error": str}                                  # usage error or missing project
```

- Writes `<project>/review.src.html` (kept, rebuildable by hand) and builds `<project>/review.html`
  by running the sibling skill's builder:
  `sys.executable <skills>/writing-html-artifacts/scripts/quirk_html.py build <project>/review.src.html --out <project>/review.html --project-dir <project>`,
  where `<skills>` is `Path(__file__).resolve().parents[2]`. `--project-dir <project>` keeps template
  lookup off whatever repo the agent's cwd is in. The builder's JSON `checks` is passed through.
  Missing builder file, builder exit 2, or non-JSON output → exit 1 naming the cause; builder exit 1
  (a static check failed) → exit 1 with `page`, `source`, `checks`. No fallback renderer.
- Source header: `{"template": "report", "title": "<brief title or 'Video review'>, <vN> review",
  "layout": "explainer", "mode": "offline", "interactions": [...]}`. The header is one line of JSON
  inside an HTML comment, so `<`, `>` and `&` in the title are written as `<`, `>`,
  `&` (a `-->` in a title must not close the comment).
- Every value read from project files is HTML-escaped before it enters the source. Media and file
  links are relative to the project (percent-encoded), so the page works from `file://` only while it
  sits in the project folder. No network references.
- The newest version (`vN` with the highest N) leads. Region order:
  1. `summary`: the note's verdict paragraph (see `review-notes.md` below), else a plain verify
     verdict. A newest version whose verify run set `stop: true` opens with "Stopped after 3 failed
     verify attempts" and names the failing checks, before any note text.
  2. `main`, in order: a `q-meta` line (product, length, aspects, narration, created date, project
     path); Findings (generated from `verify.json`: loudness, worst sync beat and any expected-time
     beats, outside calls, attempt history per MP4); Watch (one `<video>` per MP4 in a `q-grid`,
     16:9 `data-span="3"`, 9:16 and 1:1 `data-span="1"`, plus `.srt` links); Scenes (below); What I
     would check before signing off (the note's remaining content, else "The agent's frame review
     for vN isn't written yet."); Verify results (one row per check, one column per MP4, measured
     value and bar in plain words, raw JSON never shown; a `q-chart` of beat offsets when a sync
     check has beats); Frames (verify's stills from `frames/<mp4 stem>/`, one `q-tabs` section per
     MP4, each still captioned with its time and scene; the contact sheet is not shown); Outside
     calls; Earlier versions (only when there are two or more versions); Files; How this page was
     built.
- Missing pieces: a version without an MP4, `verify.json`, a verify run for one of its MP4s, or
  stills gets one visible line naming each missing item. A project with no versions, no brief or no
  storyboard still builds.
- Scenes: from the first Markdown table in `storyboard.md` whose header's first cell starts with
  "Scene" and which has a column whose header starts with "Time" (case-insensitive). A row's start
  is the first number in its Time cell; a row without one gets no play button. The spoken words are
  the items of the Script section's numbered list when their count equals the row count, else the
  row's "Narration" cell, else its first cell whose header contains "text", else empty. Each row
  with a start gets `<button type="button" class="seek" data-seek="<start>">Play sN from X s</button>`;
  with two or more MP4s a radio group picks which player the buttons start. No usable table → the
  storyboard renders as Markdown text, tables included.
- Stills: a still's time is the number before the trailing `s` in `still-NN-<t>s.png`; its scene is
  the last row whose start ≤ t. Stills without a parsable time are captioned by file name.
- Sync chart: beat labels come from `word` in the project's `beats*.json` by beat `id`, else the id;
  a beat measured `via: "expected"` is labelled "(no onset)". One series per MP4, or one series and
  the sentence "Every cut measured the same offsets." when all MP4s agree.
- Outside calls: counts grouped by provider and subcommand (or host); every call to a provider that
  is not local (`hyperframes`, `playwright`) is also listed on its own row with time, what ran,
  status and bytes, and a call to a provider not in `cloud_allow` is marked "not allowed" in text.
  Unreadable lines in `calls.jsonl` are counted in a visible line.
- Earlier versions: each older version gets its heading, its note's verdict or plain verify
  verdict, its players, any missing-items line and a link to its `verify.json`; then a compare with
  two `<select>`s listing every MP4 of every version and two players.
- An older flat `verify.json` (no `runs`) and flat `frames/` still render.

`SCHEMA:` `<vN>/review-notes.md` (written by the agent after its frame review, before the page)
```
<one paragraph: the verdict, one or two sentences>

- <a thing the user should check before signing off>
- ...
```
The first paragraph becomes `summary`; everything after it renders as Markdown under "What I would
check before signing off". An empty list is fine ("nothing beyond the checks").

## Content contracts: SKILL.md and references

Back-links: [Behavior and scenarios](logic.md#behavior-and-scenarios), [Decisions Locked](logic.md#decisions-locked).

Each file must state the decisions and scenarios listed for it. Rows marked † get a string assertion
in `test_making_videos_skill.py`.

| File | Must state |
|---|---|
| `SKILL.md` | the 8 pipeline steps in order and the two stops; scope refusal before any work for over 3 min, avatars, publishing, editing user footage (SC-10) †; macOS only; every HyperFrames call via `hf.py` †, every cloud call via `cloud.py` †; 3 failed verify attempts → stop at review (SC-5) †; SKILL_DIR convention; a one-line pointer to each reference |
| `references/gather.md` | repo reading (README, docs, skill files), claims trace to sources; URL → `hf.py -- capture … --skip-vision`; web-app recording via `record.py`; native macOS recording unsupported, offer URL capture or web build instead (SC-8) |
| `references/brand.md` | studio layout and `brand.json`; extraction from CSS/assets/capture; draft brand shown at stop 1 and saved with `brand save --confirm` only when the storyboard is approved (SC-1) †; one saved voice reused; pronunciation patches |
| `references/storyboard.md` | script, scene list with timings, narration text, style frames, scene kit; narration default on above about 20 s (SC-1, SC-2) †; 9:16 and 1:1 are separate layout passes from one storyboard (SC-2); a 3D shot is proposed and marked in the storyboard, with Blender's status, and never rendered unseen (SC-3) †; if TTS install was declined the storyboard says the video is silent (SC-7); craft rules from `research/craft.md` (pace, hold times, hooks) with sources; the scene table's Time cell opens with the scene's start second, and the Script list has one item per scene when narration is on, so the review page can build its play buttons (SC-11) |
| `references/motion.md` | general motion principles and software-video specifics from `research/craft.md`; seek-safe GSAP rules from the trials: never `play()`, no nested `add()` of scene timelines, `fromTo` not `from`, no `repeat: -1`, no ScrollTrigger, `immediateRender: false` on stacked tweens †, `gsap.set` not `tl.set(…, 0)` |
| `references/hyperframes.md` | wrapper recipes for init/lint/check/snapshot/render/capture/audio; inline the `:root` font tokens, never a linked stylesheet † ; `--describe false` †; `HYPERFRAMES_NO_TELEMETRY` †; frames for review come from the MP4; the macOS screenshot-capture fallback warning |
| `references/audio.md` | narration build order (voice first, visuals timed to measured onsets); Kokoro + alignment via `voice.py`; loudness target −16 LUFS, true peak ≤ −1 dBTP †; music only from a user file or the stock opt-in, at least 20 dB under narration †; captions: burned for 9:16/1:1, `.srt` for 16:9 † |
| `references/3d.md` | `blender_render.py` usage; `--python-exit-code` †; .blend before `--python`; the guard runs automatically after the author's script, which must tolerate extra args via `parse_known_args`; TTF/OTF fonts; sRGB→linear for brand colours; Standard view transform; ease text to face camera (mirrored-text trap); fallback to 2D when Blender is missing (SC-3) |
| `references/review.md` | verify checks and their sources (logic amendment 2026-10-22); review page; stop 2; notes → new version, old versions kept (SC-6) †; 3-attempt cap (SC-5); after its frame review the agent writes `<vN>/review-notes.md` (verdict paragraph, then things to check) before running `review_page.py` (SC-11) †; the page is built with `writing-html-artifacts` and the script exits 1 if that skill is missing |
| `references/cloud.md` | local by default; a provider runs only when the brief names it (SC-4) †; a key in the environment is never permission †; providers, endpoints, auth headers and licence/attribution rules from `research/toolchain.md`; Gemini frame review not offered |
| `references/long-form.md` | over about 60 s: lock the scene kit first, subagents compose only from the kit, verify runs on the assembled MP4 (SC-9) † |

## Data models / schemas

Back-links: [Conceptual model](logic.md#conceptual-model), [Strict verify checks](logic.md#strict-verify-checks).

`SCHEMA:` `<studio>/brands/<product>/brand.json`
```
{ "product": str, "confirmed": bool,
  "colors": { "<token>": "#rrggbb", ... },
  "fonts": { "<role>": { "family": str, "files": [str] } },     # files: TTF/OTF/WOFF2 paths in the brand dir
  "logo": str | null,
  "voice": { "engine": "kokoro" | "elevenlabs" | "openai", "id": str },
  "pronunciations": { "<word>": { "from": str, "to": str } } }  # phoneme patch
```

`SCHEMA:` `<project>/brief.json`
```
{ "slug": str, "product": str, "title": str, "length_s": number,
  "aspects": ["16:9" | "9:16" | "1:1"], "narration": bool,
  "cloud_allow": [provider], "music": { "source": "none" | "file" | "stock", "path": str | null },
  "created": "YYYY-MM-DD" }
```

`SCHEMA:` `beats.json`
```
[ { "id": str, "word": str, "clip": str, "expected_s": number,
    "region": [x, y, w, h],            # 1080p pixel coords
    "baseline_s": number, "detector": "changed" | "color",
    "color": "#rrggbb" | null } ]      # required when detector is "color" (the trial's accent check)
```

`SCHEMA:` `CHECK` (inside verify.json)
```
{ "name": str, "status": "pass" | "fail" | "skip", "measured": any, "threshold": any, "detail": str }
```

Project layout:

`SCHEMA:`
```
<studio>/videos/<YYYY-MM-DD>-<slug>/
  brief.json  storyboard.md  kit/  assets/  calls.jsonl  review.src.html  review.html
  scenes/ (HyperFrames project, 16:9)  [scenes-9x16/  scenes-1x1/]   # one folder per aspect layout pass
  v1/ <slug>-16x9.mp4 [<slug>-9x16.mp4] [*.srt] frames/<mp4 stem>/ verify.json (runs per MP4) render.log [review-notes.md]
```

## DO-NOT-CHANGE fences

Back-links: [Key decisions and rationale](logic.md#key-decisions-and-rationale), [Decisions Locked](logic.md#decisions-locked).

- `README.md` beyond line 9 and the new "What ships" bullet. The other skills' wording there is
  asserted by `tests/test_using_apps_like_a_user_skill.py:149-152`.
- Version fields in `pyproject.toml:3`, `.claude-plugin/plugin.json:4`, `.claude-plugin/marketplace.json`, and
  `CHANGELOG.md`. `bin/release.py` stamps them at release; hand edits break the release diff.
- Every other `skills/*` directory. This work adds a skill; it changes no existing one. `review_page.py`
  calls `writing-html-artifacts`' builder as a subprocess and never edits that skill.
- `~/.hyperframes/config.json` and any global `~/.claude` or `~/.agents` path. The trials showed
  global writes are the failure we're preventing.

## Always / Ask / Never

Back-links: [Decisions Locked](logic.md#decisions-locked), [Key decisions and rationale](logic.md#key-decisions-and-rationale).

**Always**
- Route every HyperFrames call in docs and scripts through `hf.py`.
- Route every cloud call through `cloud.py`.
- Keep stdlib scripts importable on Python 3.9 with no third-party packages.
- Make tests hermetic: `QUIRK_STUDIO`/`QUIRK_VIDEO_CACHE` under `tmp_path`, fake executables on PATH,
  no network.
- Decode frames for review from the rendered MP4, never from snapshots.

**Ask** (stop and report NEEDS_CONTEXT)
- If `--caption-zone` bands can't flag text in the outer 5% in 0.8.185, report what it can do;
  don't invent a DOM probe.
- Which generated-image/video API(s) to accept in `cloud.py` if the toolchain research names none
  with a stable public endpoint.
- Any need to pin a HyperFrames version other than 0.8.185.

**Never**
- Call `hyperframes snapshot` with describing enabled, or pass Gemini keys to any child.
- Install anything without `--yes`, or install Blender, Node, ffmpeg or Chrome.
- Write outside `QUIRK_STUDIO`, `QUIRK_VIDEO_CACHE`, or the skill dir.
- Use `CLAUDE_PLUGIN_ROOT` in the skill (`tests/test_writing_html_artifacts_skill.py:83-84` pattern).

## Cross-cutting

Back-link: [Key decisions and rationale](logic.md#key-decisions-and-rationale).

- **Security:** cloud credentials only from env, only in headers, never in `calls.jsonl`, argv echoes
  or verify output. `cloud.py` builds requests with `urllib`; no shell.
- **Privacy:** the wrapper's env scrub is the guard against the Gemini leak; `outside_calls` is the
  audit.
- **Observability:** `calls.jsonl`, `render.log` and `verify.json` per version are the record the
  review page shows.
- **Rollback:** the skill writes only new directories under the studio and cache; deleting
  `skills/making-videos/` and the README line reverts the plugin.

## Testing strategy

Back-link: [Done when](logic.md#done-when).

- One test file per script (list in Architecture). Each runs the script through `subprocess` with
  `sys.executable`, asserts the single JSON object and the exit code, and covers its failure paths
  (missing tool → 3, refused install → 2, disallowed provider → 1, `--describe true` refused, Blender
  argv order and missing-.blend refusal, verify's 3-attempt `stop`).
- `verify` tests use small fixtures: an HTML project with a linked font stylesheet (fonts fail), a
  render log with and without the injection line, a canned `check --json`, a `calls.jsonl` with a
  disallowed provider. Tests needing real `ffmpeg` (loudness on a generated tone) skip when it's absent.
- Worker modules (`voice_worker`, `media_worker`) get logic tests guarded by
  `pytest.importorskip("numpy")`; CI without deps skips them.
- `test_making_videos_skill.py`: frontmatter `{name, description}`, `name == "making-videos"`,
  description 50–1024 chars starting "Use when"; SKILL.md body < 300 lines; every relative link resolves;
  every `scripts/<x>.py` named in SKILL.md and references exists; no `CLAUDE_PLUGIN_ROOT`; trigger evals
  ≥12 per polarity with `skill_name` match; trap strings present in references (`HYPERFRAMES_NO_TELEMETRY`,
  `--describe false`, `--python-exit-code`, inline font tokens, `immediateRender`), plus every †
  row in Content contracts.
- Acceptance bar per task: its own test file passes. Wave gate: `python3 -m pytest -q`.
- The three acceptance renders from [Done when](logic.md#done-when) are run by the orchestrator after
  the review loop, not by pytest.

## Non-goals

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

- No MCP server, no Blender addon, no use of the upstream HyperFrames/Remotion/GSAP skills at runtime.
- No Linux or Windows code paths beyond doctor's "unsupported platform" result.
- No automated visual judgment of frames (research found VLM judges near chance); the agent reviews
  decoded frames and the user signs off.
- No native macOS app recording, avatars, publishing, or editing user footage.
