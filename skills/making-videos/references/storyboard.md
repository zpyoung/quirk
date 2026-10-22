# Storyboard: script, scene list, style frames, scene kit

The storyboard is stop 1. Write it, show it to the user with the draft brand if the brand is new, and
build nothing until the user approves it. Scope limits (over 3 min, avatars, publishing, editing user
footage) are handled before this phase; see [SKILL.md](../SKILL.md).

Contents:
- What the storyboard file holds
- Decide narration and aspects
- Script craft: hook, pace, hold times, structure templates
- Aspect handling
- 3D shots
- Style frames
- The scene kit
- Before you show it

## What the storyboard file holds

Write `<project>/storyboard.md` with these parts, in this order:

1. Header: title, product, length in seconds, aspects, narration on or off, and one line on voice
   (saved voice id, or "silent: TTS install declined").
2. Script: the narration text in full when narration is on; otherwise the on-screen copy in reading order.
3. Scene list: a table with scene id, start and end time in seconds, what is on screen, the on-screen
   text, the narration lines, the source each claim traces to, and the motion roles used.
4. Style frames: paths to the stills for key scenes (see Style frames).
5. Scene kit: the locked tokens, motion roles and components (see The scene kit).
6. Flags: any 3D shot with Blender's status, any cloud service the brief named, anything the user must decide.

Every claim on screen or in the script traces to something gather read. A claim without a source gets
cut or flagged for the user.

## Decide narration and aspects

- Narration defaults on for videos over about 20 s and off for shorter ones, unless the brief says
  otherwise. Write the decision into the header.
- If narration is on and the TTS environment is missing, doctor has already offered to install it. If the
  user declined, set narration off and put "This video is silent" in the header so the user sees it at stop 1.
- 16:9 is the default. Add 9:16 or 1:1 only when the brief asks. All aspects share one storyboard: same
  scenes, same timings, same words.

## Script craft

Open with the hook, keep one idea per scene, and budget words from the time you have. Numbers below are
conventions from video-platform guidance and subtitle standards, not laws; the sources are in the links.

### Hook (first 5 seconds)

- The first frame carries the subject with no logo sting. It should work as a still thumbnail with no sound.
- Name the problem or product by about 3 s (a vendor convention) and show the product by 5 s
  ([Google ABCD](https://www.thinkwithgoogle.com/_qs/documents/8472/ABCD_Complete_V7b_HR_1.pdf): "Introduce your brand or product in the first 5 seconds").
- Put at least two distinct visual beats in the first 5 s (same source), so early scenes run about 2.5 s or less.
- Show the point instead of stating it. Wistia found the biggest viewer drop in the opening
  seconds and advises cutting intro graphics ([Wistia](https://wistia.com/learn/marketing/understanding-audience-retention)).
- Build for sound off: large type, high contrast. TikTok reports 90% of ad recall impact lands in the first
  6 s ([TikTok](https://ads.tiktok.com/business/en/blog/creative-best-practices-top-performing-ads)).

### Narration pace and word budget

A common default is 150 words per minute (2.5 words per second). Narrated MOOC videos averaged 156 wpm
([Guo et al., L@S 2014](https://up.csail.mit.edu/other-pubs/las2014-pguo-engagement.pdf)), and explainer
guides cite about 150 words for 60 s. These are listening rates for speech; do not apply the 160-180 wpm
subtitle limits to narration.

| Length | Words at 150 wpm |
|---|---|
| 15 s | about 37 |
| 30 s | about 75 |
| 60 s | about 150 |
| 90 s | about 225 |
| 180 s | about 450 |

Subtract about 10% when silent beats carry part of the scene. Pauses cost time: three deliberate pauses
turned a 150-word script into about 70 s in one vendor test. After Kokoro speaks the lines, the measured
length is the truth; adjust the script, not the speed.

Adults read silently faster than people speak (238 wpm for non-fiction, [Brysbaert 2019](https://www.sciencedirect.com/science/article/abs/pii/S0749596X19300786)),
so text that repeats the narration is read ahead of the voice. Use on-screen text for labels and keywords,
not a transcript ([Mayer's redundancy principle](https://educationaltechnology.net/mayers-principles-of-multimedia-learning/)).

### On-screen text: hold time and words per screen

Count the hold from when the text stops moving.

| Text | Hold |
|---|---|
| First read of an animated label or headline | at least max(1.2 s, characters / 13) |
| Subtitle-style text that tracks narration | characters / 20 (Netflix English adult limit) |
| Last line of the film | at least 2 s (a common default) |

- 13 characters per second comes from accessible-film standards via [legibility.info](https://legibility.info/rules-for-text-in-videos);
  20 from the [Netflix style guide](https://partnerhelp.netflixstudios.com/hc/en-us/articles/217350977-English-USA-Timed-Text-Style-Guide);
  the [BBC](https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles) asks for about 0.3 s per word with a 1.2 s floor for short subtitles.
  Example: a 45-character label holds 3.5 s at 13 cps.
- Words per screen (single-vendor defaults, treat as soft): a headline up to about 6 words per line, body
  text up to about 12 words, lists up to 5 items of 4-5 words, emphasis on 1-2 words.
- Flashing text or transitions: no more than three flashes in any one second ([WCAG 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)).

### Scene length

One idea per scene; change the visual when the topic changes. Storyboard guides put a 60 s explainer at
6-10 scenes, so body scenes run about 5-10 s and hook scenes shorter. These are vendor conventions.
A demo shot of real UI may hold one framing for several seconds while the UI acts; contrast fast cuts
with slower holds.

### Structure templates

Pick the one that matches the brief and cut beats to fit the length. These are vendor templates over the
Google ABCD checklist (Attract, Brand, Connect, Direct).

Feature explainer (about 30 s baseline):
- 0-3 s the problem the feature solves
- 3-7 s the feature in one sentence
- 7-15 s before and after, the workflow
- 15-22 s demo in the product UI
- 22-30 s where to find it, one next step

Release announcement (five beats; a 15 s cut keeps hook, solution, one proof and the call to action):
1. Hook
2. Problem
3. Solution
4. Proof (a demo or a result)
5. Call to action

How it works (60-90 s): hook, problem, solution, how it works (one scene per step), proof, call to action.
Put the call to action after the context is set; TikTok links a closing card to higher recall.

## Aspect handling

16:9 is designed first. 9:16 and 1:1 are separate layout passes over the same scenes, timings and
narration; never scale-crop. Each pass is its own HyperFrames folder: `scenes/` for 16:9, `scenes-9x16/`
and `scenes-1x1/` for the others, with MP4s named `<slug>-9x16.mp4` and `<slug>-1x1.mp4`. Verify scans
every `scenes*/` folder for fonts, and an aspect MP4 only passes when its matching folder does. A centred 9:16 crop of a 16:9 frame keeps only about 32% of the width, so
side-by-side panels and wide UI are lost. Per aspect: stack panels vertically, zoom to the active UI
region, and enlarge type. Recommended assets are separate per aspect on [Google's guidance](https://support.google.com/google-ads/answer/9128498?hl=en).

Vertical safe zones on 1080x1920 vary by platform, and no platform publishes an organic spec. Use one
conservative envelope for critical text and faces: keep 288 px clear at the top, 672 px at the bottom,
120 px on the left and 192 px on the right. That leaves a safe box of 768 x 960 px (x 120-888, y 288-1248).
It is the largest margin per edge across Meta Reels, TikTok In-Feed and YouTube figures, read from
third-party measurements ([Solid Labs](https://www.solidlabs.com/social-safe-zones),
[AdCheckLab](https://adchecklab.com/articles/instagram-reels-safe-zone-template)). If the user delivers only
to Meta, a looser box is 950 x 979 px (14% top, 35% bottom, 6% each side). State which tier you used.

- Square 1:1: no platform figures found. Use the 5% title-safe inset, at most two caption lines, and
  larger type than 16:9.
- Captions in 9:16 and 1:1 are burned in; 16:9 gets an `.srt`. Caption layout lives in [audio.md](audio.md).
- Typical lengths by aspect from one vendor: 16:9 homepage 30-45 s, 1:1 20-30 s, 9:16 12-20 s. The
  storyboard keeps one timeline, so if the brief wants a shorter vertical cut, say so and cut scenes, not speed.

## 3D shots

Propose a 3D shot only when it adds something 2D cannot, and mark it in the storyboard.

1. Run `python3 "$SKILL_DIR/scripts/doctor.py" check --need 3d` and read the `blender` entry.
2. In the scene row, mark the scene `3D` and write Blender's status from that output: present with its
   version, or missing with the install command doctor printed.
3. Offer the user three choices at stop 1: strike the shot, install Blender, or approve a 2D fallback.
   Describe the fallback in the same row.
4. Never render a 3D shot the user has not seen in an approved storyboard. A still or sketch of the shot
   in the style frames is enough to approve. Authoring rules are in [3d.md](3d.md).

## Style frames

Style frames are stills of the key scenes (the hook, one demo scene, the closing card) rendered from the
scene kit, so the user judges the look before the build.

1. Write the key scenes as first drafts in `<project>/scenes/` using the kit, with the tokens inlined.
2. From `scenes/`, snapshot exact moments after motion settles:
   `python3 "$SKILL_DIR/scripts/hf.py" --project "<project>" -- snapshot --at 1.5,4.2`
3. Copy the PNGs from `.hyperframes/artifacts/snapshots/` into `<project>/frames-storyboard/` and
   link them from the storyboard.

These are previews for the user's approval. Snapshots can differ from the MP4 (fonts rendered correctly
in snapshots while the MP4 fell back to system fonts in a trial), so they never count as review. Real
review frames are decoded from the rendered MP4 later; see [review.md](review.md).

## The scene kit

The kit is what every scene composes from. It is locked when the user approves the storyboard. A long
video hands scenes to subagents that may use only the kit; see [long-form.md](long-form.md).

Write it to `<project>/kit/` and summarize it in the storyboard:

- Brand tokens: colors, font families and sizes per role (display, body, mono), spacing, radius. Keep the
  `:root` block as text that scenes paste inline. A linked stylesheet is not enough; see [hyperframes.md](hyperframes.md).
- Motion roles: a short named list, each with a duration and an ease, so no scene invents its own. Starting
  defaults, to adjust per brand (rationale in [motion.md](motion.md)):

  | Role | Duration | Ease |
  |---|---|---|
  | enter | 0.4 s | `expo.out` or `power3.out` |
  | exit | 0.25 s | `power2.in` |
  | emphasis | 0.3 s | `power2.inOut` |
  | transition | 0.6 s | `power2.inOut` |
  | stagger offset | 0.05-0.1 s between items | same ease as the item |

- Shared components: the pieces that repeat, as copy-ready HTML and CSS snippets (title card, label,
  UI frame for captured pages, highlight ring, cursor, caption line, end card), each using only kit tokens.
- Type scale: minimum sizes per aspect, from [motion.md](motion.md).

If the kit changes after approval, tell the user and re-approve; a changed kit invalidates scenes already built.

## Before you show it

- Each scene row has times, text, source and motion roles; scene times add up to the video length.
- Narration lines fit the word budget, and the first 5 s contain the hook, the product and two beats.
- Every on-screen text hold meets the table above.
- Aspects, narration state, 3D flags and any named cloud service are in the header and flags.
- The draft brand is shown beside it if this is the product's first video. The brand is saved with
  `brand save --confirm` only after approval; see [brand.md](brand.md).
