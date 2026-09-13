# Tech spec: `simplifying-safely`

**Status**: Draft — authored 2026-09-11, complexity gate fired on ≳3 source files.
**Logic spec**: [logic.md](logic.md) — owns *why* and *behavior*. This document owns *where* and
*contracts*. Every section below back-links the logic-spec heading that justifies it.

## Architecture

A Claude Code skill in this plugin's flat `skills/` namespace. No runtime, no script, no hook — the
deliverable is markdown the `Skill` tool loads, plus the static pytest file that pins its contracts.

| Path | Role |
|---|---|
| `skills/simplifying-safely/SKILL.md` | Hub. Every rule that changes behavior, inline. |
| `skills/simplifying-safely/evidence-and-limits.md` | Companion. Per-rule status, evidence, falsification notes, audit→shipped id map. Justification only. |
| `tests/test_simplifying_safely_skill.py` | Contract pins. Stdlib + pytest, no new deps. |
| `README.md` | Skill count, test-enforced. |
| `.claude-plugin/plugin.json` | `keywords`, by convention. |

The hub/companion split mirrors `skills/writing-scannable-prose/`, the closest analogue in the repo
— hub carries operative rules with inline status tags, companion carries "why trust this". Backs
[logic.md § Key decisions](logic.md#key-decisions-and-rationale) ("References carry justification,
never behavior") and [§ Data flow](logic.md#data-flow).

Content source is [audited-ruleset.json](audited-ruleset.json): `rules[].text` (the rule and its
trailing `Falsification:` line), `rules[].status`, `rules[].reviewer_test`,
`rules[].reviewer_test_holds`, `rules[].tier`.

One wrinkle in that source: `G1` is the only rule whose `text` opens with a literal
`[precautionary]` prefix. Strip it — the tag is its own column, and copying verbatim would render
`G1 | [precautionary] Sequence any step… | precautionary`. No other rule needs this.

## Code references

The files behind [logic.md § Behavior](logic.md#behavior) and its
[§ Scope](logic.md#scope-and-non-goals).

Create:

- `skills/simplifying-safely/SKILL.md`
- `skills/simplifying-safely/evidence-and-limits.md`
- `tests/test_simplifying_safely_skill.py`

Modify:

- `README.md:9` — the string `**24 skills**` becomes `**25 skills**`. Enforced by
  `tests/test_adhd_skill.py:157-164`, which compares the README number against a count of
  `skills/*/SKILL.md`. Extend the trailing prose list in the same line.
- `.claude-plugin/plugin.json:12-29` — append keywords to the existing array.

Patterns to follow, by example:

- `skills/writing-scannable-prose/SKILL.md:61` (the prose tag legend) and `:67-69` (the first
  `| ID | Check | Tag |` table) — the rule-table-with-inline-epistemic-tags shape.
- `skills/writing-scannable-prose/SKILL.md:188` — the "Links out" closing section and its bare
  relative link form.
- `tests/test_writing_scannable_prose_skill.py:21-144` — the whole test file shape. There is no
  shared skill-test helper in `tests/conftest.py`; each file reimplements its own frontmatter
  regex. Follow that, do not build an abstraction for one caller.

## Contracts & interfaces

### CONTRACT: frontmatter

Exactly two keys, matching all 24 existing skills.

```
name: simplifying-safely
description: <single line, ≤1024 chars>
```

`name` must equal the directory name. Do **not** carry over the `proactive: true` and `triggers:`
keys at `~/.claude/skills/applying-simplicity-principles/SKILL.md:4-5` — no skill in this repo uses
either, and always-proactive is the behavior
[logic.md § Decisions Locked](logic.md#decisions-locked) replaced with narrow triggers.

### SCHEMA: shipped rule ids

The audit ids in `audited-ruleset.json` are not shippable: `S1` and `S2` each name two rules, and
`D1`/`D2`/`D4` are overloaded across the core and the agent-docs tier. Ship a clean scheme, one
letter per tier, sequential, no collisions. Order within each tier follows
[logic.md § Behavior](logic.md#behavior).

```
G1..G4   gate (always-on core)
D1..D3   detection (always-on core)
C1..C6   code
A1..A4   agent-facing docs
S1..S3   specs
H1..H4   human-facing docs
V1..V2   conversational output
M1..M6   meta
         32 total
```

The audit→shipped mapping table lives in `evidence-and-limits.md`, so provenance to the audit
record survives the renumber. `audited-ruleset.json` keeps its own ids unchanged.

### CONTRACT: per-rule presentation in the hub

Each tier renders as one table. Tag values are exactly the three from
[logic.md § Glossary](logic.md#glossary), plus the diagnosis marker.

```
| ID | Rule | Tag |
```

- `Tag` ∈ {`grounded`, `precautionary`, `judgment`}, optionally suffixed ` · diagnosis`.
- Exactly 4 rules carry `grounded`: `G4`, `D3`, `C6`, `M1`.
- Exactly 7 carry the diagnosis marker — the rules whose `reviewer_test_holds` is `false`:
  `D3`, `C1`, `A4`, `S2`, `S3`, `M4`, `V1`.
- Status tallies, pinned: 4 `grounded`, 14 `precautionary`, 14 `judgment`.

Falsification one-liners are locked inline by
[logic.md § Decisions Locked](logic.md#decisions-locked). Render them as a single list after the
tables — one line per rule, keyed by shipped id — not as a fourth table column, which would make
every table unreadable at terminal width. 15 rules carry one: the 14 `precautionary` plus `C6`.

### CONTRACT: the subagent gate restatement (`M6`)

`M6` requires a dispatcher to restate the gate in a subagent's prompt because the subagent does not
inherit the skill ([logic.md § Data flow](logic.md#data-flow)). A rule that says "restate it" and
then makes the agent compose the restatement will get a paraphrase. Ship the literal block instead,
fenced and copy-pasteable, stating `G1`–`G3` in the imperative. The test pins the fence's presence.

### REGEX: no magnitudes in the hub

[logic.md § Key decisions](logic.md#key-decisions-and-rationale) locks direction only, never
magnitudes. The test asserts no match in `SKILL.md`:

```
\d+(?:\.\d+)?\s*(?:%|per\s?cent|percent)|ρ\s*=|\bR\s*(?:²|\^2|2)\b|\b\d+/\d+/\d+\b
```

Verified against both directions before being written down: it fires on `43%`, `84.7%`,
`43 percent`, `ρ=0.94`, `R2`, `R²`, `R^2` and `71/42/33/57`, and does not fire on rule ids
(`C1-C6`, `M6`), file paths, or "one of four tested configurations". An earlier draft ended the
percent branch with `\b`, which silently passed a bare `43%` because `%` is already a non-word
character — the test would have certified the leak it exists to catch.

The blocklist below is phrased so it never needs to quote a banned figure in order to ban it, which
is what keeps it compatible with this rule.

Also fenced: the 7–11 constraint-count figure from [logic.md § Data flow](logic.md#data-flow) must
**not** appear in `SKILL.md`. `audited-ruleset.json`'s `assembly.budget_note` states that those
counts are for the audit only. logic.md and the companion may carry it; the hub may not.

### CONTRACT: the do-not-cite blocklist (`M1`)

Inline in `SKILL.md`, never relocated to the companion — its job is intercepting a citation
reflex before anyone opens a link, which only works where the agent already is. The companion's
per-rule evidence entry for `M1` is not a second blocklist and is not barred by this ([logic.md § Key decisions](logic.md#key-decisions-and-rationale)). All seven
entries from the audit record's `M1`, each phrased as a ban without restating the banned number.
The test pins these literal anchors:

```
Cursor          Aider          CONVENTIONS.md      Karpathy
McCabe          preference data                    unused
```

### CONTRACT: section order in the hub

The test pins this order by `body.index()`, mirroring
`tests/test_writing_scannable_prose_skill.py:123-129`:

```
Overview → When to Use → always-on core → surface routing → per-surface tiers
  → meta → falsification list → do-not-cite blocklist → Integration → Links out
```

The core precedes every surface tier because it applies at every firing; the blocklist sits before
the links-out section so it is never below the fold.

## Data models

No data model. Nothing is parsed at runtime; the JSON is a build-time source read by humans and by
the test file, not by the skill.

## DO-NOT-CHANGE fences

| Region | Why fenced |
|---|---|
| `docs/quirk/specs/2026-09-11-simplifying-safely/audited-ruleset.json` | Frozen audit record. The companion is the maintained copy; edits here would silently rewrite the provenance the companion cites. |
| `docs/quirk/specs/2026-09-11-simplifying-safely/logic.md` | Approved. Amendments-log entries only, plus the `Status` line this run updates. Never a silent edit. |
| `skills/writing-scannable-prose/**` | Absorbing it is deferred, locked in [logic.md § Deferred Ideas](logic.md#deferred-ideas). The known-duplicate state on human-facing docs is accepted, not a defect to fix here. |
| `tests/test_adhd_skill.py:157-164` | The README-count test is the enforcement. Bump `README.md`, never relax the assertion. |
| `hooks/session-start.sh:9` | Injects `using-quirk` only. This skill is discovered through the normal `Skill` tool; adding it here would make it always-on, contradicting the narrow-triggers lock. |
| `~/.claude/skills/applying-simplicity-principles/` | Outside this repo. See Non-goals. |

## Always / Ask / Never

**Always** — frontmatter is exactly `name` + `description`; every rule carries a tag; every
reference link is a bare relative markdown link; `SKILL.md` stays under 500 lines.

**Ask** — any conflict with a [logic.md § Decisions Locked](logic.md#decisions-locked) entry stops
the run and is recorded as a dated Amendments entry before proceeding. Also ask before adding a
33rd rule: [logic.md § Deferred Ideas](logic.md#deferred-ideas) records that rule admission is
deliberately ungoverned, so growth is a decision, not a drive-by.

**Never** — `@file.md` force-load syntax (banned at `skills/writing-skills/SKILL.md:209-211`); a
magnitude in the hub; the blocklist in a reference file; a per-surface restatement of the gate
(`Part 2 is stated once and inherited`, [logic.md § Data flow](logic.md#data-flow)).

## Testing strategy

Success is defined by [logic.md § Scope](logic.md#scope-and-non-goals) —
reviewer judgment on real drafts, no kill condition. What follows pins the strings that judgment
depends on; it does not attempt to automate the judgment.

`tests/test_simplifying_safely_skill.py`, modelled on
`tests/test_writing_scannable_prose_skill.py`. Static assertions only — the file pins strings, it
does not judge prose. Coverage required:

1. Frontmatter delimiters parse; `name` equals the directory; description length in range.
2. Description contains the narrow triggers and **none** of `ALWAYS`, `proactively`,
   `any code-related task` — mechanically guarding the narrow-triggers lock against a drift back to
   the superseded skill's framing.
3. Description avoids `writing-scannable-prose`'s territory: none of `tighten`, `scannable`,
   `README`, `guide`, `changelog`. Both skills would otherwise fire on one prompt. Mirrors
   `tests/test_writing_scannable_prose_skill.py:73-85`.
4. All 32 shipped ids present as whole words; per-tier counts 7/6/4/3/4/2/6 (the gate and detection rules ship as one always-on core tier).
5. Tag tallies: 4 `grounded`, 14 `precautionary`, 14 `judgment`; 7 diagnosis markers.
6. 15 falsification lines present, keyed by id.
7. All seven blocklist anchors present verbatim.
8. The no-magnitudes regex finds no match; the 7–11 figure is absent.
9. Section order holds.
10. The `M6` restatement fence is present.
11. Links are markdown-relative, never `@`-prefixed; `evidence-and-limits.md` exists and is
    non-empty.
12. `README.md`'s count equals the number of `skills/*/SKILL.md`.

`COMMAND:` acceptance, runnable verbatim:

```
python3 -m pytest tests/test_simplifying_safely_skill.py -q
python3 -m pytest -q
```

### Open question for the user — behavioral validation

`skills/writing-skills/SKILL.md:58` classifies a rule the agent is tempted to rationalize away as
**discipline-enforcing**, and `:301` applies the Iron Law to that type: no such skill without a
failing test first, RED before GREEN. `:307` scopes it — the Law is the default for that type only. `G1`–`G3` are exactly that shape. But
[logic.md § Scope](logic.md#scope-and-non-goals) locks success as "whether a human can say
*violates* or *satisfies* about a real draft," and ships no kill condition.

Two user-approved artifacts in tension. This spec does not resolve it. The option, costed: one
final task running [logic.md § Scenarios](logic.md#scenarios) 1, 5 and 6 — file cleanup, the
config-flag deletion, the subagent dispatch — as pressure prompts against fresh Sonnet subagents,
RED without the skill and GREEN with it. Roughly six dispatches. The Iron Law's scope is the gate
only: tells never decide, so nothing else needs it.

**Outcome, recorded 2026-09-11:** the user kept it. RED ran before any of the skill was written.
Round 1 was void on harness defects; round 2, on a harness given a positive control first,
returned no violation in any probe — though only two of its three verdicts bind the rules as
shipped, the third having been scored against a weaker M6. GREEN was not run — with no violation
to close there was nothing to compare against. Full record in [validation-red.md](validation-red.md); the section above is kept
as the reasoning that produced the decision, not as an open question.

## Non-goals

- **Deleting `~/.claude/skills/applying-simplicity-principles/`.** Outside this repository and not
  a file this run may touch. `SKILL.md` states the supersession; the skim tells the user to remove
  the old skill themselves. Leaving both installed leaves two competing simplicity skills, one of
  them always-proactive — say so plainly rather than silently shipping the collision.
- **A generator that builds `SKILL.md` from `audited-ruleset.json`.** The companion is a maintained
  hand-written document, not a rendered artifact. A generator would make the frozen audit record
  load-bearing at build time and invert the fence above. Recorded here so a later contributor adds
  one deliberately or not at all.
- **`CHANGELOG.md`.** Written at release time by `quirk:releasing-quirk`, not at authoring time.
- **The PostToolUse hook, the executable ablation helper, and rule-admission governance** — all
  three are [logic.md § Deferred Ideas](logic.md#deferred-ideas), deferred with their falsification
  tests rather than built.
- **Prose mechanics.** `writing-scannable-prose` owns them.
