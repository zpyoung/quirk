# Videos

Two videos, one per reader, both from the same `facts.md`. quirk:making-videos builds each one and runs its own pipeline, stops and checks. This file is the brief you hand it: who the video is for, how long, what the script covers in what order, and what it must leave out. The timings are targets; the measured narration decides the real length.

## Contents

- [The brief](#the-brief)
- [Overview video](#overview-video)
- [Walkthrough video](#walkthrough-video)
- [Script rules](#script-rules)

## The brief

Give making-videos, for each video:

- the audience and the length (below)
- the path to `facts.md`, to use as its source list. Every script line must trace to a line there.
- the script structure for that video (below)
- the screenshots or app URL from gather, when there are any
- the leave-out list for that video

## Overview video

60 to 90 seconds, for anyone. It must pass the [outside-reader filter](gather.md#outside-reader-filter).

1. **The problem, concretely (0-10 s).** A real-sounding case of what goes wrong today.
2. **What it does, with example values (10-20 s).** The one-sentence summary.
3. **Using it (20-45 s).** The visible pieces in the order someone meets them, including the validation they'll hit.
4. **What changes (45-70 s).** The worked example traced end to end.
5. **Limits worth knowing (70-85 s).** Preconditions only, then one closing line that restates the benefit plainly.

For a design, it's the same structure with every behaviour described as planned.

## Walkthrough video

90 to 150 seconds, for reviewers.

1. **What it does (about a third).** The one-sentence summary, the flag if there is one, then the worked example. One line on related changes, each shown on screen, not spoken by number.
2. **What this change adds, or what the design proposes (about 40%).** For a UI change, the recording of the real flow with the new component ringed: one colour for new in this change, one for new elsewhere in the feature, and a dashed, quieter one for navigation, with a small legend. For a backend change or a design, the diagram building up with the worked example's values moving through it. Narrate the decision worth weighing. No line-by-line code.
3. **What to act on (about 20%).** Rollout guards, who must not get the flag, and what to watch after it ships, from the monitoring facts. Then an end card.

Leave out: PR, MR and issue numbers (never spoken or shown), test counts, a "what it doesn't do" list, and anything a reviewer reads faster in the diff. If `facts.md` doesn't say which pieces are new in this change rather than elsewhere, ask at stop 1 instead of guessing.

## Script rules

These apply to narration and to on-screen text.

- Say it the way an engineer would say it to a teammate: plain words, one idea per sentence, mixed sentence lengths.
- No narrator signposts ("let's dive in", "now the part users feel"), no teaser questions, no closing summary that repeats the video. Read the script aloud once and delete any line that only exists to sound like a narrator.
- Never narrate file names, function names, PR or MR numbers or issue keys. Show them on screen if a reviewer needs them.
- Write identifiers in their spoken form in the narration (from the spoken-forms section of `facts.md`), and keep the written form in captions and on screen.
- Prefer rephrasing over respelling an awkward word.
