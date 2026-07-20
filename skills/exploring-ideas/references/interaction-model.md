# Interaction Model — Checkpoints, Steering & Co-creation

Full mechanics for the `--involve` dial. Read this on demand (progressive disclosure) when a run is at `--involve medium` or `high`, or when the user steers. At `--involve low` you do not need this file — the run is today's autonomous pipeline.

Everything here **steers or expands only**. No checkpoint, steering move, or co-creation action may produce a spec, locked decision, acceptance criteria, ranking, or declared winner. Convergence always routes to the `brainstorming` handoff (see [Gate-safety](#gate-safety) below). This is the HARD-GATE, restated for every surface this file adds.

## The `--involve` dial

`--involve` answers **how much the skill pauses to include you** — orthogonal to *emphasis* (what kind of work) and `--wild` (how far past the obvious).

| Level | Checkpoints | Co-creation | Steering |
|---|---|---|---|
| **low** | none (today's scoping + handoff only) | none | standing invite still honored |
| **medium** *(default)* | plan preview + idea-landscape | react / go-deeper / add-your-own at the idea gate | full vocabulary |
| **high** | medium + post-research + pre-save artifact review | + per-direction depth prompts | full vocabulary |

- **Default medium.** Set at invocation (`--involve high`; `lo`/`med`/`hi` aliases accepted) or adjusted mid-session: *"check in less"* drops a level, *"check in more"* raises one.
- **`low` is the regression guard.** It is *exactly* today's behavior — no new checkpoints, no co-creation prompt. A run at `low` must produce the same trace as the pre-`--involve` skill on the same prompt.
- **The dial moves frequency, never the bar.** No level relaxes the HARD-GATE, the insight-pairing quality gate, or factual accuracy. Higher involvement = more touchpoints, not lower standards.
- **Mid-run changes take effect for all subsequent phases.** Dropping to `low` mid-run disables further checkpoints for the rest of the session.

## Headless / non-interactive runs (invariant)

Before relying on any checkpoint, decide whether the run is interactive:

- **Best-effort detection.** If invoked as a subagent, in a pipeline, or otherwise without a live user to answer (no interactive dispatch context), treat the run as **headless**. Direct user invocation defaults to **medium** and is interactive.
- **When headless:** **auto-skip every active checkpoint and the co-creation prompt.** Behavior falls back to today's autonomous pipeline exactly. Do not block waiting for input that will never come.
- **Log only what was actually skipped.** If one or more checkpoints were skipped, add a **Ran headless** line to the artifact recording which were skipped and which defaults/decisions were taken in their place (see [Artifact logging](#artifact-logging)). Auto-skipping is never silent — but at `--involve low` there are no checkpoints, so a low+headless run logs nothing and stays byte-for-behavior identical to today (invariant 3).

This invariant outranks the dial: a `--involve high` run that is actually headless still skips its checkpoints and logs them.

## Checkpoints

A checkpoint **surfaces current state and invites input**. It is *not* a convergent approval gate — it never asks *"is this the answer?"*, only *"should I keep going this way, or redirect?"*. Keep each one short: a moment, not a document.

Every checkpoint closes with the **standing-steer line**:

> *"You can also redirect me anytime — I'll pick it up at the next phase boundary."*

### Checkpoint 1 — Plan preview *(medium+)*

After light scoping, **before any agent runs**. This is the primary defense against the "20 minutes in the wrong direction" failure.

Show, compactly:
- Detected **emphasis + intensity (`--wild`) + involve level**
- The decomposed **research facets** (sub-questions to be searched)
- The **ideation techniques** queued
- Rough **scope** — depth, number of research rounds

Invite: *go / adjust scope / add-drop a facet / change a dial.* Then proceed on "go" (or any green-light) and apply any adjustments first.

### Checkpoint 2 — Idea-landscape review *(medium+)* — the co-creation gate

After the first divergent ideation pass, **before challenge + synthesis**. Show the **N distinct directions**, each with its insight-pairing line and originating technique (plus research findings grouped by theme when the run is research-heavy). This is where [co-creation](#co-creation-at-the-idea-gate) happens.

### Checkpoint 3 — Post-research *(high only)*

After the research loop, **before ideation**:

> *"Here's what I found, and the gaps I see — redirect before I start ideating?"*

Show themed findings + open gaps. A steer here can add/drop facets or send research back for another round before ideation begins.

### Checkpoint 4 — Pre-save artifact review *(high only)*

After synthesis, **before auto-save**. Show the assembled exploration doc, accept edits, then save. Analogous to `brainstorming`'s spec-review gate — but the document stays an **exploration doc**, never a spec. Edits may refine framing, prune, or reorder; they may **not** introduce a winner, decisions, or build steps.

### Per-direction depth prompts *(high only)*

At `high`, when presenting directions (Checkpoint 2) and findings (Checkpoint 3), offer a short *"want me to go deeper on any of these before I move on?"* alongside the standing-steer line — making depth opt-in per direction rather than waiting for the user to volunteer it.

## Steering model

The skill recognizes a small, testable vocabulary. Steering is available **at checkpoints** and via the **standing invite** between them.

### Vocabulary

- **Direction** — `go deeper on X`, `drop Y`, `add angle Z`
- **Dials** — `dial it up` / `keep it grounded` → adjusts `--wild`; `check in more` / `check in less` → adjusts `--involve`
- **Scope** — `narrow to …`, `also explore …`

### Timing

- Input given **at a checkpoint** is acted on immediately.
- Input given **between checkpoints** is honored at the **next phase boundary**. State this honestly: parallel research batches dispatched in a single message cannot be halted mid-flight — the steer applies once that batch returns. Do not pretend mid-batch interruption is possible.

### Rewind

A steer that implies an **earlier phase** (e.g. *"actually, research the X angle"* once ideation has started) **loops back** to that phase and resumes forward from there.

- **Preserve prior outputs.** Nothing already produced is discarded — the new work adds to it. The existing flow already permits ideation→research loops; rewind generalizes that edge to user-initiated jumps.
- **Record a Branch note** in the artifact: which phase it looped back to, and why (see [Artifact logging](#artifact-logging)).

### Mid-run dial changes

Take effect for **all subsequent phases**. `dial it up` changes intensity for the remaining ideation; `check in less` drops the involve level (and so removes upcoming checkpoints); dropping to `low` disables further checkpoints entirely for the session.

## Co-creation at the idea gate

Runs at Checkpoint 2 (`medium+`). The user reacts to the surfaced directions and the skill re-ideates from their input.

### Surface

- **Terminal by default.** Present directions as a **numbered list**, each with its insight-pairing line + originating technique. Follow with a free-text invite:

  > *"Drop / go deeper / add your own — or say 'looks good'."*

  No rigid forced-choice prompt — exploration stays conversational. An empty or *"looks good"* response just continues to the challenge pass.

- **Visual Companion optional.** When the companion is active, render the directions as clickable **`<agent-option-set data-multiselect>`** cards. A multi-select set yields a single `selected[]`, so the browser carries exactly one signal — **go-deeper** (the directions to expand). Unselected ≠ dropped (keep is the default); **drop** and **add-your-own** come from terminal text, which stays primary. Selection events flow through the existing `events` JSONL channel. See `visual-companion.md` → *Idea-gate co-creation*. No new component model.

### Actions

- **React** — keep / drop a direction.
- **Go-deeper** — flag a direction to expand.
- **Add-your-own** — contribute a new direction in free text.

**No ranking or scoring.** Ranking is the specific move that would implicitly crown a winner and breach the gate — do not offer it, in the terminal or the browser.

### Re-ideate loop

After collecting reactions:

1. **Drop** killed directions.
2. **Expand** flagged ("go deeper") directions.
3. **Ideate fresh** around anything the user added.
4. **Run one more short divergent pass** to refill the quota (minus killed), still holding the **insight-pairing + REJECT quality gate**.
5. Proceed to the **challenge pass** with the revised landscape.

The quota and insight-pairing requirements from the [Divergent Ideation Engine](../SKILL.md#divergent-ideation-engine) are held throughout — co-creation changes *which* directions, never *whether* they must clear the bar.

## Gate-safety

Co-creation and checkpoints exist to broaden the option space, never to converge it.

- A checkpoint never asks *"which is best."*
- If the user signals convergence at any surface — *"this one wins, let's build it"*, *"write the spec for the 2nd"* — **do not** produce a spec, ranking, or decision inline. Offer the `brainstorming` handoff instead:

  > *"That's the build step — exploration stays open here. Want me to carry [direction] into `quirk:brainstorming` → an execution skill (which authors a tech spec when warranted, then plans in context)?"*

- This is the HARD-GATE. It holds at every checkpoint, every steer, and every co-creation action, at every involve level.

## Artifact logging

These additions to `exploration-artifact-template.md` are **optional and additive** — include a line only when the thing happened. They do not alter the NOT-a-spec banner, the no-winner rule, or insight-pairing.

| Line | When | What it records |
|---|---|---|
| **Steered** *(under What was explored)* | user redirected the run | one-line summary of the redirections |
| **Branches** | a rewind occurred | which phase it looped back to, and why |
| **Set aside (user)** *(under Findings / Idea landscape)* | user killed directions at the gate | the dropped directions, for honest provenance — not re-listed as live |
| **Ran headless** | run was non-interactive *and* a checkpoint was skipped (so never at `low`) | that checkpoints were auto-skipped and which would-be decisions/defaults were taken |
