# Tech Spec: Outcome-Altitude Elicitation

**Status:** Authored — reviewed, fixes applied — ready for planning
**Logic spec:** [logic.md](logic.md)

## Architecture

Pure documentation change. No runtime code, no dependencies, no build step. The "system" is three
markdown/Python files in the `quirk` plugin. Back-link: [Scope & non-goals](logic.md#scope--non-goals).

| File | Role | State |
|---|---|---|
| `skills/brainstorming/SKILL.md` | Always-loaded skill body. Owns rules that must be in effect on every run. | Modify (342 lines → ≤400) |
| `skills/brainstorming/references/essential-coverage.md` | Progressive-disclosure reference. Owns the Essential six and the fast-track procedure. | **Already drafted** (80 lines, untracked) — reconcile, do not recreate |
| `tests/test_brainstorming_elicitation.py` | Prose pins for the new mechanisms. | Create |

The `references/` subdirectory follows `skills/exploring-ideas/references/` and
`skills/adhd/reference/` (singular).

**Placement rule:** a rule that must always be in effect goes inline in `SKILL.md`; a *procedure or
list* consulted at a known moment goes in `references/`. A rule behind a link is a rule that
silently does not apply on runs that skip the link.

## Code references

Line numbers are against `skills/brainstorming/SKILL.md` at commit `41748d7` (342 lines, verified).

| Anchor | Current content | Change |
|---|---|---|
| `SKILL.md:10` | Intro: "ask questions one at a time to refine the idea" | Amend for batching — one of **seven** sites carrying this framing |
| `SKILL.md:20-34` | Checklist, 11 steps | Insert new step 6 (coverage gate); renumber old 6–11 → 7–12 |
| `SKILL.md:28` | Checklist step 5: "one at a time, for anything not covered…" | Amend for batching *(separate edit from the renumber above — do not conflate)* |
| `SKILL.md:60` | Edge `"Ask remaining\nclarifying questions" -> "Dispatch option-validation\nresearch (parallel)"` | Split into two edges through the new node. **Only this edge**; `:61`'s endpoints are untouched |
| `SKILL.md:38-70` | `digraph brainstorming` node list | Add one node for the coverage gate |
| `SKILL.md:110-116` | `### Result Integration` | Findings become *candidate questions*, not direct question input |
| `SKILL.md:152` | End of `### Expected Gray-Area Catalog` | **Insertion point** for the new `### Question Altitude` subsection |
| `SKILL.md:151-152` | `Data` and `Integration` catalog rows | Altitude cleanup — exactly as specified below |
| `SKILL.md:224-241` | `### Step 2 — Drill-in` | Add the ordering rule to the per-question rules |
| `SKILL.md:242-247` | `### Checkpoint Rules` | Add the delegation-vs-election sentence |
| `SKILL.md:263` | "run the gray-areas resolution … before **single-question dialogue**" | Amend for batching — **site three**, found by the plan-document reviewer; uses neither "one at a time" nor "per message", which is why two earlier sweeps missed it |
| `SKILL.md:264,266` | "ask ... one at a time", "Only one question per message" | Amend for batching — sites three and four |
| `SKILL.md:316` | Key Principle: "**One question at a time** (free-form dialogue)" | Amend for batching — site six |
| `SKILL.md:319` | Key Principle: "**Resolve gray areas before single-question dialogue**… ask remaining open questions one at a time" | Amend for batching — **site seven**, found by the plan-build coherence sweep; a second principle distinct from `:316` |

### Catalog cleanup — the exact entries

Auditing the catalog against the altitude test found **one** plainly build-only entry, not three.
The other two are legitimate but ambiguously named. Back-link: [The altitude rule](logic.md#the-altitude-rule).

| Entry | Domain | Ruling | Action |
|---|---|---|---|
| `auth-storage` | Integration | **Build-only.** Where credentials live is invisible to the integrator. | Replace with `auth-method` — how the consumer authenticates, which *is* observable |
| `performance-mode` | Data | **In bounds, ambiguously named.** Means the user-selectable mode, not internal optimization strategy. | Keep; annotate to name the observable reading |
| `data-mapping` | Integration | **In bounds.** For an integration the field contract *is* the observable surface. | Keep; annotate that it means the visible field contract, not the transform implementation |

`CONTRACT:` No other catalog entry changes. If applying the altitude test appears to invalidate a
*fourth* entry, stop and surface it rather than deleting — see Always/Ask/Never.

## Contracts & interfaces

Back-links: [The altitude rule](logic.md#the-altitude-rule), [The Essential set](logic.md#the-essential-set),
[Behavior & scenarios](logic.md#behavior--scenarios).

**The altitude test** — the literal wording is the specification; applied per candidate question.

`CONTRACT:` `Would the answer change what the consumer observes, or only how it is built?`
`observable → in bounds · build-only → out of bounds · "observable" is relative to THIS thing's consumer`

**Escape clause** — must appear adjacent to the test, or the rule reads as absolute and gets
rationalized at the first API spec:

`CONTRACT:` an implementation choice may be asked when that choice *is itself* the user-facing
decision — the same exception already granted for naming file structure.

**Ambiguous altitude — the tie-breaker.** Every other contract here inherits a fallback from
elsewhere in the spec; this one needs its own, or the unclear case resolves by coin-flip:

`CONTRACT:` when altitude is genuinely unclear, attempt to **reframe the question in terms of what
the consumer observes**. If it survives reframing, ask the reframed version. If it cannot be
reframed observably, it is build-only → route to `[tech-spec]`. Never ask the un-reframed version.

**The three screens**, applied in order over every candidate question:

`CONTRACT:` `altitude(q) → tier(q) → order(q)`
`altitude rejects; tier classifies Essential|Default-able; order sorts most-forking-first, then foundational→edge-case`

**Coverage gate** (new checklist step 6):

`CONTRACT:` `covered = established_decisions ∩ ESSENTIAL_SIX`
`if |covered| < 6: ask the gaps, do not proceed to approaches`
`fast-track is legal iff |covered| == 6`

Precondition: clarifying questions have run. Postcondition: all six coverable without invention.
Invariant: coverage is judged by substance, not by whether a question was asked. Error behavior:
a steer arriving before coverage is declined — name the open items, ask them, do not skip
([Behavior & scenarios](logic.md#behavior--scenarios)).

**Fast-track trigger** — recognized free-text steer, never an `AskUserQuestion` option.

`REGEX:` recognize intent, not literal strings — "enough, design it" / "go with your
recommendations" / "stop asking and build it" and clear paraphrases.

## Data models / schemas

Two literal tags. Exact strings matter — they are what a reader and a later tech spec scan for.
Back-link: [Decisions Locked](logic.md#decisions-locked).

`SCHEMA:` Decisions Locked entry, fast-tracked item → `- <decision> — assumed — fast-tracked`
`SCHEMA:` Deferred Ideas entry, build-only question → `- [tech-spec] <the question>`

Both are **content brainstorming produces inside sections that already exist**. Neither adds a
section to `logic.md`, so neither requires editing `skills/writing-specs/logic-spec.md`.

## DO-NOT-CHANGE fences

Each fence names the region and why it is fenced.

1. **`SKILL.md:27` — checklist step 4's adhd wording.** The literal substring
   ``optionally surface *additional* non-obvious areas via the `adhd` skill first`` is asserted by
   `tests/test_brainstorming_adhd_offer.py::test_checklist_step_4_reworded`. Renumbering steps is
   safe; altering this sentence is not.
2. **`SKILL.md:154-223` — the entire `Step 0` / `Step 1` adhd block.** Seven pinned substrings
   across three test functions: `### Step 0 — Offer adhd divergent discovery (optional)`,
   `Find gray areas`, `Use the standard set (Recommended)`, `Add adhd areas`,
   `latent ambiguous decisions`, ``prefixing each label with `adhd:` ``, and `truly trivial`.
   Inserting the altitude subsection at `:152` (immediately *before* this block) is fine; editing
   inside it is not.
3. **The literals `Industry Insights` and `Deferred Ideas` must both remain present in `SKILL.md`.**
   `tests/test_writing_specs_skill.py::test_brainstorming_section_names_match_logic_spec` requires
   each to appear in *both* `brainstorming/SKILL.md` and `writing-specs/logic-spec.md`. The
   `[tech-spec]` tag attaches to Deferred Ideas — do not rename the list to accommodate it.
4. **Negative fence: never reintroduce** ``consider using the `adhd` skill to surface non-obvious options``.
   `test_approaches_advisory_bullet_removed` asserts its absence; it was deliberately removed in #25.
5. **`skills/writing-specs/**` — not edited by this work.** Per
   [Scope & non-goals](logic.md#scope--non-goals). A change there doubles the review surface and
   re-opens a consolidation that landed in #39.

## Always / Ask / Never

**Always**
- Keep `SKILL.md` ≤ 400 lines (`COMMAND:` `wc -l skills/brainstorming/SKILL.md`).
- Keep the full suite green — **1020 tests pass** at `41748d7`; the two files most at risk are
  `test_brainstorming_adhd_offer.py` (6) and `test_writing_specs_skill.py` (10).
- Put the altitude test's literal wording inline, not behind the reference link.

**Ask**
- If the altitude test appears to invalidate a catalog entry beyond the three ruled on above,
  surface it rather than deleting.
- If the ≤400-line cap cannot be met without compressing settled prose, stop. Compressing
  spec-locked rule text to hit a budget silently sheds operative clauses.

**Never**
- Never write the Essential six into a produced `logic.md` as a section, a checklist, or a score —
  per [Key decisions](logic.md#key-decisions--rationale), a rubric the model is later measured
  against gets padded.
- Never add the fast-track as an option inside an `AskUserQuestion` call — it would consume one of
  four slots and is a delegation option, which `Checkpoint Rules` forbids.
- Never renumber or reword inside the fenced adhd block.

## Coherence sweep (plan-build)

Repo-wide grep for the changed vocabulary. Every referencing file is scoped or cleared.

| File | Ruling |
|---|---|
| `skills/brainstorming/SKILL.md` :10, :28, :263, :264, :266, :316, :319 | **Scoped** — all seven amended |
| `skills/brainstorming/SKILL.md:244` | **Scoped** — sole site of the no-delegation rule |
| `skills/exploring-ideas/references/techniques/first-principles.md:11` | unchanged, verified consistent — unrelated sense ("reintroduce conventions one at a time") |
| `skills/exploring-ideas/references/techniques/scamper.md:21` | unchanged, verified consistent — unrelated sense (lenses applied one at a time) |
| `skills/subagent-driven-development/SKILL.md:477` | unchanged, verified consistent — merging branches one at a time |
| `skills/adhd/**` | unchanged, verified consistent — delegates gray-area discovery; encodes no question cadence |
| `skills/exploring-ideas/SKILL.md:35` | unchanged, verified consistent — that skill's own scoping cadence |
| `skills/filing-requests/reference/field-catalogs.md:92` | unchanged, verified consistent — that skill's own "one question per turn" rule |
| `skills/adversarial-review/profiles/plan.md:4` | unchanged, verified consistent — unrelated idiom |
| `skills/receiving-code-review/SKILL.md:170` | unchanged, verified consistent — unrelated (batching code fixes) |

**Corrections logged.** The site count moved twice, and the reason matters more than the number:

- 4 → 6 at plan-build: greps for `one at a time` found a second Key Principle at `:319`.
- 6 → 7 at plan review: `:263` says **single-question dialogue** and contains neither earlier
  search term. `:319` was caught only because it happened to carry both phrasings.

`CONTRACT:` the sweep term set is `one at a time | one question | single-question | per message |
one-at-a-time`. Searching a subset is what produced both misses.

## Cross-cutting

**Rollback:** single-commit revert; no migration, no persisted state, no consumers outside the repo.

**Observability:** none available. There is no telemetry on skill behavior, which is why outcome
measurement is a Deferred Idea rather than an acceptance criterion. The only feedback channel is the
prose pins plus human review of a later brainstorming session.

**Security:** none — no scripts, no network, no user input handling.

## Testing strategy

New file `tests/test_brainstorming_elicitation.py`, matching the prose-pin style of
`tests/test_brainstorming_adhd_offer.py` (read the file, assert literal substrings).
Back-link: [Decisions Locked](logic.md#decisions-locked) → Placement.

| What | Acceptance bar |
|---|---|
| Coverage gate is a checklist step | New step present; checklist renumbered to 12 |
| Coverage gate in the flow graph | New node string present in the `digraph` block |
| Essential six | All six item names present in `references/essential-coverage.md` |
| Altitude test | The literal test sentence present **inline in `SKILL.md`**, not only in the reference |
| Altitude escape clause | Escape wording present adjacent to the test |
| Altitude tie-breaker | Reframe-or-route rule present |
| Catalog cleanup | `auth-storage` absent; `auth-method` present |
| Routing tag | `[tech-spec]` documented against the Deferred Ideas list |
| Fast-track tag | `assumed — fast-tracked` documented against Decisions Locked |
| Fast-track gate | Text stating it is available only after Essential coverage |
| Fast-track is not an option | Text stating it is a free-text steer, never an `AskUserQuestion` option |
| Delegation vs election | The new Checkpoint Rules sentence present |
| Ordering rule | Most-forking-first wording present in the drill-in rules |
| Batching amended everywhere | **Absence-based:** none of the seven stale literals survives in `SKILL.md` (see the pin list in the test file). Absence, not a count, so an eighth site cannot hide |
| Reference file linked | `SKILL.md` links `references/essential-coverage.md` — nothing links to it today |
| Candidate questions | Result Integration states findings become *candidate* questions |
| Reference file reachable | `references/essential-coverage.md` exists and is linked from `SKILL.md` |
| Body budget | `SKILL.md` ≤ 400 lines |

`COMMAND:` `python3 -m pytest tests/ -q`

Expected: **1020 pre-existing tests pass** plus the new file's pins; 0 failures.

## Non-goals

- No activation testing — the skill description is unchanged.
- **No subagent behavioral test that the rules are followed once loaded.** Prose pins prove
  presence, not compliance. This is a known, accepted limit, not an oversight.
- No changes to the Visual Companion, the Research Agents phase structure, or the adhd flow.
- No edit to `skills/writing-specs/`.
