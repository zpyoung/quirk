# Verify, review page and notes loop

Verify every render before the user sees it, look at the decoded frames yourself, then stop at the review page. Never tell the user a render is good because the preview or a snapshot looked right.

Contents:
- [The loop](#the-loop)
- [Preparing verify's inputs](#preparing-verifys-inputs)
- [Running verify](#running-verify)
- [The verify checks](#the-verify-checks)
- [Reading verify.json](#reading-verifyjson)
- [Your own visual pass](#your-own-visual-pass)
- [Review page and stop 2](#review-page-and-stop-2)
- [Notes become a new version](#notes-become-a-new-version)

`SKILL_DIR` is the directory holding SKILL.md, `P` is the project folder and `V` is the version folder (`$P/v1`).

## The loop

1. Render into `$V` (recipe in [hyperframes.md](hyperframes.md)) and prepare the inputs below.
2. Run `verify.py`.
3. If a check failed and `stop` is false, fix the cause, re-render into the same `$V`, regenerate every input, and verify again. The user has not seen this version yet, so rebuilding in place is allowed.
4. If `stop` is true, do not rebuild. Go to the review page with the failures flagged.
5. When verify passes, do your visual pass, write the review notes, build the page and stop.

Only failed verify runs count toward the stop. After 3 failed verify attempts on one MP4, verify sets `"stop": true` for it: stop looping and show the user the failing render with the failing checks flagged. A passing re-run (for example after a layout fix you chose to make) is free and does not add an attempt, so never copy a project to a scratch folder to verify there and dodge the counter. A new version starts its own count.

## Preparing verify's inputs

Regenerate all of these after every fix. A stale file from an earlier attempt makes verify judge the wrong render.

| Input | How to produce it | Needed for |
|---|---|---|
| MP4 | `hf.py ... render --output "$V/<slug>-16x9.mp4"`; verify takes the only `*.mp4` in `$V`. A 9:16 or 1:1 render is `<slug>-9x16.mp4` or `-1x1.mp4`, rendered from `scenes-9x16/` or `scenes-1x1/` | everything |
| Render log | the same render with `> "$V/render.log" 2>&1` | fonts |
| Check JSONs with band labels | for each aspect cut, four `hf.py ... check --json --caption-zone "<band>;severity=error;seek=.05,.15,.25,.35,.45,.55,.65,.75,.85,.95,1"` runs, one per edge band, saved as `$V/check-<band>.json` (`check-<band>-9x16.json` for the 9:16 cut, generated from `scenes-9x16/`; same for 1:1); the `seek=` list samples the whole film, because the default samples only its last instant (exact commands in [hyperframes.md](hyperframes.md#recipes)) | contrast, title-safe |
| Beats file | written when narration is on; see below. One per aspect: `beats.json` for 16:9, `beats-9x16.json`, `beats-1x1.json`. Verify picks the file by the MP4's name. A narrated video fails `sync` without it | sync |
| Audio JSON | verify runs `hf.py audio` itself for each beat clip; to supply your own, save `hf.py ... audio CLIP --only loudness,onsets,silence,envelope --hop-ms 10 --json` and pass `--audio-json CLIP=FILE` | sync |

The beats file is a list of the on-screen changes that must land on a spoken word. Write `$P/beats.json` while building the 16:9 visuals, and `$P/beats-9x16.json` and `$P/beats-1x1.json` for those cuts. Regions are pixels of the render being verified, so a 9:16 file cannot reuse 16:9 regions. Each entry:

```json
[{ "id": "ship-node", "word": "ship", "clip": "assets/voice/a.wav", "clip_start_s": 0.0, "expected_s": 1.3,
   "region": [820, 400, 280, 160], "baseline_s": 1.0, "detector": "changed", "color": null }]
```

- `clip` is the narration file that holds the word; `clip_start_s` is where that clip starts on the timeline; `expected_s` is where the word should fall on the timeline.
- `region` is `[x, y, w, h]` in pixels of the rendered frame, around the element that changes. In a captioned 9:16 or 1:1 cut, keep every region out of the caption band (below about y 1130 of 1920 in 9:16): the `changed` detector fires on the burned caption appearing and reports a constant offset that no tween shift fixes.
- `baseline_s` is a time before the beat when the region is still in its old state. The beat's moment is the first frame after it where the region changes.
- `detector` is `changed` (pixels in the region change) or `color` (the region shifts toward `color`, a `#rrggbb`).

## Running verify

```bash
python3 "$SKILL_DIR/scripts/verify.py" --project "$P" --version v1 \
  --render-log "$V/render.log" \
  --check-json top="$V/check-top.json" --check-json bottom="$V/check-bottom.json" \
  --check-json left="$V/check-left.json" --check-json right="$V/check-right.json" \
  --beats "$P/beats.json" --at 1.5,4.2,7.0
```

For a 9:16 cut, pass its own check JSONs and beats, for example `--check-json top="$V/check-top-9x16.json"` and `--beats "$P/beats-9x16.json"`; with `--mp4` naming a `-9x16.mp4`, verify picks `beats-9x16.json` itself when `--beats` is omitted.

- `--beats` is optional: verify uses the beats file for the MP4's aspect (`beats.json`, `beats-9x16.json` or `beats-1x1.json`) when it exists. Omit it for a silent video.
- `--at` lists seconds for the stills. Pass one settled instant per storyboard scene, after its last entrance finishes (scene end minus 0.5 s works), not the midpoint, which often lands mid-animation. The contact sheet is built from these `--at` stills, so a badly chosen instant shows an empty or half-entered card in both the sheet and the stills. When scenes overlap for the whole film, scene ends do not apply: pick the moments after each major move lands, and look at the animation to find them. The default is six evenly spaced stills.
- With several MP4s in `$V` (for example 16:9 and 9:16), verify refuses with exit 2. Pass `--mp4` and run once per file; for the second aspect, regenerate the check JSONs from its own `scenes-9x16/` folder. Each MP4 has its own run in `verify.json`, with its own attempt count and stop flag, so a 9:16 retry does not use up the 16:9 attempts. The printed JSON is the run you just made, plus `mp4`.
- Exit 0 means no check failed. Exit 1 means a check failed, or the MP4 is missing (`missing_render`). Exit 2 is a usage error such as an unreadable input. Exit 3 means ffmpeg or ffprobe is missing.
- Verify prints one JSON object. The detail of a failing check names what to run or fix.

## The verify checks

Each check reads the source that can see the thing: raw MP4 pixels cannot locate text, so contrast and title-safe come from HyperFrames `check` on the page. A check with status `skip` does not fail the run; read its detail to see why.

| Check | Source | Passes when |
|---|---|---|
| `fonts` | static scan of every HTML file under every `scenes*/` folder (`scenes/`, `scenes-9x16/`, `scenes-1x1/`), plus the render log; a `*-9x16.mp4` or `*-1x1.mp4` also needs its matching folder to exist and pass | every `var(--font-*)` resolves in an inline `<style>` or `style=` (in that file or the root `index.html`); no linked stylesheet defines `--font-*`; no `font:` shorthand uses `var(--font-*)` (write `font-family`); and the log's `Injected deterministic @font-face rules for N requested font families` has N at least the number of families in `brand.json` |
| `contrast` | `contrast.findings` in the check JSONs | no `contrast_aa_failure`; measured is the failing count and the worst ratio. It fails if a JSON has no enabled contrast section (lint errors skip the browser audit) or reports an error |
| `title_safe` | `layout.findings` in the four band JSONs, each sampled at eleven instants across the film | no `caption_zone_collision` in any band, and all four bands were supplied |
| `loudness` | `ffmpeg -af ebur128=peak=true` on the MP4 | narrated: integrated loudness from -17 to -15 LUFS and true peak at or below -1.0 dBTP. Silent video: skipped |
| `sync` | `beats.json`, `hf.py audio` per clip, and a pixel analysis run in the skill's venv | every beat's first changed frame is within one frame of its word's onset. Silent video: skipped when there are no beats or no venv. Narrated video: fails with "narrated videos need beats.json (see audio.md)" when there is no `beats.json`, and fails with the `doctor.py` fix when the venv is missing |
| `blender` | every `guard.json` under the project, except those under a `sketches/` folder | no default scene and no mirrored frames. Skipped without 3D |
| `render_log` | `render.log` | no known-bad compiler warning, such as `Video "<id>" has sparse keyframes`. Fix the cause and re-render ([hyperframes.md](hyperframes.md#render-log-warnings)) |
| `outside_calls` | `calls.jsonl` against the brief's `cloud_allow` | every logged cloud provider is in `cloud_allow`. Every `hf.py` and `record.py` call is logged too, as a local provider, so the count of logged calls can be large for a video with no cloud use; only cloud providers need allowing (HyperFrames and Playwright are local) |

Notes on interpreting results:
- A narrated video cannot pass with `sync` skipped. A failing `sync` with no `beats.json` means write it ([audio.md](audio.md)); with a missing venv, run `doctor.py check --need narration`.
- In `sync`, a beat flagged "no audio onset near the expected time" was timed against `expected_s` instead; look at it in the frames.
- A `title_safe` fail means an element box sits in the outer 5% of an edge. The bands test boxes, not glyphs, so a full-width centred text box fails even when its letters are well inside. Keep text boxes inside x 96..1824 and y 54..1026 at 1080p (scale for other sizes), for example with a `max-width`. Do not waive it with `data-layout-allow-caption-zone`.
- A `fonts` fail from the log means the MP4 may use fallback fonts. The fix is to inline the `:root` tokens in each composition ([hyperframes.md](hyperframes.md#fonts)).

## Reading verify.json

`$V/verify.json` holds `version`, `passed` and `runs`, keyed by MP4 filename. Top-level `passed` is true only when every run passed. Each run holds `attempt`, `passed`, `stop`, `checks`, `frames` and an `attempts` list (`n`, `ts`, `passed`). Each check has `name`, `status` (`pass`, `fail` or `skip`), `measured`, `threshold` and `detail`. `frames.sheet` is the contact sheet (built from the `--at` stills) and `frames.stills` the stills, all decoded from that MP4 into `$V/frames/<mp4 stem>/`. A `verify.json` from an earlier version of the script has no `runs`; verify reads it as the run for the single MP4 present, and the review page still shows it.

To decide: a run's `passed` false means at least one `fail`; read each failing check's `detail`, fix, and run again. A run's `stop` true means its third failed attempt happened; passing runs are not counted.

## Your own visual pass

Open the contact sheet and every still with the Read tool and write down what you saw in each. Verify measures; it cannot see whether a title is cut off or the wrong typeface. A model that says "looks fine" without naming what it saw is not a gate, and your pass never overrides a failed check.

Look for:
- Fonts: brand typeface, not a generic system sans or mono. This is the trap the font check exists for.
- Text cut off at an edge, overflowing its box, or overlapping another element.
- Timing: a line held long enough to read, an end card that holds, nothing popping in a frame early or late.
- Blank or black frames, especially the first and last frames.
- Mirrored or edge-on text in any 3D clip.
- Colours and logo against the brand; claims on screen against the storyboard. A few RGB units of drift from the H.264 bt709 encode is expected (a ground of 242, 239, 232 decodes near 241, 236, 231). Flag drift above about 8 per channel, or a visibly different hue.
- Small text: shrink the sheet in your head to phone size and check it still reads.

If you find a problem verify did not, fix it before the user sees the version. Report what you checked and what you could not see.

## Review page and stop 2

Write the review notes, then build the page. Do both after verify, and again after every new version.

The notes go in `<vN>/review-notes.md`, written from your own pass over the frames decoded from the MP4 and written before you run the script:

```markdown
<one paragraph: the verdict, one or two sentences>

- <a thing the user should check before signing off>
- <another>
```

The first paragraph becomes the page's summary under the title. Everything after it shows under "What I would check before signing off". An empty list is fine. Without the file the page still builds and says your frame review is not written yet, so a missing file never blocks stop 2, but write it every time.

```bash
python3 "$SKILL_DIR/scripts/review_page.py" --project "$P"
```

The script writes `$P/review.src.html`, builds `$P/review.html` from it through quirk's `writing-html-artifacts` skill (report template), and prints `{"page", "source", "checks"}`. It exits 1 if `writing-html-artifacts` is missing or its build or static checks fail, and it writes no fallback page, so report that failure instead of handing over an older `review.html`. A missing project exits 2.

The page is about 750 KB because the HTML kit is inlined. It opens from disk and makes no network calls. Its links are relative, so keep it inside the project folder. It shows, newest version first:
- the verdict, or "Stopped after 3 failed verify attempts" with the failing checks when verify stopped;
- findings generated from `verify.json`;
- one player per MP4, and a scene table whose play buttons jump to each scene (see the Time cell and Script list rules in [storyboard.md](storyboard.md#what-the-storyboard-file-holds));
- your check-before-signing-off list;
- the verify results in plain words, with a beat-offset chart when sync ran;
- verify's per-scene stills, one tab per MP4. The contact sheet is not on the page. Verify still writes it for your own pass;
- the outside calls: counts, then each cloud call on its own row, with providers outside `cloud_allow` marked;
- earlier versions with their players, and a compare of any two;
- links to the files.

A version missing its MP4, `verify.json` or stills gets a line naming what is missing.

Stop 2 is the point where you wait for the user. Tell them:
- the path to `review.html`, ready to open;
- the verify result in a sentence: how many checks passed, which failed or were skipped and why, and the attempt count;
- if `stop` was true, say so first and name the failing checks, because the version is shown as it is;
- what you saw in the frames, in one or two lines;
- a request for notes.

Then wait. Do not render again until notes arrive.

## Notes become a new version

Turn the user's notes into the next version; never edit a version they have seen.

1. Create the folder: `python3 "$SKILL_DIR/scripts/studio.py" version new --project "$P"` prints `{"version": "v2", "path": ...}`. It never reuses a number.
2. Apply the notes to `scenes/`, render into the new folder, and run the loop above. The new version has its own `verify.json` and attempt count.
3. Rebuild the page. It shows `v1` and `v2` side by side.

`v1`'s MP4, frames, `verify.json` and `render.log` stay exactly as they were. Scripts add files to a version folder and only `verify.py` updates `verify.json` there. If a note is unclear, ask which version it applies to before changing anything.
