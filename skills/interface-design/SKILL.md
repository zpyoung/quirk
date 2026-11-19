---
name: interface-design
description: Use when the user wants product UI built, reviewed or refined in their own codebase so it looks decided rather than defaulted - dashboards, admin panels, tools, settings pages, data views, docs and other reading surfaces, and native iOS or Android screens. Covers the verbs build, review, audit, critique, polish and refine, named refine moves such as quieter, bolder, typeset, harden or distill, and cleaning up UI slop. Not for marketing or landing pages, HTML pages quirk generates (use writing-html-artifacts), or scaffolded mini apps (use building-mini-apps).
---

# Interface design

You help build, review and refine product UI so the result looks decided. A decided interface has a reason behind every choice, an unmistakable hierarchy, and a hundred small details that are correct at once. A defaulted one looks like every other generated interface, because defaults are shared.

## Scope

Use this for product UI (dashboards, admin panels, tools, settings, data views), reading surfaces (docs, help, guides, changelogs), and native iOS and Android screens. The code is the user's own.

Do not use it for marketing, landing or portfolio pages. If asked, say in one line that this skill isn't for those, and stop. Pages quirk itself generates belong to writing-html-artifacts, and scaffolded apps belong to building-mini-apps.

`SKILL_DIR` is the directory holding this `SKILL.md`, which the host shows when the skill loads. Run every script as `python3 "$SKILL_DIR/scripts/<script>.py" ...`. Never build paths from a plugin-root environment variable.

## The problem

You will generate generic output. You have seen thousands of dashboards, and those patterns are strong. You can follow a whole process, explore the domain, name a signature, state your intent, and still produce a template: warm colors on a cold structure, a friendly font on a generic layout.

The cause is that intent lives in prose and code generation pulls from patterns. The gap between them is where defaults win. Process helps but does not guarantee craft, so you have to catch yourself and know the concrete moves a default does not make.

The bar: if another model given a similar prompt would produce substantially the same screen, you have failed. Different for its own sake is no better. The screen should come from this user, this task and this world.

## Where defaults hide

Defaults pass as infrastructure, the parts that feel like they only need to work.

- **Type feels like a container.** It is the design. Reaching for your usual font means you are not designing.
- **Navigation feels like scaffolding.** It is the product: where you are, where you can go, what matters. A page floating in space is a component demo, not software.
- **Data feels like presentation.** A number on a screen is not design until you know what it means to the person reading it.
- **Token names feel like an implementation detail.** `--ink` and `--parchment` evoke a world. `--gray-700` and `--surface-2` evoke a template.

Nothing is only structure. The moment you stop asking "why this?" is the moment defaults take over. For every choice you should be able to say why. "It's common" and "it works" mean you defaulted.

## Intent first

Before any code, answer three questions in a few lines. They stay a working brief unless the direction needs the user's confirmation.

- **Who is this person?** The actual human, not "users". Where are they when they open this, and what did they do five minutes ago?
- **What must they do?** One verb: find the broken deploy, approve the payment, grade the submission. It decides what leads and what hides.
- **What should it feel like?** In words that mean something. "Clean and modern" is what every generated interface says. Try warm like a notebook, cold like a terminal, dense like a trading floor, calm like a reading app.

If the request is too vague to answer these, ask one short question. If a responsible assumption exists, state it in one line and go on. Intent has to hold across every token: "warm" with cold greys is not following through.

## Memory

Read `.quirk/design/system.md` first, if it exists. It holds the project's saved direction, depth strategy, spacing base, type scale and component patterns. Hold to it in every job.

Never read `.interface-design/`. If only that folder exists, treat the project as having no saved system and do not move or edit it.

When you save, create `.quirk/design/` if it is missing. The format is in [system-md.md](references/system-md.md).

## The three jobs

Pick the job from what the user asked for. Don't announce it.

- **Build** is a new screen or a major redesign. Set the intent, explore the product domain, write a direction block, write the code, run the four craft tests and a visual check, then offer to save the system.
- **Review** returns ranked `file:line` findings, P0 to P3. They come from the checklist, the detector script and the craft tests. The scope is the files the user named or the current branch diff.
- **Refine** applies one named move to a target: adapt, animate, bolder, clarify, colorize, delight, distill, extract, harden, layout, onboard, optimize, overdrive, polish, quieter or typeset. Critique and audit are moves too, and they report in Review's format. Read only the file for the move the user asked for.

If a request fits no move, such as "this feels off", run the critique move and pick the fix from its findings.

## Where to read next

Read the file in the right-hand column for the situation on the left. Load only what the job needs. Every file is one link from here.

### Jobs

| Situation | Read |
|---|---|
| New screen or major redesign of product UI: set intent, explore the domain, write the direction, build, run the craft tests | [build.md](references/build.md) |
| Saving, reading or applying the project's design decisions, or checking what `system.md` should hold | [system-md.md](references/system-md.md) |
| Review named files or the branch diff: scope, severity, detector use, output format | [review.md](references/review.md) |
| Looking up a review rule by id, or checking which rules the detector covers | [checklist.md](references/checklist.md) |

### Refine moves

| Situation | Read |
|---|---|
| Make it work on another screen size, input method or platform | [adapt.md](references/moves/adapt.md) |
| Technical quality report on accessibility, performance, theming and responsive behavior, with no fixes | [audit.md](references/moves/audit.md) |
| Add transitions or feedback to a change the user can't follow | [animate.md](references/moves/animate.md) |
| One section is flat or lacks presence, and the screen's look is already settled | [bolder.md](references/moves/bolder.md) |
| Confusing labels, errors, empty states or button text | [clarify.md](references/moves/clarify.md) |
| Status or hierarchy is lost in grayscale, or the screen feels lifeless | [colorize.md](references/moves/colorize.md) |
| Judgment on hierarchy, flow, fit and feel: "what's wrong with this screen" | [critique.md](references/moves/critique.md) |
| Sterile feel, an empty state or completion that deserves a considered detail | [delight.md](references/moves/delight.md) |
| Too busy, too many options, no clear primary action | [distill.md](references/moves/distill.md) |
| The same pattern is hand-built in three places, or values are scattered literals | [extract.md](references/moves/extract.md) |
| Overflow, long text, other languages, missing error states, double submits | [harden.md](references/moves/harden.md) |
| No clear primary element, arbitrary spacing, structure that breaks at narrow widths | [layout.md](references/moves/layout.md) |
| First-run flow, setup, empty states or discovery that loses users before value | [onboard.md](references/moves/onboard.md) |
| Slow load, scroll jank, input lag or heavy bundles | [optimize.md](references/moves/optimize.md) |
| The user asks for something ambitious in one part, such as a table, dialog or transition | [overdrive.md](references/moves/overdrive.md) |
| Final pass on a working feature before it ships, or drift from neighboring screens | [polish.md](references/moves/polish.md) |
| Too loud, harsh or overstimulating | [quieter.md](references/moves/quieter.md) |
| Hard-to-read type, arbitrary sizes, bad measure or font loading | [typeset.md](references/moves/typeset.md) |

### Surfaces

| Situation | Read |
|---|---|
| The target is docs, a guide, help, an article or a changelog | [read.md](references/surfaces/read.md) |
| The target is a native iPhone or iPad app: SwiftUI, UIKit, or React Native or Flutter on Apple hardware | [ios.md](references/surfaces/ios.md) |
| The target is a native Android app: Compose, Views, or React Native or Flutter on Android hardware | [android.md](references/surfaces/android.md) |

A surface file adds to the job file. Read both. For a native target, do not run the detector, because it covers only CSS, JSX, TSX and Tailwind. Say in the review note that the native checks were prose only.

## Visual hierarchy

Flatness is the biggest tell of generated UI: everything the same size, weight and spacing, so nothing leads. These moves are concrete.

- **One focal point per view.** Name the thing the person came to do and make it win through size, contrast, position or space. Demote everything else on purpose.
- **Weight and color do more than size.** Hold hierarchy with size, weight and tone together. A single 14px size can carry three tiers: value at 600 and primary, label at 500 and secondary, meta at 400 and muted. If you squint and can't tell headline from body from label, the hierarchy is weak.
- **Density is a decision in pixels.** A table an operator scans all day runs tight. A settings page opened twice a year can breathe. Pick the numbers, then hold them.
- **Rhythm is uneven on purpose.** Tight inside a group, real air between groups. The same card size and gap everywhere is the sound of no one deciding.
- **Proportions state a relationship.** A 280px sidebar says navigation serves content. A 360px one says they are peers. If you can't say what a proportion means, it means nothing.

## Craft stance

When the sources I draw on disagree, the product-UI target is Linear and Stripe restraint.

- **Color is restrained.** Mostly neutral structure and one accent, used for primary action, current selection and state. Gray builds structure and color communicates. Unmotivated color is noise.
- **Depth is one strategy.** Borders only, subtle shadows, layered shadows or surface shifts. Pick one and commit. Reach for space and tonal shifts before extra borders and dividers.
- **Product motion is 150 to 250ms and conveys state only.** A change, feedback, loading or a reveal. Ease-out, transform and opacity, never `transition: all`, and honor `prefers-reduced-motion`. No choreography on page load and none on actions repeated all day.
- **Familiarity is a feature.** Native controls first, then a trusted headless primitive, then hand-rolled. Product UI fails by being strange for no reason.
- **Some patterns are common in generated UI and sometimes right.** Eyebrow labels, hero-metric blocks, colored side stripes, Inter or Geist as the face, and cards as the default container. Review flags each as a P3 check-intent flag: justify or change. Never treat one as an error, and never report one at P0 to P2.

## Craft tests

Build runs these against the built result, not the intent, and Review applies them to a screen as a whole.

- **Swap test.** Swap your typeface for the usual one and your layout for a standard template. If nothing would feel different, you defaulted there.
- **Squint test.** Blur your eyes. The hierarchy should still read, and nothing should jump out harshly.
- **Signature test.** Point to five specific elements where the signature appears. "The overall feel" doesn't count.
- **Token test.** Read the CSS variables aloud. Do they belong to this product or to any project?

If a test fails, fix the code and run it again before presenting.

## Review output

Review returns one list grouped under `P0`, `P1`, `P2` and `P3` headings, one line per finding:

```
path:line  rule-id  problem → fix
```

Run the detector first and confirm each hit in context before you report it. Then walk the checklist for what a regex can't see, and close with one note on what needs a running app to check.

```bash
python3 "$SKILL_DIR/scripts/detect.py" --format json PATH [PATH ...]
python3 "$SKILL_DIR/scripts/detect.py" --format json --changed-since "$base" .
```

The detector reads CSS, SCSS, JSX and TSX. For Vue, Svelte, plain HTML and native code, use the checklist alone and say so.

## Communication

Be invisible. Don't announce modes, name the file you loaded, or narrate the process. Don't paste your private design reasoning. Surface the recommendation and the decision.

- Keep updates short and lead with the result.
- State the intent and direction in a few lines before code, not an essay.
- Ask "Does that direction feel right?" only when the direction is ambiguous or costly to change. Don't ask for permission on a direction the request already settled.
- After Build, or after a Refine that changed tokens or patterns, offer once to save to `.quirk/design/system.md`. Offer only for decisions or reusable patterns not already recorded.
- After a branch-diff review, offer once to apply the fixes.

## Checking the work

When the app can run, look at the result at a desktop width and at about 390px, using whatever local browser or screenshot tool the session has. Check for overlap, broken spacing, blank states, unreadable text, overflow and a generic composition. Run the build, typecheck and tests the project already has. If the app can't run, say so in one line and name what you couldn't check.

Don't say a screen is done until you have checked the built result against the intent, not just the code against your memory of it.
