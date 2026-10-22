# Verify, review page and notes loop

Verify every render before the user sees it, look at the decoded frames yourself, then stop at the review page. Never tell the user a render is good because the preview or a snapshot looked right.

Contents:
- [The loop](#the-loop)
- [Preparing verify's inputs](#preparing-verifys-inputs)
- [Running verify](#running-verify)
- [The seven checks](#the-seven-checks)
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
5. When verify passes, do your visual pass, build the page and stop.

Each verify run adds one attempt to that MP4's run in `$V/verify.json`. After 3 failed verify attempts on one MP4, verify sets `"stop": true` for it: stop looping and show the user the failing render with the failing checks flagged. A new version starts its own count.

## Preparing verify's inputs

Regenerate all of these after every fix. A stale file from an earlier attempt makes verify judge the wrong render.

| Input | How to produce it | Needed for |
|---|---|---|
| MP4 | `hf.py ... render --output "$V/<slug>-16x9.mp4"`; verify takes the only `*.mp4` in `$V`. A 9:16 or 1:1 render is `<slug>-9x16.mp4` or `-1x1.mp4`, rendered from `scenes-9x16/` or `scenes-1x1/` | everything |
| Render log | the same render with `> "$V/render.log" 2>&1` | fonts |
| Check JSONs with band labels | four `hf.py ... check --json --caption-zone "<band>;severity=error;seek=.05,.15,.25,.35,.45,.55,.65,.75,.85,.95,1"` runs, one per edge band, saved as `$V/check-<band>.json`; the `seek=` list samples the whole film, because the default samples only its last instant (exact commands in [hyperframes.md](hyperframes.md#recipes)) | contrast, title-safe |
| `beats.json` | written when narration is on; see below. A narrated video fails `sync` without it | sync |
| Audio JSON | verify runs `hf.py audio` itself for each beat clip; to supply your own, save `hf.py ... audio CLIP --only loudness,onsets,silence,envelope --hop-ms 10 --json` and pass `--audio-json CLIP=FILE` | sync |

`beats.json` is a list of the on-screen changes that must land on a spoken word. Write it at `$P/beats.json` while building the visuals:

```json
[{ "id": "ship-node", "word": "ship", "clip": "assets/voice/a.wav", "expected_s": 1.3,
   "region": [820, 400, 280, 160], "baseline_s": 1.0, "detector": "changed", "color": null }]
```

- `clip` is the narration file that holds the word; `expected_s` is where the word should fall on the timeline.
- `region` is `[x, y, w, h]` in pixels of the rendered frame, around the element that changes.
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

- `--beats` is optional: verify uses `$P/beats.json` when it exists. Omit it for a silent video.
- `--at` lists seconds for the stills. Pass the midpoint of each storyboard scene; the default is six evenly spaced stills.
- With several MP4s in `$V` (for example 16:9 and 9:16), verify refuses with exit 2. Pass `--mp4` and run once per file; for the second aspect, regenerate the check JSONs from its own `scenes-9x16/` folder. Each MP4 has its own run in `verify.json`, with its own attempt count and stop flag, so a 9:16 retry does not use up the 16:9 attempts. The printed JSON is the run you just made, plus `mp4`.
- Exit 0 means no check failed. Exit 1 means a check failed, or the MP4 is missing (`missing_render`). Exit 2 is a usage error such as an unreadable input. Exit 3 means ffmpeg or ffprobe is missing.
- Verify prints one JSON object. The detail of a failing check names what to run or fix.

## The seven checks

Each check reads the source that can see the thing: raw MP4 pixels cannot locate text, so contrast and title-safe come from HyperFrames `check` on the page. A check with status `skip` does not fail the run; read its detail to see why.

| Check | Source | Passes when |
|---|---|---|
| `fonts` | static scan of every HTML file under every `scenes*/` folder (`scenes/`, `scenes-9x16/`, `scenes-1x1/`), plus the render log; a `*-9x16.mp4` or `*-1x1.mp4` also needs its matching folder to exist and pass | every `var(--font-*)` resolves in an inline `<style>` or `style=` (in that file or the root `index.html`); no linked stylesheet defines `--font-*`; and the log's `Injected deterministic @font-face rules for N requested font families` has N at least the number of families in `brand.json` |
| `contrast` | `contrast.findings` in the check JSONs | no `contrast_aa_failure`; measured is the failing count and the worst ratio. It fails if a JSON has no enabled contrast section (lint errors skip the browser audit) or reports an error |
| `title_safe` | `layout.findings` in the four band JSONs, each sampled at eleven instants across the film | no `caption_zone_collision` in any band, and all four bands were supplied |
| `loudness` | `ffmpeg -af ebur128=peak=true` on the MP4 | narrated: integrated loudness from -17 to -15 LUFS and true peak at or below -1.0 dBTP. Silent video: skipped |
| `sync` | `beats.json`, `hf.py audio` per clip, and a pixel analysis run in the skill's venv | every beat's first changed frame is within one frame of its word's onset. Silent video: skipped when there are no beats or no venv. Narrated video: fails with "narrated videos need beats.json (see audio.md)" when there is no `beats.json`, and fails with the `doctor.py` fix when the venv is missing |
| `blender` | every `guard.json` under the project | no default scene and no mirrored frames. Skipped without 3D |
| `outside_calls` | `calls.jsonl` against the brief's `cloud_allow` | every logged provider is allowed (HyperFrames and Playwright are local) |

Notes on interpreting results:
- A narrated video cannot pass with `sync` skipped. A failing `sync` with no `beats.json` means write it ([audio.md](audio.md)); with a missing venv, run `doctor.py check --need narration`.
- In `sync`, a beat flagged "no audio onset near the expected time" was timed against `expected_s` instead; look at it in the frames.
- A `title_safe` fail means text sits in the outer 5% of an edge. Move the text. Do not waive it with `data-layout-allow-caption-zone`.
- A `fonts` fail from the log means the MP4 may use fallback fonts. The fix is to inline the `:root` tokens in each composition ([hyperframes.md](hyperframes.md#fonts)).

## Reading verify.json

`$V/verify.json` holds `version`, `passed` and `runs`, keyed by MP4 filename. Top-level `passed` is true only when every run passed. Each run holds `attempt`, `passed`, `stop`, `checks`, `frames` and an `attempts` list (`n`, `ts`, `passed`). Each check has `name`, `status` (`pass`, `fail` or `skip`), `measured`, `threshold` and `detail`. `frames.sheet` is the contact sheet and `frames.stills` the stills, all decoded from that MP4 into `$V/frames/<mp4 stem>/`. A `verify.json` from an earlier version of the script has no `runs`; verify reads it as the run for the single MP4 present, and the review page still shows it.

To decide: a run's `passed` false means at least one `fail`; read each failing check's `detail`, fix, and run again. A run's `stop` true means its third attempt also failed.

## Your own visual pass

Open the contact sheet and every still with the Read tool and write down what you saw in each. Verify measures; it cannot see whether a title is cut off or the wrong typeface. A model that says "looks fine" without naming what it saw is not a gate, and your pass never overrides a failed check.

Look for:
- Fonts: brand typeface, not a generic system sans or mono. This is the trap the font check exists for.
- Text cut off at an edge, overflowing its box, or overlapping another element.
- Timing: a line held long enough to read, an end card that holds, nothing popping in a frame early or late.
- Blank or black frames, especially the first and last frames.
- Mirrored or edge-on text in any 3D clip.
- Colours and logo against the brand; claims on screen against the storyboard.
- Small text: shrink the sheet in your head to phone size and check it still reads.

If you find a problem verify did not, fix it before the user sees the version. Report what you checked and what you could not see.

## Review page and stop 2

Build the page after verify, and again after every new version.

```bash
python3 "$SKILL_DIR/scripts/review_page.py" --project "$P"
```

It writes `$P/review.html` and prints `{"page": ...}`. The page is one self-contained file that opens from disk. It shows a player per version, the storyboard, each MP4's contact sheet and stills, each MP4's verify checks with their measured values, the outside calls, and a version list, newest first, with a side-by-side compare of any two. A version missing its MP4, `verify.json` or frames still gets a row saying what is missing. A missing project exits 2.

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
