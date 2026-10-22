# Logic spec: `making-videos`, a local-first video skill

**Status**: Approved · Tech spec: authored (`tech.md`; tier gate fired: touches >3 source files across skill docs, scripts, and tests)

On 2026-10-22 we ran seven parallel trials of a Reddit post's Claude Code video stack (HyperFrames,
Remotion, GSAP skills, the LottieFiles motion-design skill, Blender MCP) in the `vst-t*` Orca worktrees
under `~/orca/workspaces/quirk/`. HyperFrames plus motion-design guidance plus Kokoro narration made the
best videos. The same trials hit four traps, and none of them showed up until the MP4 was decoded:

- `hyperframes snapshot` sent frames to Gemini because a key was in the environment.
- Telemetry was on.
- `hyperframes init` installed skills globally.
- Fonts linked from a stylesheet rendered as system fonts in the MP4 while every preview looked right.

`making-videos` packages what worked into one quirk skill and turns each trap into code. It uses CLIs
and APIs only, with no MCP server. Blender runs headless from its own command line.

## Conceptual model

The skill turns a brief into a finished MP4 of up to 3 minutes. It is tuned for videos about software
(feature explainers, release and skill announcements, how-it-works pieces), but its motion guidance is
general so other kinds of video can follow later. It runs a fixed pipeline with two stops where it
waits for the user.

It works with four things, all outside the user's repo:

| Thing | Where | What it holds |
|---|---|---|
| Studio | `~/Studio`, one per machine | Every brand and every video project |
| Brand | `~/Studio/brands/<product>/` | Colour and type tokens, fonts, logo, the saved narration voice |
| Video project | `~/Studio/videos/<date>-<slug>/` | Brief, storyboard, scene kit, assets, scenes, review page |
| Version | `v1/`, `v2/`, … inside a project | One render: the MP4, any captions file, frames decoded from that MP4, the verify results |

A brand is extracted once per product, confirmed by the user, and reused by every later video for that
product. A version is never overwritten.

Heavy shared tools live in one machine-wide cache, `~/.cache/quirk-video/`: the Python TTS environment,
the Whisper models, and the pinned HyperFrames CLI. They download once per machine, not once per project.

The skill carries its own condensed guidance, written from the trials, the upstream HyperFrames and
motion-design skills, and a web best-practices research pass. It does not need the upstream skills
installed.

## Data flow

1. **Doctor** checks Node, ffmpeg, Chrome, the Python TTS environment, and Blender when 3D is planned.
   It lists what's missing. With the user's yes it installs the safe pieces (the TTS environment and
   models into the shared cache). For the rest it prints the install command.
2. **Gather** reads the brief, then whatever the video needs: the repo's README, docs and skill files,
   any URL the user gives (taken as a `hyperframes capture`), and a recording of a running web app made
   with Playwright's video recording. Every claim in the script traces to something it read.
3. **Brand.** If the product has a saved brand, the skill reuses it. If not, it extracts colours, fonts
   and logo from the repo's CSS and assets or from the capture, and saves the draft.
4. **Storyboard.** The skill writes the script, a scene list with timings, the narration text, still
   style frames for the key scenes, and the scene kit. **This is the first stop.** On a product's first
   video, the draft brand is shown here too and saved as confirmed when the storyboard is approved.
5. **Build.** When narration is on, the voice comes first. Kokoro speaks the lines, Whisper measures
   each word's start, and the visuals are timed to those measurements. Scenes are built through a
   wrapper around the pinned HyperFrames CLI. Videos over about 60 s may hand scenes to subagents, which
   compose only from the locked scene kit. A 3D scene renders headless through Blender into a clip that
   HyperFrames composites.
6. **Render and verify.** The skill renders the MP4, then decodes frames from it and checks them. A
   failed check sends the work back to step 5 before the user sees it.
7. **Review page.** A local HTML page per project shows the player, the storyboard, the decoded frames,
   the verify results, every outside call made, and every version side by side. **This is the second
   stop.**
8. **Notes loop.** The user's notes produce the next version, which runs steps 5 to 7 again.

## Key decisions and rationale

- **Scripts own the steps that went wrong in the trials; the model owns creative judgment.** Prose rules
  were skipped in the trials, even with explicit warnings in the brief. A wrapper that always sets the
  version, turns telemetry off and strips cloud keys can't be skipped. Anthropic's skill guidance makes
  the same split.
- **Frames are checked from the real MP4, never from snapshots or the preview server.** In trial t1 the
  font fallback passed `hyperframes check`, snapshots and preview, and appeared only in the rendered file.
- **Narration is built before the visuals.** Trial t2 reached −27 to +7 ms sync by timing each beat to a
  measured word start. Timing the voice to finished visuals has no such anchor.
- **The scene kit is locked before anything is built in parallel.** Published multi-agent video work found
  style drift when shared style lived in prompts, and found it stopped once the visual language lived in a
  shared code kit.
- **Cloud is opt-in per video, by name.** An API key in the environment is never permission. This is what
  caused the Gemini leak.
- **HyperFrames is pinned and bumped on purpose,** so a render made today renders the same next month.
- **Blender runs as `blender -b <file> --python <script> --python-exit-code 1 -- <args>`.** The
  `.blend` must come before `--python`. Without `--python-exit-code`, a script error still exits 0. A
  missing scene file renders Blender's default cube without complaint. The Blender script enforces all
  three.
- **Gemini frame review is not offered.** Claude reviews the decoded frames itself, so it would duplicate
  work and add a cloud call.

## Behavior and scenarios

1. **SC-1 First video for a new product**
   - **Given** no saved brand for the product, and a brief asking for a 20 s release announcement
   - **When** the user invokes the skill from the product's repo
   - **Then** the first stop is the storyboard, with the draft brand shown beside it. Narration is off
     because the video isn't over about 20 s. After approval the skill saves the brand as confirmed,
     renders `v1`, verifies it, and makes its second stop at the review page.
   - **Data before:** **Studio**: no brand for "Acme CLI"*; **Repo**: README, `docs/`, `site.css`*
   - **Walkthrough:**
     1. Doctor finds every 2D tool present.
     2. Gather reads the README and the release notes.
     3. Brand extracts green `#1e7a52`*, Outfit and IBM Plex Mono from `site.css`*.
     4. The storyboard shows 3 scenes*, no narration, and the draft brand. The user approves it.
     5. Build, render and verify pass on the first try.
   - **Data after:** **Brand "Acme CLI"**: ✓ confirmed; **Project**: ✓ `v1/` with MP4 and verify
     results; **Review page**: ✓ open for notes

2. **SC-2 Narrated explainer with a vertical cut**
   - **Given** a saved brand with voice `af_heart`, and a brief for a 90 s explainer plus a 9:16 version
   - **When** the user approves the storyboard
   - **Then** narration is on (over about 20 s). The 16:9 render gets an `.srt` file alongside it. The
     9:16 render is a separate layout pass from the same storyboard and has captions burned in. Both
     share one narration track.
   - **Data before:** **Brand**: voice `af_heart`; **Brief**: 90 s, 16:9 + 9:16
   - **Walkthrough:**
     1. Kokoro speaks the script in voice `af_heart`. Whisper measures each word's start.
     2. Scenes are timed to the word starts and built in 16:9.
     3. The vertical layout reuses the scenes' content and timing with a new arrangement.
     4. Verify checks sync and loudness on both renders.
   - **Data after:** **v1**: ✓ `explainer-16x9.mp4` + `.srt`; ✓ `explainer-9x16.mp4` with burned-in captions

3. **SC-3 The agent proposes a 3D shot and Blender is missing**
   - **Given** a brief that doesn't mention 3D, and Blender not installed
   - **When** the agent decides a 3D shot would help and writes it into the storyboard
   - **Then** the storyboard marks the shot as 3D and notes that Blender is missing, with its install
     command. The user can strike the shot, install Blender, or approve a 2D fallback. The skill never
     renders a 3D shot the user hasn't seen in the storyboard.

4. **SC-4 A cloud service named for one video**
   - **Given** `GEMINI_API_KEY` and `ELEVENLABS_API_KEY`* set in the environment
   - **When** the brief says "use ElevenLabs for the voice"
   - **Then** only ElevenLabs is called. Gemini is never called, because a key alone is not permission.
     The review page lists the ElevenLabs calls. The brand's saved voice is unchanged unless the user
     asks to save the new one.
   - **Data before:** **Environment**: Gemini key set; ElevenLabs key set*
   - **Walkthrough:**
     1. The brief names ElevenLabs, so the voice step calls it for 6 lines*.
     2. Every HyperFrames call runs through the wrapper with the Gemini keys removed.
   - **Data after:** **Review page, outside calls**: ✓ ElevenLabs × 6*; ✗ Gemini none

5. **SC-5 Verify catches a font fallback**
   - **Given** a scene that links its fonts from a stylesheet
   - **When** verify decodes frames from the rendered MP4
   - **Then** verify fails the font check. The skill fixes the scene (inlining the tokens) and renders
     again before showing the user anything. After 3 failed attempts on one version it stops at the
     review page with the failing checks flagged instead of looping further.

6. **SC-6 Notes become a new version**
   - **Given** `v1` on the review page
   - **When** the user writes "hold the end card a second longer; make the labels bigger"
   - **Then** the skill builds `v2` from `v1` with those two changes. It leaves `v1` untouched and shows
     both side by side on the review page.
   - **Data before:** **Project**: `v1/` (10.0 s*)
   - **Walkthrough:**
     1. The skill applies both notes to the scenes.
     2. It renders and verifies `v2`.
   - **Data after:** **Project**: `v1/` ✓ unchanged; `v2/` ✓ 11.0 s*; **Review page**: ✓ v1 and v2 side by side

7. **SC-7 First run on a bare machine**
   - **Given** a Mac with Node and ffmpeg but no TTS environment and no Blender
   - **When** the skill starts a narrated video
   - **Then** doctor lists the TTS environment and models (about 800 MB) as installable and Blender as
     not needed for this video. It installs the TTS pieces into the shared cache only after the user says
     yes. Declining means the video is built silent, and the storyboard says so.

8. **SC-8 Footage of a running web app**
   - **Given** a brief asking to show the app's onboarding flow, and the app running at a local URL
   - **When** the gather step runs
   - **Then** the skill records the flow with Playwright's video recording and uses the clip as footage in
     a scene. Recording a native macOS app is not supported. The skill says so and offers a URL capture
     or a recording of the web build instead.

9. **SC-9 A long piece built in parallel**
   - **Given** an approved storyboard for a 2.5 min video with 9 scenes*
   - **When** the build step starts
   - **Then** the scene kit is already locked from the storyboard step. Subagents build scenes using only
     the kit's tokens, motion roles and components. Verify runs on the assembled MP4, not on single scenes.

10. **SC-10 A request outside scope**
    - **Given** a brief asking for a 5 min video with an AI presenter, uploaded to YouTube
    - **When** the skill reads the brief
    - **Then** it says which parts are out of scope (over 3 min, avatars, publishing) before any work and
      offers what it can do, such as a 3 min cut without a presenter, delivered as files.

### Strict verify checks

Verify takes each check from the source that can see it (see Amendments): the rendered MP4 and its
logs, plus HyperFrames `check` on the page for contrast and title-safe. Every check produces a
measured number in the version's verify results.

| Check | Passes when |
|---|---|
| Fonts | Each text style's rendered glyphs match the brand font, not a system fallback |
| Title-safe | No text outside the central 90% of the frame |
| Contrast | Text meets WCAG AA (4.5:1, or 3:1 for large text) against what's behind it |
| Loudness | Narrated videos measure about −16 LUFS integrated with a true peak at or below −1 dBTP |
| Voice sync | Each timed beat's first changed frame is within one frame of its word's measured start |
| Blender | No default-cube render, no mirrored text in a 3D clip |
| Outside calls | No cloud call the brief didn't name |

## Scope and non-goals

In scope: videos up to 3 minutes; 16:9 by default with 9:16 or 1:1 on request; repo, URL capture and
web-app recordings as sources; Kokoro narration with named cloud voices as opt-ins; stock media and
generated media as named opt-ins; Blender 3D scenes when the brief asks or the agent proposes one.

Out of scope for v1:

- AI avatars or talking-head presenters
- Uploading or posting to YouTube or social sites
- Editing footage the user shot
- Videos over 3 minutes
- Windows and Linux (the skill runs on macOS only, and doctor says so elsewhere)
- Gemini frame review
- Recording native macOS apps (deferred, below)

## Decisions Locked

**Scope**
- Main job: short videos about software, with general motion guidance so other video types can follow.
- Longest video: 3 minutes.
- Aspect: 16:9 by default; 9:16 or 1:1 on request, each its own layout pass.
- Inputs: the brief plus anything the video needs (repo, URL capture, web-app recording).
- Platform: macOS only.
- Excluded: avatars, publishing, editing the user's own footage.
- Name: `making-videos`, invoked as `/quirk:making-videos`.

**3D**
- Blender runs from its own CLI, headless, with no MCP.
- Optional stage, used when the brief asks or when the agent proposes it in the storyboard.
- Full 3D scenes are allowed, not just titles.

**Install**
- The skill carries its own comprehensive guidance, drawn from the upstream skills and web best
  practices, and calls a pinned HyperFrames CLI.
- HyperFrames is pinned in the skill and bumped on purpose.
- Doctor reports gaps and installs the safe pieces after the user's yes.
- Heavy tools live in one shared cache in the home folder.
- Projects live outside the repo, in `~/Studio`, with a brand folder per product.
- First-time brands are extracted, shown to the user, then saved.

**Cloud**
- Local by default. A cloud API runs only when the user names it for that video.
- Available opt-ins: cloud TTS (ElevenLabs or OpenAI), stock media (Pexels, Pixabay, Freesound),
  generated images or video.
- HyperFrames telemetry is always off for the skill's runs, set per command.

**Audio**
- Narration is on for videos over about 20 s and off for shorter ones unless asked.
- One voice saved with the brand and reused.
- Music only from a user-supplied file or the stock opt-in, ducked under narration.
- Captions are burned in for 9:16 and 1:1; 16:9 gets an `.srt` file alongside.

**Review**
- Two stops: after the storyboard, then after the first full render.
- A local review page per project with player, storyboard, decoded frames and version history.
- Notes produce a new version; every version is kept.
- Strict self-check before the user sees a render.
- After 3 failed verify attempts on one version, the skill stops and shows the failing render.

**Approach**
- One phased skill with a few deterministic scripts. Scene subagents only for long pieces, after the
  scene kit is locked.

## Industry Insights

From the trials (2026-10-22, notes in each `vst-t*` worktree's `NOTES.md`):

- The t1 font fallback appeared only in the MP4; `check`, snapshots and preview all looked right.
- `hyperframes snapshot` sent frames to Gemini 10 times across four trials whenever a key was present.
- t2 measured voice sync at −27 to +7 ms by timing beats to Whisper word starts.
- The separate GSAP skills gave five pieces of advice that break a seek-based render (`play()`, nested
  `add()`, `from()`, `repeat: -1`, ScrollTrigger).
- t7's Blender socket timed out on long renders while Blender kept rendering. The headless CLI has no
  socket.

From research:

- Keep `SKILL.md` under 500 lines, references one level deep, and prefer scripts for deterministic steps.
  Only a script's output costs context.
  ([Anthropic skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices))
- HyperFrames treats `lint` and `check` as required gates and forbids `Date.now()`, unseeded randomness
  and render-time network fetches. Its own repo says its skills "carry knowledge, not process."
  ([hyperframes CLAUDE.md](https://github.com/heygen-com/hyperframes/blob/main/CLAUDE.md))
- A practitioner who shipped two HyperFrames videos: "Watch the render before declaring victory." On macOS
  the renderer fell back to screenshot capture mode with only a warning.
  ([Trilogy AI](https://trilogyai.substack.com/p/first-contact-with-hyperframes))
- Prompting alone left Remotion scenes with fonts from 14 to 19 px for the same role. Moving the visual
  language into a shared code kit fixed it.
  ([Roboto Studio](https://robotostudio.com/blog/how-to-use-remotion-agent-skills-with-claude-code))
- Per-scene parallel workers trade away shared context; one pipeline gives each worker the planner's full
  history to compensate. ([Bleu](https://docs.buildbleu.com/blog/using-llms-to-generate-educational-videos-with-manim/))
- Automated VLM judging of rendered scenes agreed with humans at about chance in one study, so a model's
  "looks fine" is not a gate. ([ManimAgent](https://arxiv.org/html/2606.30296))
- Blender headless: the `.blend` must come before `--python`, script errors exit 0 unless
  `--python-exit-code` is set, and a missing `.blend` silently renders the default scene.
  ([Renderset docs](https://docs.polygoniq.com/renderset/1.8.0/advanced_topics/headless_rendering/),
  [Blender manual](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html))
- No source compared one wrapper CLI against calling each tool directly; the CLI-vs-MCP benchmarks compare
  `gh` against an MCP server. ([Scalekit](https://www.scalekit.com/blog/mcp-vs-cli-use))

## Deferred Ideas

- Recording native macOS apps with `screencapture` (needs Screen Recording permission).
- Linux and Windows support.
- `[tech-spec]` Exact HyperFrames version to pin and the bump procedure.
- `[tech-spec]` How the font check tells a brand glyph from a fallback (rendered-glyph comparison vs
  Chrome's font report during render).
- `[tech-spec]` The scene kit's file format and how subagents receive it.
- `[tech-spec]` Whether the review page uses the house Web Awesome + Bulma scaffold or quirk's
  `writing-html-artifacts` templates.
- `[tech-spec]` The acceptance harness for the three runs below.

## Done when

A fresh agent with only `making-videos` loaded completes three runs, and the user signs off on each
review page:

1. A 20 s silent announcement.
2. A narrated explainer of about 90 s with a 9:16 cut.
3. A short piece with a Blender 3D scene.

Each run passes every strict verify check, makes no cloud call the brief didn't name, and sends no
telemetry.

## Glossary

- **Brand**: a product's saved tokens, fonts, logo and narration voice, reused across its videos.
- **Doctor**: the first step; it checks tools and installs the safe ones with the user's yes.
- **Scene kit**: the locked tokens, named motion roles and shared components every scene composes from.
- **Stop**: a point where the skill waits for the user's approval. There are two: storyboard and review.
- **Studio**: `~/Studio`, the machine-wide home for brands and video projects.
- **Verify**: the strict check on frames and audio decoded from the rendered MP4.
- **Version**: one immutable render folder (`v1`, `v2`, …) with its verify results.
- **Wrapper**: the script every HyperFrames call goes through. It pins the version, turns telemetry
  off, and removes cloud keys the brief didn't name.

## Status & amendments

**Amendments:**

- 2026-10-22, assumed (question timed out, recommended default applied): verify takes each check from
  the source that can see it, not all from the decoded MP4. Contrast and title-safe come from
  HyperFrames `check` on the page, which knows where text is. Fonts come from a static check that
  tokens are inlined, the render log's font-injection line, and the agent viewing frames decoded from
  the MP4. Loudness, voice sync, Blender and outside calls come from the MP4 and the logs. Raw MP4
  pixels can't locate text, so the original wording couldn't be built as written.
