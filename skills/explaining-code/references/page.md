# Explainer page

The page is for a reader who hasn't opened the change or the design. It tells them what it does, what to weigh, and what to watch after it ships. You build it with quirk:writing-html-artifacts (`report` template, `explainer` layout). That skill owns the build, the static checks, browser verify and the delivery note; this file owns what goes in the page.

## Contents

- [Sections for a code change](#sections-for-a-code-change)
- [Sections for a design or plan](#sections-for-a-design-or-plan)
- [Components](#components)
- [Writing rules](#writing-rules)
- [Pre-delivery checklist](#pre-delivery-checklist)

## Sections for a code change

The `summary` slot holds the one-sentence summary from `facts.md` as the `q-lede`, with the key precondition. `main` opens with a `q-meta` line naming the PR, MR, branch or range and the head SHA, then these sections in order. Leave out a section that has nothing in `facts.md`; don't pad it.

| Section | What goes in it |
|---|---|
| What changed | The visible pieces, then one concrete line on the whole picture and a diagram with one node per change or service, each related PR or MR credited for its own diff. A hero screenshot of the new state, when there is one. |
| How it behaves | The worked example as a `q-flow` or `q-sequence` trace, one step per hop with the value at that step. |
| Decision worth weighing | The one decision, chosen next to not chosen, with the code in a `q-diff` and a `q-diff-note` on the line that carries it. |
| Walkthrough | Screenshots in the order a user meets them, one caption each, and the walkthrough video when there is one. UI changes only. |
| Tests | The scenarios covered, grouped by the question a reviewer would ask. |
| Monitoring | What the code emits, each with `file:line`, then the paths that emit nothing. Suggestions go in their own labelled paragraph. |
| Considerations | Rollout notes someone must act on. The flag, and who must not get it, goes here. |
| Sources | The last section: the change at its head SHA, each related change and the branch you read it on, and how screenshots were made. |

Pick the decision worth weighing before you write "What changed". The scope text is easier once you know what you want the reader to weigh.

## Sections for a design or plan

The `summary` slot says what will be possible once it ships, with real values, and says it's a proposal. `main` opens with a `q-meta` line naming the document, its date or revision, and the code SHA you checked it against.

| Section | What goes in it |
|---|---|
| The problem today | What happens now, cited to today's code with `file:line`. |
| What it proposes | The proposed shape as a diagram, with the existing parts and the new parts told apart by `kind`, and a legend. |
| How it would behave | The worked example as a `q-flow` or `q-sequence` trace, labelled proposed. |
| Decision worth weighing | The main choice against the alternatives the document considered, in a `q-compare`. |
| What it touches | The current files, endpoints and tables the design changes, each with `file:line`, and any data model change as a `q-schema`. |
| Open questions | What the document leaves open, and what reading the code raised. |
| Rollout and risks | Migration order, flags, and what to watch, labelled proposed. |
| Sources | The document and section anchors, and the SHA of the code you read. |

## Components

All of these are in the writing-html-artifacts component reference. Use them instead of hand-written layout.

- `q-flow` for service and data-flow diagrams. Put the worked example in its `traces`, so the reader steps through the values. Use `kind` to tell new from existing, and say which colour means what in the section text.
- `q-sequence` when the example is mostly calls between services rather than a pipeline.
- `q-diff` with `q-diff-note` for the code behind the decision worth weighing. Cut the diff down to the hunk that matters.
- `q-compare` for chosen against not chosen, and for a design's alternatives.
- `q-schema` for a data model or migration.
- `q-code` for a config line or command someone must copy (enabling the flag, running a migration).
- Screenshots: embed them as JPEG data URIs so the page stays one file, with real `width` and `height` on each `<img>` and alt text that says what the frame shows. The diagram components alone put the page past the size check's 2 MB warning, so that warning is expected; stay well under the 10 MB failure by dropping frames before lowering quality until text blurs.
- The walkthrough video goes beside the page as `walkthrough.mp4` and is referenced by that relative path in a `<video controls>`. The two files travel together, so say so in the delivery note. Verify fails with a console error if the MP4 isn't there yet, so copy it in before you verify.

## Writing rules

- Plain voice, the way you'd explain it at a teammate's desk. Short sentences next to longer ones.
- Concrete before abstract. "Waits 2, 4, then 8 seconds" beats "configurable exponential backoff".
- Open each section with its conclusion, then the evidence.
- Cut AI tells: "not X but Y", narrator signposts ("here's where it gets interesting"), punchy pairs like "no warning, no fallback", reflexive lists of three, "robust", "seamless", "leverage", "Furthermore".
- At most one em dash per roughly 200 words.
- No invented specifics. A number, name, file, line or change you haven't read doesn't go in. Write `[ASK: ...]` and ask.
- Spell out a term the first time. The reader may be on another team.

## Pre-delivery checklist

Run this after writing-html-artifacts' own verify passes, on the built file.

- [ ] **Claims match the code.** Reread every behaviour claim, `file:line`, metric name, flag name and related-change credit against the branch or SHA you cite.
- [ ] **Proposed is labelled.** On a design page, nothing proposed reads as though it ships today.
- [ ] **The trace runs.** Step through every `q-flow` or `q-sequence` trace in the browser; each step's value matches the worked example in `facts.md`.
- [ ] **Nothing unfilled.** No `[ASK: ...]` remains, and every suggestion is still labelled.
- [ ] **Outside readers.** If the user wants to share the page outside the team, it passes the [outside-reader filter](gather.md#outside-reader-filter).
