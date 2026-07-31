# Tech spec: `writing-scannable-prose` skill

## Purpose

Turn the approved logic spec for the `writing-scannable-prose` skill into a build-ready contract: the exact files to create, what belongs in each and what must not, the frontmatter verbatim, the 28-check representation, the revision protocol as numbered steps, and the acceptance criteria.

**Status:** Draft — ready for review · **Logic spec:** [logic.md](logic.md)

## Decisions locked

Every behavioral decision is locked in [logic.md's Decisions locked](logic.md#decisions-locked) and is **inherited, not restated here** — duplicating it would create two sources of truth that drift. This document locks only implementation-level choices, and those live in [Always / Ask / Never](#always--ask--never) below.

One conflict-resolution rule applies: if implementation finds a locked decision infeasible, the fix is a dated Amendments entry in logic.md first, never a silent divergence in this document or in the skill.

This document owns *where* and *what must hold*. It does not restate the conceptual model, the rationale for any locked decision, or the rule set's substance — see [logic.md](logic.md) for all of that. Every section below back-links the logic-spec anchor that justifies it.

## Architecture

Three new files under a new skill directory, one new test module, no changes to any existing skill's behavior:

```
skills/writing-scannable-prose/
  SKILL.md               # hub: gate, model, all 28 checks by group+tag, blocklist,
                          # escalation protocol, deference rules — created
  worked-examples.md     # one before/after per check, grouped F/A/B/C/D/E — created
  evidence-and-limits.md # grounded-vs-precautionary status, falsification notes,
                          # pointer to the two exploration docs — created
tests/
  test_writing_scannable_prose_skill.py  # created
```

No library or runtime dependency is introduced — this is a Markdown skill, loaded and interpreted by the agent, not executed. The only "technology" in play is the repo's existing skill-loading mechanism (frontmatter `name`/`description` triggers activation, per [skills/writing-skills/SKILL.md](../../../../skills/writing-skills/SKILL.md)) and pytest for the test module.

Two files already exist and are **not part of this skill's deliverable**, but are load-bearing raw material for it — see "Existing fixture to reuse" below.

Back-links: logic.md's [File layout](logic.md#file-layout).

## Existing fixture to reuse

`docs/quirk/specs/2026-07-29-writing-scannable-prose/verbose_example.md` and `docs/quirk/specs/2026-07-29-writing-scannable-prose/scannable_example.md` already exist and are committed (added in `671881d docs(spec): add rule group F (section grain) + worked example`). They are a real before/after pair of a synthetic MR description — the same document that exposed the residue-stub gap group F now closes (see logic.md's Amendments, 2026-07-30 entry). `verbose_example.md` is the "before" (contains the review-round-history and process-narrative sections F4 routes away, and the residue-stub failure mode named in the amendment); `scannable_example.md` is the "after."

**Recommended use, not locked by the logic spec:** link `worked-examples.md`'s F-group entries (F1–F4) to this pair by relative path rather than duplicating the MR text inline — the pair is long (verbose_example.md is 217 lines, scannable_example.md 172), and duplicating it invites the two copies to drift. A reasonable implementer could instead excerpt short before/after snippets inline for consistency with the other 24 checks' shorter examples; either satisfies the logic spec, which does not fix this. This tech spec recommends linking.

**DO-NOT-CHANGE:** neither file may be edited, moved, or renamed by this work — they are the fixture the amendment log's residue-stub finding depends on, and rewriting them to "fix" the residue-stub example would destroy the evidence the F-group check exists to catch.

## Code references

Nothing pre-existing is modified. What gets created, exactly:

- `skills/writing-scannable-prose/SKILL.md` — new file, frontmatter + body per "The `SKILL.md` template" below.
- `skills/writing-scannable-prose/worked-examples.md` — new file, structure per "File manifest" below.
- `skills/writing-scannable-prose/evidence-and-limits.md` — new file, structure per "File manifest" below.
- `tests/test_writing_scannable_prose_skill.py` — new file, per "Test contract" below. Naming follows the repo's per-skill test-file precedent (`tests/test_adhd_skill.py`, both reference-file constants and per-test docstrings), not the single generic `tests/test_skill.py` (that name is already claimed by `typed-artifacts` and is a one-off, not a convention — confirmed by grep: it is the only test module using the bare name).
- `README.md:9` — the line `**21 skills** under \`skills/\` covering …` must become `**22 skills**`. This is not optional busywork: `tests/test_adhd_skill.py::test_readme_skill_count_matches_skill_directory` already asserts the digit in that line equals the count of `skills/*/SKILL.md` files, and it will fail the moment the new directory lands with no README edit. No new test is needed for this — the existing one already covers it.
- `.claude-plugin/plugin.json` — **no change required, re-derived empirically rather than from a specific line.** Correction from an earlier draft of this spec: `.claude-plugin/plugin.json:13` is not a directory-path declaration — it is the string `"skills"` inside the `keywords` array (line 12 opens `"keywords": [`), i.e. the first of sixteen freeform marketplace-search tags. The file contains no field that enumerates or paths to individual skills at all. This repo's own files don't state the discovery mechanism explicitly either (checked: no line in `README.md`, `.claude-plugin/marketplace.json`, or `skills/using-quirk/SKILL.md` documents it for Claude Code specifically — `using-quirk/SKILL.md` states auto-discovery only for Copilot CLI, "Skills are auto-discovered from installed plugins"), so the exact mechanism is a platform-level convention external to what this repo declares, not something this spec can cite a repo line for. What *is* verifiable in-repo: of the 21 existing skill directories, only 2 (`adhd`, `typed-artifacts`) happen to appear as `keywords` entries, and the other 19 — including `writing-skills`, `writing-plans`, `writing-tech-spec`, `systematic-debugging`, `test-driven-development` — are absent from both `.claude-plugin/plugin.json` and `marketplace.json` entirely, yet all load and run (this very tech spec was authored using several of the absent ones). That precedent is the basis for the conclusion: a 22nd skill needs no `.claude-plugin/plugin.json` entry to be discoverable, because most of the current 21 have none. Adding `keywords` for `writing-scannable-prose` remains available as optional discoverability polish, not a requirement.

Back-links: logic.md's [Rule inventory](logic.md#rule-inventory), [File layout](logic.md#file-layout).

## The frontmatter, verbatim

```yaml
---
name: writing-scannable-prose
description: Use when writing or revising a human-facing technical document — README, guide, ADR, PR description, changelog — or when asked to tighten, shorten, or declutter one ("tighten this", "too long", "hard to scan", "make this scannable"). Separates what the reader's decision depends on from detail they do not want, cutting whole sections that earn no keep; then treats every remaining cut as a dependency problem, so compression removes real bulk without orphaning the claims it leaves behind.
---
```

`name`: 23 characters, matches the directory name `writing-scannable-prose`, lowercase/hyphens only. `description`: 490 characters — under the repo's stated ≤1024 hard limit and under its "≤500 if possible" preference. Verify both with a length check rather than trusting these counts, which are perishable facts about a string in this document (E1).

**Both halves of the pass are named, deliberately.** An earlier draft of this description covered only the dependency/orphaning half (groups A–E). That under-sells group F, which is the section-grain work the logic spec's 2026-07-30 amendments added and which is the highest-value part of the pass on a real document — and it would have cost activation: "does this README need all these sections?" matches "detail they do not want" and matches nothing in an orphaning-only description.

**Deliberate omission, not an oversight:** the description names no genre this skill does *not* cover and contains none of the words "voice," "tone," "de-AI," or "humanize." Logic spec's [Activation](logic.md#activation) section requires avoiding that vocabulary so this skill and `writing-like-a-human` can co-fire on a docs task without competing on the *same* trigger words; an explicit "not for voice/tone" exclusion clause would reintroduce exactly the vocabulary being avoided. Differentiation instead comes entirely from the positive trigger list (document genres + revision phrasings), which a pure voice/tone request ("make this sound less corporate") does not match.

Back-links: logic.md's [Activation](logic.md#activation).

## SKILL.md section-by-section outline

Target: **~1,650 words total, under 350 lines** for SKILL.md's body (frontmatter excluded from both counts). This is deliberately past the "frequently-loaded leaf skill" targets in `skills/writing-skills/SKILL.md` — this is a technique skill loaded only when a docs task is active, comparable in shape to `skills/systematic-debugging/SKILL.md` (1,504 words) and `skills/writing-tech-spec/SKILL.md` (1,814 words), not to an always-on hub. Verify with `wc -w skills/writing-scannable-prose/SKILL.md` against this target at commit time.

| Section | Content | Word budget |
|---|---|---|
| Frontmatter | Verbatim block above | — (not counted) |
| Overview | Dependency-checker framing, orphaning-vs-verbosity, two-reader model, gate (fires on claims/reasoning/procedure, not line count) | 130 |
| Authoring inputs | The 2-row table: reader+decision → F1/F2/F4; procedural-vs-explanatory → A4. States mode is *not* an authoring input | 70 |
| Revision protocol | The two-pass procedure — see "Revision protocol as executable procedure" below for its exact shape, including the F1-undecided fail-safe (F2 skips, sections default to keep) and the passage-grain procedural/explanatory classification A4 consumes | 210 |
| Escalation modes | Blocking (F2 only) vs. non-blocking (A–E), one short table, the reversibility justification in one sentence | 90 |
| Group F table + F4 category table | 4 rows + the 5-row category→destination table | 190 |
| Group A table | 6 rows | 130 |
| Group B table | 5 rows | 110 |
| Group C table | 4 rows | 90 |
| Group D table | 6 rows | 120 |
| Group E table | 3 rows | 60 |
| Do-not-cite blocklist | Inline, 5 items, one line each | 70 |
| Falsification notes | 4 precautionary rules (A4, B1, B3, C4), one line each pointing to `evidence-and-limits.md` for the full note | 60 |
| Deference and scope | Template wins on structure, explicit user request wins outright, applies to whole document not just new text | 100 |
| Skill applies to itself | One short paragraph + license to deviate | 40 |
| Report shape | The revision-report shape, see below | 90 |
| Real-user gap | One short paragraph | 40 |
| Links out | Pointers to `worked-examples.md` and `evidence-and-limits.md` | 20 |
| **Total** | | **~1,620** |

Everything longer than the budget above routes to a reference file, never inline — in particular, per-check worked examples and the grounded/precautionary evidence table are **reference-file content by construction**, not a SKILL.md section; SKILL.md states the tag and one line of falsification note at most.

Back-links: logic.md's [Data flow](logic.md#data-flow), [Rule inventory](logic.md#rule-inventory), [Also inline in SKILL.md](logic.md#rule-inventory) (subsection under Rule inventory).

## Representing the 28 checks

**Shape:** one Markdown table per group (six tables total: F, A, B, C, D, E), each under its own `###` heading matching the logic spec's group titles verbatim (e.g. `### F — Does this section belong?`). Columns: `ID | Check | Tag`. F4's category→destination table is a second, separate table immediately following the F group table (not a 4th column on the F table — the categories apply only to F4, cramming them into every F-group row would misstate scope).

**ID scheme:** `F1`–`F4`, `A1`–`A6`, `B1`–`B5`, `C1`–`C4`, `D1`–`D6`, `E1`–`E3` — verbatim from logic.md's Rule inventory, unchanged. Each ID appears as the literal first cell of its table row, e.g. `| F1 | **Name the reader...** | \`judg\` |`. This makes every ID a plain substring in SKILL.md's raw text — greppable with `grep -F 'F1'` or a `\bF1\b` regex, which is what the test contract below relies on.

**Tag rendering:** the tag column holds one of `` `mech` ``, `` `judg` ``, `` `prin` `` in backticks — visually distinct from prose and, combined with the ID column, gives a test three independent signals to check per row (ID present, tag present, tag is one of the three valid values) without needing to parse table structure.

**Ordering:** Group F's heading and table physically precede Group A's in the document — this is what makes "F runs first" a property of the artifact itself, checkable by comparing string offsets (`body.index("### F —") < body.index("### A —")`), not just a claim in prose.

Back-links: logic.md's [Rule inventory](logic.md#rule-inventory), [Structure by topic, enforcement by tag](logic.md#structure-by-topic-enforcement-by-tag) (subsection under Key decisions and rationale).

## Revision protocol as executable procedure

This is the literal step sequence SKILL.md's "Revision protocol" section instructs the agent to run — write it in SKILL.md as numbered steps, not prose paragraphs, so it is followed rather than summarized:

1. **Derive F1's line.** Check sibling artifacts of the same genre, the project template if one exists, and whether the content already lives somewhere canonical. State the result as one visible line: `Reader: <who> — Decision: <what they do next>`. If no repo signal resolves it, say so explicitly rather than guessing silently.
2. **Run F2 against every section**, using F1's line as the test: does this section's absence change the named decision? Mark each section keep/remove. **If step 1 could not derive F1's line, F2 does not run at all: every section defaults to keep.** This is the fail-safe direction, not an arbitrary tiebreak — F2 removal is the one edit in this whole protocol that a report cannot walk back (per logic.md's "Removal is the one edit that gets a checkpoint"), so removing a section against a premise nobody stated is strictly worse than removing nothing. Name the undecided F1 line in the report as a non-blocking escalation (see "Report shape") so the user can supply it and re-run F2 later. This does not add a second blocking point: logic.md's escalation-modes section locks exactly one blocking case — F2 removals proposed for an answer — and halting the entire pass here to demand an F1 line would create a second, which the locked design does not have.
3. **For every section marked remove, run F3**: name where each load-bearing item inside it re-homes. A section with an item that has no destination is not yet ready to propose — find the destination or reclassify the item as not load-bearing.
4. **Emit the removal proposal** — see "Removal proposal shape" below — as one batch, covering every section marked remove in steps 2–3 together. **Stop and wait for the user's answer before proceeding to step 5.** This is the one blocking point in the whole protocol. (If step 2 produced no removals — either because every section passed F2, or because F1 could not be derived — this step emits nothing and the pass proceeds straight to step 5.)
5. **Run F4** on every surviving section: route author-facing detail (per the category table) to its named destination; leave a deliberately-not-made decision in place.
6. **Run groups A–E** on the surviving, F4-routed content. Before applying A4 to any given passage, classify that passage procedural (steps executed) or explanatory (reasoning believed) — this is the second authoring-table input (logic.md's Data flow), made at **passage grain only**, never at document or section grain, and consumed by A4 alone. When the authoring phase already set this for a freshly-drafted passage, reuse that call; for a passage entering the pass in revision-only mode — the common case, since the authoring phase never ran against an existing draft — classify it in place, immediately before A4 fires on it, so A4 never consumes a classification the procedure itself never produced. No step in this group pauses for a reply. Where a specific judgment call — including this classification, when genuinely ambiguous — cannot be self-verified, apply the edit provisionally and add one line to the report (see "Report shape") naming the call and enough detail to reverse it.
7. **Emit the revision report** — see "Report shape" below — covering everything steps 1–6 changed and why, including the non-blocking escalations from steps 2 and 6.

**Removal proposal shape** (step 4's output):

```
## Proposed section removals
| Section | Why it fails F2 (against the Reader/Decision line) | Load-bearing items | Destination |
|---|---|---|---|
```

One row per section marked for removal. The `Load-bearing items` / `Destination` columns are F3's output attached to F2's proposal — this is what stops a removal proposal from being approved without also committing to where its survivors land. Empty (no rows) whenever step 2 found nothing to remove, including the F1-undecided case — an empty proposal is not itself the F1 escalation; that is named separately in the report.

**Report shape** (step 7's output):

```
## Revision report
- Removed: <section> — <one-line F2 reason>. Moved: <item> → <destination> (repeat per item)
- Routed (F4): <item> — <category> → <destination>
- Changed (A–E): <check ID> — <what changed> — <why>
- Escalated (non-blocking, F1 undecided): <repo signals checked> — <why no reader/decision line could be derived> — F2 skipped, every section kept
- Escalated (non-blocking, A–E only): <check ID> — <the call> — <how to reverse it>
```

Not a checklist transcript (logic spec is explicit that it must not read as one) — each line names a concrete edit and its reason, omitted entirely for checks that fired with no edit to report.

Back-links: logic.md's [Data flow](logic.md#data-flow), [Escalation has two modes, and only one of them blocks](logic.md#escalation-has-two-modes-and-only-one-of-them-blocks), [Section grain is a distinct unit, and it comes first](logic.md#section-grain-is-a-distinct-unit-and-it-comes-first), [Removal is the one edit that gets a checkpoint](logic.md#removal-is-the-one-edit-that-gets-a-checkpoint).

## Contracts & interfaces

This is a Markdown skill with no function signatures, but it has one behavioral contract worth stating precisely, since planning and review will check against it:

**CONTRACT:** (procedural, not code) the revision pass, run against any document:
- Preconditions: a document containing claims, reasoning, or procedure (the Gate in logic.md's Behavior and scenarios); an explicit user request for expansiveness on some part of the document, if any, is known before the pass starts.
- Postconditions: every section either passed F2, was proposed for removal with F3 re-homing named, or defaulted to keep because F1 could not be derived; every surviving section passed F4 routing; groups A–E ran over the surviving, routed content, with every A4-governed passage classified procedural or explanatory immediately before A4 fired on it; a report was produced.
- Invariants: F2 removals are never performed unasked; F2 never removes a section when F1's line could not be derived (fail-safe default: keep); A–E never pauses for a reply; A4 never runs against a passage with no procedural/explanatory classification; no qualifier, scope condition, sample size, or exception attached to a surviving claim is removed (A2); no numeric threshold is introduced anywhere in the output document by this skill's own suggestions.
- Error/edge behavior: if F1 cannot be derived from any repo signal, the pass states that explicitly, skips F2 entirely (no section is removed on an underived premise), and names the gap as a non-blocking escalation rather than halting the whole pass or fabricating a reader/decision line; if the user's explicit request conflicts with a cut, the request wins and the skill states which checks it still applied (structure, orphan checks, linear channel) per logic.md's deference scenario.

Back-links: logic.md's [Behavior and scenarios](logic.md#behavior-and-scenarios), [Key decisions and rationale](logic.md#key-decisions-and-rationale).

## Data models / schemas

None — no structured data interchange, no API, no persisted schema. The only "shapes" in this skill are the two Markdown table layouts above (rule tables, removal proposal, revision report), which are documentation conventions, not data contracts consumed by other code.

## File manifest

| File | Belongs in it | Must NOT be in it |
|---|---|---|
| `SKILL.md` | Gate; two-reader model; authoring inputs; the full two-pass protocol as executable steps; all 28 checks by group+tag in table form; F4's category table; the 5-item do-not-cite blocklist (inline, per logic.md's rationale that a reflex needs to be caught before a link can be followed); one-line falsification pointers; escalation modes; removal-proposal and report shapes; deference/scope rules; the real-user-gap paragraph; "skill applies to itself" note | Per-check before/after examples (→ `worked-examples.md`); the full grounded-vs-precautionary evidence table and citation list (→ `evidence-and-limits.md`); anything reproducing the two exploration documents' research narrative |
| `worked-examples.md` | One before/after pair per check ID, 28 total, grouped under F/A/B/C/D/E headings matching SKILL.md's groups; each example short enough to scan (a few lines in, a few lines out, one line naming what changed) | Rule definitions or tags (SKILL.md owns those — an example illustrates, it doesn't redefine); evidence or citations (→ `evidence-and-limits.md`) |
| `evidence-and-limits.md` | Per-rule grounded/precautionary status; the four falsification notes in full (A4, B1, B3, C4); a single pointer to both exploration documents at `docs/quirk/explorations/2026-07-29-scannable-prose.md` and `docs/quirk/explorations/2026-07-29-scannable-prose-mechanisms.md`; the real-user-gap statement in full, if longer than SKILL.md's one-paragraph summary warrants | Inline citations scattered through SKILL.md (logic.md's locked decision: "one pointer to the exploration as the citation layer; no inline sources"); new research not already in the two exploration docs |
| `tests/test_writing_scannable_prose_skill.py` | Structural assertions only — see Test contract below | Behavioral assertions about what the agent does when it loads the skill (untestable by a static-file check; covered instead by the type-appropriate technique validation in logic.md's Validation section, run manually) |

Progressive disclosure check: SKILL.md links to both reference files with plain Markdown links (`[worked-examples.md](worked-examples.md)`, `[evidence-and-limits.md](evidence-and-limits.md)`), never `@`-force-loaded, consistent with `skills/writing-skills/SKILL.md`'s "Force-Loaded Cross-References" anti-pattern.

Back-links: logic.md's [File layout](logic.md#file-layout), [Also inline in SKILL.md](logic.md#rule-inventory).

## DO-NOT-CHANGE fences

- **`docs/quirk/specs/2026-07-29-writing-scannable-prose/logic.md`** — fenced because it is the approved source of truth this tech spec was authored from; any conflict discovered gets resolved via a dated Amendments entry there first, never a silent edit here or in the skill (per the writing-tech-spec rubric's feasibility-escalation rule).
- **`docs/quirk/specs/2026-07-29-writing-scannable-prose/verbose_example.md` and `scannable_example.md`** — fenced because they are the residue-stub validation fixture the 2026-07-30 amendment log entry depends on; see "Existing fixture to reuse" above.
- **`docs/quirk/explorations/2026-07-29-scannable-prose.md` and `2026-07-29-scannable-prose-mechanisms.md`** — fenced because they are the cited evidence layer for every locked decision in logic.md; editing them would silently invalidate citations the skill and its `evidence-and-limits.md` point at.
- **`tests/test_skill.py`, `tests/test_adhd_skill.py`, and every other existing test module** — fenced from this work; the new test module is additive only. (The one exception is *reading*, not editing: `test_readme_skill_count_matches_skill_directory` inside `test_adhd_skill.py` already covers the README count — see Code references — and must be left as-is, satisfied by editing `README.md`, not by editing the test.)
- **`.claude-plugin/plugin.json`** — no edit required (see Code references); if an implementer chooses to add discoverability keywords, that is additive-only and must not remove or reorder existing keywords.

## Always / Ask / Never

**Always**
- Author the frontmatter exactly as given in "The frontmatter, verbatim" above.
- Keep the check ID scheme (`F1`–`F4`, `A1`–`A6`, `B1`–`B5`, `C1`–`C4`, `D1`–`D6`, `E1`–`E3`) byte-identical to logic.md's Rule inventory — a renumbering breaks the test contract's greppability and the cross-reference from `worked-examples.md`.
- Place Group F's heading and table before Group A's in SKILL.md's actual document order.
- Update `README.md`'s skill count to `22`.
- Link to `worked-examples.md` and `evidence-and-limits.md`; never inline their content wholesale.

**Ask** (implementer's judgment call, flag the choice made in the PR/commit rather than silently picking one)
- Whether `worked-examples.md`'s F-group entries link to the existing `verbose_example.md`/`scannable_example.md` pair or excerpt short snippets inline (this spec recommends linking — see "Existing fixture to reuse").
- Exact prose wording within each budgeted section in the outline table, so long as the word budget and required content are both met.
- Whether to add `.claude-plugin/plugin.json` keywords for discoverability (optional, additive-only).

**Never**
- Never let any check outside F2 pause the pass for a reply (logic.md's locked escalation-modes rule).
- Never perform an F2 removal without proposing it first.
- Never introduce a numeric threshold anywhere in SKILL.md's own rule text (a locked decision with zero exceptions) — this is not mechanically enforceable by the automated test contract (see "Gap" below) and must be caught by a manual read before commit.
- Never gate anything on a readability score (E3) — including, reflexively, this document's own word-count targets, which are a token-budget device for the skill's authors, not a scannability metric applied to reader-facing prose.
- Never force-load a reference file with `@` syntax.

Back-links: logic.md's [Decisions locked](logic.md#decisions-locked).

## Cross-cutting

- **Security:** none beyond the repo's standard skill-trust model — a loaded skill steers the agent's behavior on the document it's editing, and this skill claims no elevated tool access. See `skills/writing-skills/SKILL.md`'s "Security & trust" section for the general model; nothing here adds to it.
- **Observability:** none — no runtime telemetry, no logs. The "report" the pass produces (see "Report shape" above) is the closest analogue, and it exists specifically so a run is visibly either performed or skipped, per logic.md's Data flow section.
- **Data migration:** none — no persisted state changes shape.
- **Rollback:** delete `skills/writing-scannable-prose/`, delete `tests/test_writing_scannable_prose_skill.py`, and revert `README.md:9`'s count back to `21`. No other file is touched by this work, so rollback is a plain revert of the commit(s) that add these paths.

## Testing strategy

**Test file:** `tests/test_writing_scannable_prose_skill.py`, mirroring `tests/test_adhd_skill.py`'s shape (module-level `REPO_ROOT`/`SKILL_PATH` constants, one `re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)` frontmatter parse per test, numbered docstrings).

**What it must cover** (never the test bodies themselves — function names and the assertion each makes only):

| Test function | Assertion |
|---|---|
| `test_skill_has_valid_frontmatter` | YAML frontmatter block exists; `name` and `description` fields both present |
| `test_skill_name_matches_directory` | Frontmatter `name` equals `writing-scannable-prose`, matching the parent directory name |
| `test_skill_description_has_trigger_phrases` | Description contains each of: `README`, `guide`, `ADR`, `PR description`, `changelog`, `tighten this`, `too long`, `hard to scan`, `make this scannable` |
| `test_skill_description_avoids_voice_tone_vocabulary` | Description does NOT contain (case-insensitive) `voice`, `tone`, `de-ai`, `humanize` — mirrors `test_adhd_skill.py`'s `test_adhd_skill_routing_guard` pattern, guarding against the collision the logic spec's Activation section calls out |
| `test_skill_blocklist_entries_present` | Body contains each of the 5 do-not-cite items (the 30%-bold maximum, "25% faster with bullets," 7±2 as a list cap, "30% faster scanning," the F-pattern as a design target) — matched on a short distinguishing substring per item, not exact prose |
| `test_skill_all_28_check_ids_present` | Body contains a `\bID\b`-matching occurrence of every one of the 28 IDs: `F1, F2, F3, F4, A1, A2, A3, A4, A5, A6, B1, B2, B3, B4, B5, C1, C2, C3, C4, D1, D2, D3, D4, D5, D6, E1, E2, E3` |
| `test_skill_group_f_ids_explicitly_present` | Explicit, separate assertion (not folded into the loop above) that `F1`, `F2`, `F3`, and `F4` are each present — this is the regression the logic spec's own amendment log names: a stale 24-check contract would otherwise let group F silently disappear from a future edit while the loop-based 28-count test above still (wrongly) passes if some other check were duplicated |
| `test_skill_group_f_precedes_group_a` | `body.index("### F —") < body.index("### A —")` (or equivalent heading-based ordering check) |
| `test_skill_links_to_reference_files_not_forced` | Body contains `[worked-examples.md](worked-examples.md)` and `[evidence-and-limits.md](evidence-and-limits.md)` as literal Markdown links; body does NOT contain `@worked-examples.md` or `@evidence-and-limits.md` |
| `test_reference_files_exist` | `skills/writing-scannable-prose/worked-examples.md` and `.../evidence-and-limits.md` both exist and are non-empty |
| `test_readme_skill_count_updated` | Not a new test — already covered by `tests/test_adhd_skill.py::test_readme_skill_count_matches_skill_directory`; run the existing suite as part of acceptance, don't duplicate the assertion here |

**Acceptance bar for the type ("technique," per logic.md's Validation section):** run `pytest tests/test_writing_scannable_prose_skill.py tests/test_adhd_skill.py -v` — all pass. Then apply the fresh-scenario check named in logic.md's Validation section: run the revision pass against a real, not-written-under-the-skill document in this repo — `docs/quirk/specs/2026-07-29-writing-scannable-prose/verbose_example.md` is the ready-made candidate, since it is exactly that document — confirm F2 correctly proposes removing its process-narrative sections with F3 re-homing named, confirm the checkpoint blocks before A–E, and confirm the resulting document does not regress to the residue-stub failure the amendment log describes. This manual pass is not itself a pytest test; it is the technique-type validation the logic spec requires, run once before commit and recorded in the commit message or PR description.

**Not covered by the automated test contract, by construction:** whether the skill's *body* is actually followed when loaded (an execution-axis question, per `skills/writing-skills/SKILL.md`'s activation/execution split) and whether `worked-examples.md` truly has all 28 entries (no test asserts this — it is a manual completeness check at commit time, listed here so it isn't silently skipped).

Back-links: logic.md's [File layout](logic.md#file-layout) (test-module paragraph), [Validation](logic.md#validation).

## Activation test plan

Concrete prompts, run manually (or via a subagent) against the finished skill and observed for trigger/no-trigger, per `skills/writing-skills/SKILL.md`'s activation-testing guidance:

**Should trigger:**
1. "This README's gotten really long, can you tighten it up?"
2. "Draft an ADR for the caching decision — keep it scannable."
3. "This PR description is a wall of text, can you make it easier to scan?"
4. "Write the changelog entry for this release."
5. "This guide is hard to scan, there's too much going on in each paragraph."

**Should NOT trigger:**
1. "Make this paragraph sound less like an AI wrote it" — pure voice/de-AI request, `writing-like-a-human`'s territory, no document-genre or revision-phrasing match.
2. "Can you make the tone of this email warmer?" — pure tone request, same reasoning.
3. "Fix the bug where the login button doesn't respond on mobile." — no document artifact in play at all.
4. "Refactor this function to reduce cyclomatic complexity." — code refactor, not a prose-document task.

Back-links: logic.md's [Activation](logic.md#activation).

## Non-goals

Restated from logic.md's own [Scope and non-goals](logic.md#scope-and-non-goals) only insofar as they bound this tech spec's file manifest (full rationale stays in logic.md, not duplicated here):

- No code, script, or tool is created — this is a pure-Markdown skill.
- No changes to `writing-like-a-human` or any other existing skill.
- No CI wiring beyond the one new pytest module — this skill's "acceptance" is a technique-type manual validation pass, not a CI gate (logic.md is explicit that no readability score, and by extension no automated prose-quality gate, is ever a target).
- No numeric-threshold tooling of any kind (linter, word-count gate, bold-density checker) — the logic spec's whole premise is that this domain ships no defensible numbers; building an enforcement tool would smuggle one back in through the tooling layer.
- This tech spec does not re-derive or re-litigate any locked decision in logic.md's [Decisions locked](logic.md#decisions-locked) section.

## Gaps: what this tech spec cannot resolve, and why

**1. The `writing-like-a-human` skill does not exist anywhere in this repository.** The logic spec's Activation section and its rationale for avoiding voice/tone/de-AI/humanize vocabulary both assume a sibling `quirk:writing-like-a-human` skill that co-fires and must not collide with this one. A repo-wide grep (`grep -rln "writing-like-a-human" --include="*.md" --include="*.json" .`, run outside this spec's own directory) returns nothing — no `skills/writing-like-a-human/` directory, no reference to it in `.claude-plugin/plugin.json`, no mention anywhere else in the codebase. A skill with that name *is* available to the agent in this session, but as an unprefixed (non-`quirk:`) skill, meaning it ships from a different plugin or a personal/global skill location, not from this repository.

Consequence: the description-avoidance rule and the "should-not-trigger on a pure voice/tone request" activation test are both still fully implementable exactly as written — they don't require the sibling skill to exist in this repo, only that this skill's own description not compete for its vocabulary. What is **not** verifiable from inside this repo is a side-by-side reading of the two skills' descriptions to confirm they don't overlap in some way neither author anticipated, because there is no second `SKILL.md` here to read them against. This tech spec proceeds on the assumption that avoiding the four named words is sufficient, per the logic spec's own stated resolution, and flags that assumption as unverified rather than silently treating it as confirmed.

**2. "No numeric thresholds anywhere in SKILL.md" is not mechanically testable as written.** The logic spec locks this as an absolute rule, and the test contract above covers everything else that's testable by grep or substring match. A regex that flags "any digit" would false-positive on the check IDs themselves (`F1`, `A6`, …), on ordinary version numbers, and on legitimate non-threshold numerals if any appear in prose examples; a regex narrow enough to avoid those false positives would be exactly the kind of invented procedural machinery the logic spec's whole design philosophy rejects (see logic.md's "Why this shape and not a style guide"). This tech spec resolves it as a **manual read**, named explicitly in "Always/Ask/Never" and in the testing strategy's coverage table, rather than inventing a brittle automated check to paper over the gap.

**3. `worked-examples.md`'s completeness (28/28 entries) has no automated test.** The team's test contract, as specified, scopes the "all 28 check IDs present" assertion to SKILL.md only (matching `tests/test_skill.py`'s existing pattern of testing the hub file, not reference files). Nothing in the existing test-module conventions checks a reference file's content completeness. This tech spec names it as a manual acceptance item rather than adding a test outside the requested contract's scope — if the reviewer wants an automated check here, that is a scope decision for the plan-building step, not one this tech spec should make unilaterally.
