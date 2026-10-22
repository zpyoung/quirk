---
name: making-videos
description: Use when the user asks for a video, explainer, motion graphics, an animated announcement or demo, a narrated or voiceover piece, or a rendered MP4, usually about software and up to 3 minutes. Builds it locally from a brief with HyperFrames, optional Kokoro narration and optional headless Blender, checks the rendered MP4, and hands over a review page. Not for editing footage the user shot, AI avatars or talking heads, videos over 3 minutes, or uploading and publishing.
---

# Making videos

Turn a brief into a finished MP4 of up to 3 minutes, run a fixed pipeline, and stop twice for the user: after the storyboard, and after the first full render. Everything runs locally unless the user names a cloud provider for this video.

`SKILL_DIR` is the directory holding this `SKILL.md`, which the host shows when the skill loads. Run every script as `python3 "$SKILL_DIR/scripts/<script>.py" ...`. Never build paths from a plugin-root environment variable: not every host sets one. Scripts print JSON to stdout and diagnostics to stderr. `$P` is the project folder, `~/Studio/videos/<date>-<slug>`.

## Refuse out-of-scope parts first

Read the brief before any work. If it asks for any of these, say which parts are out of scope, offer what you can do, and wait for the answer before starting:

- **Over 3 minutes.** Offer a cut of 3 minutes or less.
- **An avatar or talking-head presenter.** Offer the same video without a presenter.
- **Uploading or posting** to YouTube or social sites. Offer the MP4 and review page as files.
- **Editing footage the user shot.** Offer to build new motion graphics, or to record a running web app.
- **Windows or Linux.** The skill is macOS only. Say so and stop.

Example: "5 min with an AI presenter, upload to YouTube" becomes "I can make a 3 min cut without a presenter and give you the files; the length, presenter and upload are out of scope."

## Always-on rules

- **Every HyperFrames call goes through `hf.py`.** Never run `npx hyperframes`, `pnpm dlx hyperframes` or a global `hyperframes`. The wrapper pins the version, turns telemetry off, and removes cloud keys from the environment.
- **Every cloud call goes through `cloud.py`, and only for providers the user named for this video.** A key in the environment is never permission. The default is no cloud at all.
- **Frames for review come from the rendered MP4.** Previews, snapshots and `hyperframes check` passed a font fallback that only the MP4 showed. Never call a render good from a preview.
- **Versions are never overwritten.** `v1` stays as the user saw it; notes produce `v2`. Rebuilding in place is allowed only for a version the user has not seen.
- **3 failed verify attempts on one version means stop.** Only failed runs count; a passing re-run is free. Do not loop further, and never copy a project to dodge the counter. Show the failing render on the review page with the failing checks flagged.
- **Ask before installing.** Run `doctor.py install --yes` only after the user says yes. Never install Blender yourself, and never write installed skills into the user's global setup.
- **Write nothing into the user's repo.** Projects and brands live in `~/Studio`; heavy tools live in `~/.cache/quirk-video/`.
- **Every claim in the script traces to something you read.** No source, no claim.
- **Narration is on above about 20 s and off below it, unless the user asks.** A 9:16 or 1:1 cut is its own layout pass from the same storyboard, not a crop. Details are in [storyboard](references/storyboard.md).

## Pipeline

Follow the steps in order. Steps 4 and 7 are stops: ask, then wait.

1. **Doctor.** Run `python3 "$SKILL_DIR/scripts/doctor.py" check --need narration,3d,record`, listing only what the brief needs. Add `captions` whenever a 9:16 or 1:1 cut is requested, because burned captions need ffmpeg-full. Report what is missing. For installable pieces (`install --what tts` or `--what playwright`), say the size and ask; run with `--yes` only on a yes. If the user declines the TTS install, build the video silent and say so in the storyboard. Blender is not installed for the user: print its install command.
2. **Gather.** Read the repo, capture any URL the user gave, and record a running web app if the video shows one. Keep `$P/sources.md`. Native macOS app recording is not supported: say so and offer a URL capture or the web build. See [gather](references/gather.md).
3. **Brand.** Run `studio.py brand show --product <p>`. Reuse a confirmed brand, and skip the save at step 4: studio folders are shared across runs, so another run may have confirmed it. Otherwise extract a draft and save it unconfirmed. See [brand](references/brand.md).
4. **Storyboard (stop 1).** Create the project with `studio.py project new`, write `storyboard.md` with script, scene list, timings, style frames and the scene kit, and show it. On a first video, show the draft brand beside it. Mark any 3D shot as 3D with Blender's status. With narration on, you may run `voice.py say` and `voice.py align` first so the timings are measured rather than budgeted. Wait for approval, then save the brand with `brand save --confirm` unless it was already confirmed. See [storyboard](references/storyboard.md), and [cloud](references/cloud.md) if the user names a provider.
5. **Build.** With narration on, the voice comes first (skip `say` and `align` if you already ran them for stop 1): `voice.py say`, `voice.py align`, `voice.py captions`, then time each scene to the measured word starts. Scenes are built through `hf.py`. A 3D scene renders through `blender_render.py` into a clip HyperFrames composites. Over about 60 s, subagents may build scenes from the locked kit only. Read [motion](references/motion.md) and [hyperframes](references/hyperframes.md) always. Skip [audio](references/audio.md) when the video is silent, [3d](references/3d.md) when no shot is 3D, and [long-form](references/long-form.md) at 60 s or under.
6. **Render and verify.** Run `studio.py version new --project "$P"` before the first render, so `$P/v1` exists. Run it again before each re-render of a version the user has already seen (step 8 is that run), and never for a version they have not seen. Render the MP4 with `hf.py`, then run `verify.py --project "$P" --version v1`. Fix every failed check and render again before the user sees anything. Look at the decoded frames yourself. See [review](references/review.md).
7. **Review page (stop 2).** Run `review_page.py --project "$P"`, tell the user the path to `review.html`, the verify result in a sentence, and what you saw in the frames. Ask for notes and wait.
8. **Notes loop.** Run `studio.py version new --project "$P"`, apply the notes to the scenes, and repeat steps 5 to 7 for the new version, whose folder this command just created. Rebuild the page so old and new sit side by side. If a note is unclear, ask which version it applies to.

## When something fails

- **Verify fails.** Read `verify.json`, fix the cause, regenerate every input, and verify again. On the 3rd failed attempt, stop and go to step 7 with the failures flagged. Passing runs do not count toward the 3.
- **A tool is missing.** Run `doctor.py check` for the install command and ask the user. Do not install around the wrapper.
- **The brief names a provider.** Add it to `cloud_allow` in `brief.json` and read [cloud](references/cloud.md). Name only that provider in calls.
- **The brief does not name a provider but a key is set.** Do not call it. Voices come from Kokoro and visuals are built in code.

## References

Read a reference when its step starts, not before.

- [gather](references/gather.md): reading the repo, `hf.py capture` of a URL, `record.py` for a web app, and what is unsupported.
- [brand](references/brand.md): the `~/Studio` layout, extracting a brand, `brand show` and `brand save`, and tokens in compositions.
- [storyboard](references/storyboard.md): script craft, narration and aspect decisions, style frames, and the scene kit.
- [motion](references/motion.md): durations, easings, how to show software, seek-safe GSAP rules, and typography. Read it before writing any scene.
- [hyperframes](references/hyperframes.md): wrapper rules, project setup, authoring rules, fonts, render recipes, and render-log warnings.
- [audio](references/audio.md): `voice.py`, pronunciation, loudness targets, music ducking, captions, and beat sync.
- [3d](references/3d.md): `blender_render.py`, the scene script, colour, fonts, and compositing the clip.
- [long-form](references/long-form.md): locking the kit, briefing scene subagents, and verifying the assembled MP4.
- [review](references/review.md): `verify.py`, the eight checks, your visual pass, the review page, and notes.
- [cloud](references/cloud.md): `cloud_allow`, `cloud.py call`, and the call log.
