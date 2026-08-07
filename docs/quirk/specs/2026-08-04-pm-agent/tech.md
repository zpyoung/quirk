# Tech spec — `pm-agent`

**Status:** **Phase 1 sections approved for implementation. Phases 2–3 are a reviewed draft with
known critical defects — do not build from them.**

> **Scope gate — read before implementing anything.**
>
> This document was adversarially reviewed on 2026-08-05
> ([`review-2026-08-05-codex-tech.md`](./review-2026-08-05-codex-tech.md), 15 findings: 3 critical,
> 10 high, 2 medium). Its verdict was *not buildable as written*, and every critical landed in the
> write and dispatch layers.
>
> **Approved — Phase 1 (read layer).** *Architecture*, *Code references*, *Parser strict vs.
> compatibility modes*, the `artifact_lib.py` contract, the index/status/doctor read layer, *DO-NOT-
> CHANGE fences*, and the Phase 1 rows of *Testing strategy*. The parser section has been corrected
> since the review — see below — and its defect was found and fixed here, not deferred.
>
> **Not approved — Phases 2–3.** The lifecycle/CAS mechanism, `park` persistence, schema-v2
> migration, `reconcile`, the probe contract, the packet, and the Orca adapter. Confirmed defects
> include: CAS silently dropped the `attempt` key the logic spec locks, so a stale `finish` can
> write attempt-1 evidence into attempt 2; `park` records neither reason nor attempt count; the Orca
> adapter omits `orca orchestration send`'s **required** `--subject` and reads `result.dispatch.id`
> where the CLI returns a flat `dispatchId`; and with `EXPECTED_SCHEMA_VERSION` raised to 2,
> `artifact_append.py`'s `version > EXPECTED` guard accepts a **v1** file and writes v2 fields into
> it — the mixed-schema state v2 exists to prevent.
>
> These sections stay in the document as a starting point for a later pass. They are not a build
> target.
**Logic spec:** [`logic.md`](./logic.md) — owns *why* and *behavior*, including the threat model
(cooperative worker, legibility not enforcement — every check named below is a mistake-catcher, none
is a security control). This document owns *where* and *contracts*. Every technical section
back-links the `logic.md` section it implements.

**For agents.** This is the code-anchored implementation map for `bin/artifact_lib.py`, `bin/pm.py`,
`bin/pm_adapter.py`, the schema-v2 templates, the nine `/quirk:pm:*` commands, and the `pm` skill.
It contains pointers, not pasted prose — exact files, contracts, and schemas. The implementer
authors the actual script bodies and `SKILL.md`/command prose; this document says *where*, *what
must be true after*, and *what not to guess at*.

**No-Code convention (inherited from `writing-plans`).** Every code-shaped block below is tagged
`CONTRACT:` (interface/signature shape), `SCHEMA:` (exact data shape / literal on-disk rendering),
`COMMAND:` (verbatim shell), `REGEX:` (a literal pattern that is the spec), `CONFIG:` (exact config
keys/values), or `PSEUDOCODE (justified, ≤3 lines):`. No block pastes a full implementation.

**Where this spec had to call it.** `logic.md`'s own Amendments log explicitly defers five things to
this document by name: "`ROADMAP.md` grammar, `Blocked by` lexical rules, parser strict/compat
modes, exit-code table, and the fault-injection test matrix" (`logic.md` → [Status & amendments →
2026-08-05 — completion contract reworked](./logic.md#status--amendments)). It further states, of
the Orca dispatch-ID sequencing problem, that it is "left open... a Phase 3 sequencing problem" —
also this document's job to resolve. Wherever this document invents something `logic.md` doesn't
state, the call is marked inline with **Tech-spec call (logic.md silent):** and its reasoning. These
are additions, not reinterpretations — none of them narrows or contradicts a Decisions Locked entry.

---

## Purpose

Make `bin/pm.py`, `bin/artifact_lib.py`, and the schema-v2 write path buildable and testable without
reopening any behavioral question `logic.md` already settled. Concretely, this document pins down:

1. **The formal grammars** `logic.md` deliberately left to implementation: `ROADMAP.md`'s milestone
   syntax, `Blocked by`'s lexical rules, and the on-disk rendering of every new field.
2. **The parser convergence** that `logic.md`'s own Key Decisions flags as a precondition for
   shipping anything: `artifact_append.py:88-92` and `artifact_review.py:18-31` have already
   diverged, and this document picks — and justifies — the one canonical behavior
   `bin/artifact_lib.py` implements.
3. **Five algorithms** logic.md names but leaves as prose: the probe execution contract, the
   compare-and-swap transition mechanism, the `migrate` upgrade, the `reconcile` promotion pass, and
   the Orca adapter's call sequencing (including the dispatch-ID ordering problem `logic.md` states
   it could not resolve).
4. **The full exit-code table**, continuing the scheme `artifact_append.py` established (2/3/5/8) and
   closing the gap where exit 4 was promised in the original design but never implemented.
5. **The test and fault-injection matrix** — lifecycle transitions, CAS races, crash-mid-transition,
   probe semantics, worktree failures, cross-project paths, skipped signals, v1→v2 migration, and
   parser compatibility.

Out of scope: `SKILL.md`'s prose, the nine command files' exact wording, and script bodies. Those are
the implementer's, written against the contracts here.

---

## Architecture

*Back-link: [logic.md → Decisions Locked → Structure](./logic.md#decisions-locked)*

`CONFIG:` file layout —

```
bin/
  artifact_lib.py         # NEW — shared parse/render primitives (§Parser strict vs. compatibility modes)
  pm_adapter.py            # NEW — Adapter Protocol, git-only fallback, orca adapter (§The adapter)
  pm.py                    # NEW — CLI: next/start/finish/park/decide/reconcile/roadmap/status/migrate
  artifact_append.py       # MODIFIED — imports artifact_lib; gains `blocked_by`/`logged` fields; EXPECTED_SCHEMA_VERSION 1→2
  artifact_review.py       # MODIFIED — imports artifact_lib; behavior preserved (see convergence note)
  artifact_init.py         # MODIFIED — also scaffolds templates/ROADMAP.md

templates/
  BUGS.md DEFERRED.md TEST_BACKLOG.md proposals.md   # MODIFIED — schema-version: 2, new field docs
  ROADMAP.md                                          # NEW template

hooks/
  load_artifact_tail.sh    # MODIFIED — calls `pm.py --index` instead of tailing

skills/
  pm/SKILL.md               # NEW

commands/
  pm/next.md      pm/start.md     pm/finish.md   pm/park.md
  pm/decide.md    pm/reconcile.md pm/roadmap.md  pm/status.md   pm/migrate.md

tests/
  test_artifact_lib.py      # NEW — parser convergence, strict/compat modes, ROADMAP.md grammar
  test_pm_ready.py          # NEW — ready-set, urgency, age, unplaced (§Job 1)
  test_pm_lifecycle.py      # NEW — start/finish/park/decide, CAS, exit codes
  test_pm_probes.py         # NEW — test:/grep:/none probe contract, hashing
  test_pm_handoff.py        # NEW — packet, worktree creation, adapter Protocol, git-only fallback
  test_pm_orca_adapter.py   # NEW — orca adapter against a stubbed `orca` CLI (no network/orca install)
  test_pm_reconcile.py      # NEW — three-way exit distinction, fetch, --verify
  test_pm_migrate.py        # NEW — idempotent v1→v2, partial-run resume, proposals.md version bump
  test_pm_index_doctor.py   # NEW — bounded index rendering, doctor findings catalog
  conftest.py               # MODIFIED — add pm-specific fixtures (§Testing strategy)
```

**Technologies in play:** Python 3.9+ stdlib only (`argparse`, `re`, `fcntl`, `subprocess`,
`dataclasses`, `typing.Protocol`, `hashlib`, `datetime`, `pathlib`), `git` (invoked via
`subprocess`, never a git-python binding), the `orca` CLI (invoked via `subprocess`, optional —
its absence is the tested default path, not a degraded one), pytest (repo's existing stack,
`pyproject.toml:1-8`).

**Tech-spec call (logic.md silent):** `logic.md`'s Decisions Locked → Structure names exactly two
files (`bin/artifact_lib.py`, `bin/pm.py`). This document adds a third, non-CLI module,
`bin/pm_adapter.py`, holding the Adapter `Protocol` and its two implementations. It has no
`argparse` surface of its own and is never invoked directly — `pm.py` imports it. This mirrors the
`filing-requests` tech spec's own precedent (`_common.py`/`_yaml_mini.py` beyond `logic.md`'s named
scripts, [filing-requests/tech.md → Architecture](../2026-07-30-filing-requests/tech.md)):
splitting internal implementation modules that carry no independent command surface doesn't add to
the *deliverable* surface `logic.md` locked, and keeps `pm.py` from becoming an unreviewable single
file mixing CLI parsing, lifecycle logic, and subprocess-heavy adapter code with very different
testing needs (the adapter tests stub `git`/`orca`; the lifecycle tests don't touch either).

**Architecture-level guarantees (inherited from the original design, still binding):**

1. All artifact mutation — ledger fields and `ROADMAP.md` alike — routes through `bin/*.py`. Claude
   never `Edit`/`Write`s an artifact file directly.
2. **Inert in a project that has not run init.** `pm.py` degrades exactly like `artifact_append.py`
   does today: no `BUGS.md`/etc. → the same "run `/quirk:artifacts:init` first" message, never a
   traceback. See [§Inertness and v1/v2 back-compat](#inertness-and-v1v2-back-compat).
3. Hooks remain warn-only and always `exit 0` — see `hooks/load_artifact_tail.sh:9-10,36` for the
   existing gate pattern this module's hook change preserves.

---

## Code references

*Back-link: [logic.md → bin/artifact_lib.py is extracted before any feature lands](./logic.md#key-decisions--rationale)*

| Symbol | Today | After this work |
|---|---|---|
| `find_max_id` | `bin/artifact_append.py:88-92` (loose, no title capture) | moved verbatim to `bin/artifact_lib.py`, unchanged regex — see [§Parser strict vs. compatibility modes](#parser-strict-vs-compatibility-modes) |
| `render_entry` | `bin/artifact_append.py:95-106` | moved verbatim to `bin/artifact_lib.py` |
| `SCHEMA_VERSION_RE` / `detect_schema_version` | `bin/artifact_append.py:109-114` | moved verbatim to `bin/artifact_lib.py` |
| `parse_entries` | `bin/artifact_review.py:18-31` (strict, title required, dict-collapses repeated field labels) | reimplemented in `bin/artifact_lib.py` as `parse_entries` returning `Entry`/`MalformedHeading`, strict by construction — see below |
| `SCHEMAS` dict | `bin/artifact_append.py:14-83` | moved to `bin/artifact_lib.py`, `bug`/`defer`/`test-skip` gain `blocked_by`; `test-skip` gains `logged` |
| `EXPECTED_SCHEMA_VERSION = 1` | `bin/artifact_append.py:85` | `SCHEMA_VERSION = 2` in `bin/artifact_lib.py`, imported by both `artifact_append.py` and `artifact_review.py` |
| flock discipline | `bin/artifact_append.py:165-180` (`.{file}.lock`, `ARTIFACT_LOCK_TIMEOUT`, 5s default) | reused verbatim (same lock file, same env var) by `pm.py` — see [§The CAS transition mechanism](#the-cas-transition-mechanism) |
| `--project-dir` convention | `bin/artifact_append.py:122-123`, all four `bin/*.py` scripts | reused by every `pm.py` subcommand |
| ADR ID allocation pattern (retry-on-collision) | `bin/adr_create.py:60-71` | referenced, not reused — `pm.py` never allocates new ledger IDs, only `artifact_append.py` does |

**The divergence team-lead flagged, confirmed at these exact lines:**
`bin/artifact_append.py:90` — `re.compile(rf"^##\s+{re.escape(header)}-(\d+):", re.MULTILINE)` — no
title captured, no title required. `bin/artifact_review.py:20` —
`re.compile(rf"^##\s+{re.escape(header)}-(\d+):\s*(.+)$", re.MULTILINE)` — requires `\s*(.+)$`, i.e.
at least one non-whitespace-trimmed character before end of line. A heading `## BUG-7:` with nothing
after the colon matches the first and not the second. `bin/artifact_review.py:29` collapses repeated
field labels into a `dict` — the reason `logic.md` repeatedly cites for why lifecycle history can't
be preserved by field duplication (`logic.md` → [Attempt and refusal counts are aggregates, not a
history](./logic.md#job-2--ushering-a-started-task)).

---

## Parser strict vs. compatibility modes

*Back-link: [logic.md → bin/artifact_lib.py is extracted before any feature lands](./logic.md#key-decisions--rationale),
[logic.md → Amendments → shared-parser extraction deferred to tech.md](./logic.md#status--amendments)*

**The canonical rule: two regexes, one strict and one loose, each kept for the job it already does —
never unified into one, because unifying them would either break ID allocation's safety property or
break the backlog's agreement property.**

`REGEX:` — **loose (ID-only), used exclusively for `find_max_id`:**
```
^##\s+{header}-(\d+):
```
Verbatim from `bin/artifact_append.py:90`. Its job is "never allocate an ID that's already claimed on
disk." Any heading claiming an ID — however malformed — has claimed it, so this regex must stay loose
or a titleless legacy heading becomes an invisible, re-issuable ID. **This is unchanged behavior**:
`bin/artifact_lib.find_max_id(text, header)` is `bin/artifact_append.py:88-92` moved verbatim.

`REGEX:` — **strict (title validation), used to classify blocks:**
```
^##[ \t]+{header}-(\d+):[ \t]*(\S.*)$
```

**This is NOT verbatim from `bin/artifact_review.py:20`, and the difference is a live bug.** The
existing regex is `^##\s+{header}-(\d+):\s*(.+)$`, and an earlier draft of this section reproduced
it while claiming it "requires a non-empty title". It does not. `\s` matches newlines, so `\s*`
happily crosses the line break and `(.+)` then consumes the *next line* as the title. Verified:

```
## BUG-7:                     →  matches, with title = '- **Severity**: low'
- **Severity**: low
```

Two consequences, both silent today: the entry is admitted as *valid* with a garbage title, and the
swallowed line is no longer part of the block, so **that field is lost from the parse**. A
whitespace-only title (`## BUG-1:` plus trailing spaces) is admitted the same way, since `\s*`
backtracks to leave one space for `(.+)`; `.strip()` then yields `''`.

The corrected regex restricts post-colon whitespace to horizontal (`[ \t]*`) and requires the title
to begin with a non-whitespace character (`\S`), so a titleless heading genuinely fails to match.

`ALGORITHM:` — **loose headings are the block boundaries; strict classifies what is inside them.**

This ordering is load-bearing and is the second half of the fix. If strict matches were used as
boundaries — as `bin/artifact_review.py:23-28` does today — then a heading that fails strict is not
a boundary at all, so the preceding entry's block runs on through it and the field scan absorbs its
fields under last-value-wins. A malformed heading would silently overwrite its predecessor's
`Status`. Slicing on loose and classifying afterwards makes every ID-claiming heading terminate the
block before it, whether or not it is well-formed:

```python
bounds = list(LOOSE.finditer(text))
for i, m in enumerate(bounds):
    end   = bounds[i + 1].start() if i + 1 < len(bounds) else len(text)
    block = text[m.start():end]
    → STRICT.match(block) ? Entry(...) : MalformedHeading(...)
```

Verified against the three-entry case (valid / titleless / valid): the titleless heading no longer
swallows a line, the preceding entry keeps its own fields, and the malformed block is reported
*with* its fields intact so `--doctor` can show what is in it.

Every consumer that decides what's `open`, `ready`, `unplaced`, or roadmap-eligible —
`pm.py next/start/finish/park/decide/reconcile/status/doctor/index` and the refactored
`artifact_review.py` — uses this one classifier. That is the convergence `logic.md`'s Key Decisions
section requires ("Job 1 and job 2 must agree on what 'open' means").

**This is a behavior change, and it is deliberate.** `artifact_review.py`'s output changes for files
containing a titleless heading: an entry that today renders with a garbage title and a missing field
becomes a `--doctor` finding instead. No existing test covers that input (see *No-behavior-change
verification* below), and the current behavior is not worth preserving — it is data loss.

`CONTRACT:`
```python
@dataclass(frozen=True)
class Entry:
    id: int
    header: str                    # "BUG" | "DEFER" | "TEST" | "PROPOSAL"
    title: str
    fields: dict[str, str]         # last-value-wins collapse of repeated labels (unchanged from today)
    raw: str                       # verbatim block text incl. heading line, for handoff-packet copy
    start: int                     # char offset of heading line start, for in-place field splicing

@dataclass(frozen=True)
class MalformedHeading:
    id: int
    header: str
    reason: str                    # "no title" | "duplicate id"

@dataclass(frozen=True)
class ParseResult:
    entries: list[Entry]           # strict-mode matches only
    malformed: list[MalformedHeading]

def parse_entries(text: str, header: str) -> ParseResult: ...
def find_max_id(text: str, header: str) -> int: ...
def render_entry(schema: dict, entry_id: int, fields: dict[str, str]) -> str: ...
def detect_schema_version(text: str) -> int | None: ...
```

**What happens to entries the old parsers disagreed about.** A titleless `## BUG-7:` heading:
`find_max_id` still counts ID 7 as claimed (loose regex, unchanged) — a later append still allocates
`BUG-8`, not a colliding `BUG-7`. `parse_entries` excludes it from `.entries` and returns it in
`.malformed` with `reason="no title"`, carrying its parsed fields so `--doctor` can display them.

Note this is *not* "matching today's `artifact_review.py` behavior" — today that heading is admitted
as a valid entry with the next line as its title, and that line's field is dropped. The new
behavior is the corrected one. Every backlog computation (`ready`, `unplaced`, `--next`'s shortlist) therefore
never sees it — consistent with today's `artifact_review.py`, and now *also* consistent with
`--next`/`--doctor`, which didn't exist before. `--doctor` surfaces it as a `MALFORMED_HEADING`
finding (id, header, line) — see [§Doctor findings catalog](#doctor-findings-catalog) — so the
divergence that used to be silent (present in one script's output, absent from the other's) is now a
visible, actionable finding instead of a second silent disagreement.

**Duplicate entry IDs** (two well-formed headings both claiming e.g. `BUG-7` — the loud-merge-conflict
case `logic.md`'s non-goals section accepts as intentionally loud): `parse_entries` returns *both* as
separate `Entry` objects sharing `.id == 7` in `.entries` (matching today's block-slicing behavior,
which already tolerates this without crashing). **Tech-spec call (logic.md silent):** any `pm.py`
lookup-by-ID (`start`, `finish`, `park`, `decide`, blocker resolution) that resolves to more than one
`Entry` for the requested ID refuses — exit 4 (§Exit codes) — naming both line numbers, rather than
guessing which block to mutate. `--doctor` also reports it as `DUPLICATE_ID`, independent of whether
any command was run against it.

**No-behavior-change verification.** `test_artifact_append.py` and `test_artifact_review.py` are the
acceptance bar: every test in both files must pass unmodified against `bin/artifact_lib`-backed
`artifact_append.py`/`artifact_review.py`. Concretely: `test_gaps_use_max_plus_one`
(`tests/test_artifact_append.py:101-116`) and `test_sequential_id_increment` (`:85-98`) pin
`find_max_id`'s loose behavior; `test_review_lists_populated_entries`
(`tests/test_artifact_review.py:16-33`) pins `parse_entries`'s strict behavior and its exact
`render_report` output shape. Neither fixture set includes a titleless, whitespace-titled, or duplicate heading today, so the
change above alters zero currently-asserted output. That absence is exactly why the defect survived:
the behavior it corrects was never observed by any test.

`tests/test_artifact_lib.py` adds the fixtures that pin it, and these are the acceptance bar for
Phase 1 — each corresponds to a failure verified against the live code:

| Fixture | Asserts |
|---|---|
| `## BUG-7:` alone on its line, followed by a field line | strict does **not** match; the following line is **not** consumed as a title; the field remains in the malformed block |
| `## BUG-1:` + trailing spaces | strict does **not** match — guards the `\s*` backtrack |
| valid / titleless / valid, in that order | the middle heading terminates the first block; entry 1 keeps its own fields and acquires none from entry 2 |
| titleless heading | `find_max_id` still counts the ID (loose unchanged), so it is never re-issued |
| duplicate-ID heading pair | both returned as separate `Entry` objects; lookup-by-ID refuses with exit 4 |
| existing gap / sequential / unicode cases | re-run directly against `artifact_lib` |

**No "compatibility mode" flag.** `logic.md`'s amendment log uses the phrase "parser strict vs.
compatibility modes" naming what to specify, not naming two runtime-selectable behaviors. There is
exactly one behavior per function (`find_max_id` always loose, `parse_entries` always strict) — no
flag, no environment variable, no per-call opt-out. A flag would reintroduce the exact
divergence-by-configuration this section exists to close.

---

## Data models & schemas

*Back-link: [logic.md → In scope for v1](./logic.md#in-scope-for-v1),
[logic.md → Decisions Locked → Completion evidence](./logic.md#decisions-locked)*

### `ROADMAP.md` formal grammar

`SCHEMA:` file shape —
```markdown
<!-- schema-version: 2 -->
<!-- ROADMAP.md SCHEMA
Ordered milestones, each naming BUG/DEFER/TEST entry IDs. Milestones are ordered
top-to-bottom; earlier milestones rank higher for --next's sort key. An ID should
appear in at most one milestone (--doctor flags duplicates). PROPOSAL entries are
never valid roadmap members. This file is agent-proposed, human-ratified — see
/quirk:pm:roadmap. Manual edits are allowed; pm.py re-parses on every run.
-->

# ROADMAP

## Milestone: Auth hardening
- BUG-3
- DEFER-7
- TEST-12

## Milestone: Search v2
- BUG-9
```

`REGEX:` milestone heading — `^## Milestone: (.+)$` (heading text is the free-text display name; no
ID, no slug — milestones are referenced only by document position, never by identity, since
"linkage lives in the roadmap, not on the entry" (`logic.md` → [Key decisions &
rationale](./logic.md#key-decisions--rationale)) applies symmetrically: nothing outside `ROADMAP.md`
ever names a milestone).

`REGEX:` membership line, one ID per line — `^- (BUG|DEFER|TEST)-(\d+)\s*$`. Any other line under a
milestone heading (a restated title, a description, a line with trailing content after the ID) is
excluded from membership and reported by `--doctor` as `ROADMAP_LINE_MALFORMED` (milestone name, raw
line) — never a hard parse failure, matching `bin/artifact_lib`'s per-line resilience posture.

**Ordering.** Milestone rank is 0-based document position (first `## Milestone:` heading = rank 0).
An eligible entry in no milestone sorts at rank `-1` (already locked: [logic.md → Milestone rank for
the escape hatch](./logic.md#job-1--roadmap-and-whats-next)).

**Duplicate membership** (an ID under two milestones). **Tech-spec call (logic.md silent):**
first-occurrence-wins for rank (the earliest milestone containing the ID determines its sort rank);
every occurrence past the first is a `--doctor` `DUPLICATE_MEMBERSHIP` finding (id, first milestone,
duplicate milestone). This mirrors the "fail toward a definite, computable answer, never a crash"
posture the locked decisions already use for dangling/self/cyclic blockers
([logic.md → An unresolvable blocker blocks](./logic.md#job-1--roadmap-and-whats-next)) — applied
here because `logic.md` names the rule ("a milestone's membership is one fact") without saying what
happens when a hand-edit violates it.

**Dangling / disallowed references.** `--doctor` findings, never a read-time failure:
- `DANGLING_ROADMAP_REF` — an ID with no matching entry in any ledger file. Verbatim: "`--doctor`
  flags only roadmap IDs that do not exist" ([logic.md → Entry closed but still named in the
  roadmap](./logic.md#scenarios)).
- `PROPOSAL_IN_ROADMAP` — a `PROPOSAL-N` ID under any milestone. Locked: "it may not reference a
  `PROPOSAL`... `--doctor` reports a `PROPOSAL` reference in a milestone as a finding" ([logic.md →
  In scope for v1](./logic.md#in-scope-for-v1)).
- `DUPLICATE_MILESTONE_NAME` — two `## Milestone:` headings share the same display text.
  **Tech-spec call (logic.md silent):** low-severity finding, non-blocking — rank comes from
  position, not name, so this can never corrupt sort order; it's purely a human-legibility nit.

**Write-time is stricter than read-time.** `pm.py roadmap --write <path>` (§Contracts, below)
validates a *freshly agent-proposed* file before committing it and **refuses** (exit 2) on any of:
malformed membership line, unknown ID, `PROPOSAL` reference, or duplicate membership — there is no
legacy content to be lenient about at the moment new content is generated. `--doctor`, reading
whatever is *already on disk* (possibly hand-edited, possibly older than this validation existed),
reports the same four conditions as non-blocking findings instead. This is the same split the read
layer already uses for the ledger files (`artifact_append.py` refuses malformed input at write time;
`--doctor` degrades gracefully on read) — the roadmap now uses the identical two-tier posture, applied
to its own grammar.

### `Blocked by` lexical rules

*Back-link: [logic.md → An unresolvable blocker blocks — it never unblocks](./logic.md#job-1--roadmap-and-whats-next),
[logic.md → Satisfaction is an allowlist](./logic.md#job-1--roadmap-and-whats-next)*

`SCHEMA:` on-disk rendering (unchanged style from every other field) —
```markdown
- **Blocked by**: BUG-3, DEFER-7
```
Absent field = no blockers (matches the existing "empty optional field omitted" convention proven by
`tests/test_artifact_append.py:60-82`).

`REGEX:` token split — `re.split(r'\s*,\s*', value.strip())`. Each token must then fully match
`^(BUG|DEFER|TEST)-\d+$` (`re.fullmatch`) or it is malformed.

| Rule | Behavior |
|---|---|
| **Separator** | Comma, optional surrounding whitespace. No other separator recognized (a `;`- or newline-joined list is entirely malformed — one token that fails the ID regex). |
| **Whitespace** | Stripped at token boundaries only. Internal whitespace inside a token (`BUG - 3`) fails the fullmatch — malformed, not normalized. |
| **Case** | Header must be uppercase (`BUG`/`DEFER`/`TEST`) — case-sensitive, never normalized. **Tech-spec call (logic.md silent):** entry IDs are always upper-case by construction (`SCHEMAS[*]["header"]`, `bin/artifact_append.py:16,34,51`); accepting `bug-3` and silently uppercasing it would let two spellings of the same reference draft differently in different sessions, for no benefit. |
| **Malformed token** | Treated identically to an unknown ID (below) — fail-closed, blocks, never silently dropped. Reported as `DANGLING` with `reason="malformed token"`. |
| **Duplicate IDs in one field** | `Blocked by: BUG-3, BUG-3` — de-duplicated for satisfaction purposes (semantically a no-op), and separately reported as `BLOCKED_BY_DUPLICATE` (low severity — a hygiene hint, not a correctness issue, since dedup makes it behaviorally identical to listing once). |
| **Self-reference** | `BUG-7` naming itself. **Subsumed by cycle detection** (below) as a length-1 cycle — needs no special-case code. While `BUG-7` is `open`, `ready(BUG-7)` requires `BUG-7` to already be `closed`/`wontfix`/`superseded`, which is impossible while it's still `open`; it can only exit via `decide`, which doesn't consult blockers at all ([logic.md → decide may be invoked from any non-terminal state](./logic.md#command-surface)). |
| **Unknown ID** | Entry does not exist in any ledger file. Locked: fails closed, `DANGLING` finding, never reads as satisfied ([logic.md → An unresolvable blocker blocks](./logic.md#job-1--roadmap-and-whats-next)). |
| **`PROPOSAL-N` reference** | **Rejected outright** — see next paragraph. Reported as `BLOCKED_BY_PROPOSAL`, treated as `DANGLING` for satisfaction purposes (blocks, never satisfies). |
| **Cycle** (length ≥ 2, or self-reference as length 1) | Every member stays blocked — no special-casing needed for *correctness* (see below); `--doctor` additionally runs a dedicated detection pass for *diagnosis*. |

**Why `PROPOSAL-N` is rejected as a blocker target — a landmine this document closes before it ships.**
`proposals.md` entries render their own `- **Status**: [proposed / accepted / rejected /
superseded]` field (`templates/proposals.md:9`) — the *same field label* the PM lifecycle uses on
`BUG`/`DEFER`/`TEST` entries, but with an incompatible value vocabulary. `superseded` is a **legal
value in both vocabularies**. A blocker-satisfaction check that naively reads *any* referenced
entry's `Status` field and string-matches against the allowlist (`closed`/`wontfix`/`superseded`)
would treat `Blocked by: PROPOSAL-5` as satisfied the moment a human marks that proposal
`Status: superseded` — an accidental satisfaction that has nothing to do with the PM lifecycle
`PROPOSAL-5` was never enrolled in. `logic.md` doesn't discuss blocking-by-proposal at all; this
tech spec closes the gap by disallowing it entirely, consistent with the locked rule that "PM
lifecycle commands reject `PROPOSAL` entries" ([logic.md → In scope for
v1](./logic.md#in-scope-for-v1)) extended to the blocker graph, not just the five lifecycle
subcommands.

**Cycle detection is a `--doctor`-only pass, decoupled from the `ready()` hot path — and this is
not a compromise, it falls out of the design for free.** `logic.md` locks two things that appear to
be in tension: readiness "uses direct blockers only... there is no graph walk in the read path"
([logic.md → Readiness uses direct blockers only](./logic.md#job-1--roadmap-and-whats-next)), yet
cycles must be caught somehow. The resolution: **`ready(e)` needs no cycle-awareness to be
*correct***. If `BUG-1` is blocked by `BUG-2`, and `BUG-2` is blocked by `BUG-1`, then
`ready(BUG-1)` directly requires `BUG-2` to be `closed`/`wontfix`/`superseded` — which it can never
be while it's itself blocked on `BUG-1` — so `BUG-1` simply, correctly, never becomes ready. No
special handling is needed for the O(1)-per-entry hot path to be right; a cycle just means "correctly
stuck," which is the intended behavior for a real cycle. `--doctor`'s `CYCLE` finding is therefore a
pure diagnostic convenience layered on top, not a correctness requirement:

`PSEUDOCODE (justified, ≤3 lines):` `--doctor` builds one directed graph (edge: entry → each of its
`Blocked by` targets) across all `BUG`/`DEFER`/`TEST` entries regardless of status, then runs a
bounded DFS with a recursion-stack set; revisiting a node already on the stack reports the stack
slice from that node as one `CYCLE` finding (deduped by rotation). This needs justifying only because
"detect a cycle" is a well-known but non-trivial graph algorithm — prose alone invites an
accidentally-quadratic or non-terminating reimplementation.

### Field rendering — `Status`, `Probe`, `Handoff`

*Back-link: [logic.md → Data flow → Job 2](./logic.md#job-2--ushering-a-started-task),
[logic.md → Decisions Locked → Completion evidence](./logic.md#decisions-locked)*

All three are **single-valued fields, overwritten in place on every transition** — never duplicated,
consistent with `bin/artifact_review.py:29`'s existing dict-collapse of repeated labels, and with
`logic.md`'s own statement that history survives only via the attempt/refusal *counters*, not field
duplication ([logic.md → Attempt and refusal counts are aggregates, not a
history](./logic.md#job-2--ushering-a-started-task)). `logic.md`'s worked examples in its Data flow
section are illustrative, not literal — e.g. the `closed` example line omits `attempt N`
(`logic.md:376`) where the `delivered` line includes it (`logic.md:369`); this document fixes one
literal grammar covering every state, always including the attempt number, since dropping it at
exactly the state most likely to be read much later would lose the retry-visibility counters exist
to provide.

`SCHEMA:` `Status` field, one line per state (absent field = `open`, unchanged v1 semantics):

| State | Literal rendering |
|---|---|
| `open` | *(field absent — never rendered)* |
| `in_progress` | `- **Status**: in_progress — 2026-08-05 — attempt 1` |
| `in_progress`, after ≥1 refused `finish` | `- **Status**: in_progress — 2026-08-05 — attempt 1 — refused 2` |
| `delivered` | `- **Status**: delivered — 2026-08-05 — attempt 1 — commit: 9a3f21c` |
| `closed` | `- **Status**: closed — 2026-08-06 — attempt 1 — integrated: 9a3f21c` |
| `wontfix` | `- **Status**: wontfix — 2026-08-05 — attempt 1 — reason: superseded by redesign` |
| `superseded` | `- **Status**: superseded — 2026-08-05 — attempt 1 — reason: folded into BUG-12 — by: BUG-12` |

The date is always the date of *that* transition (start date for `in_progress`, finish date for
`delivered`, reconcile date for `closed`, decide date for `wontfix`/`superseded`) — never the
original `start` date once the entry has moved past its first transition. The refusal count is
appended only when non-zero, keeping the common (never-refused) case terse, matching every other
worked example in `logic.md`.

`SCHEMA:` `Probe` field. At `start`:
```markdown
- **Probe**: test:tests/test_auth.py::test_safari — baseline: fail — spec#a1b2c3d4 file#e5f6a7b8
```
Rewritten in place at `finish` (never a second field line — see the single-valued rule above):
```markdown
- **Probe**: test:tests/test_auth.py::test_safari — baseline: fail — spec#a1b2c3d4 file#e5f6a7b8 — final: pass — spec#a1b2c3d4 file#e5f6a7b8
```
`grep:` baseline additionally names every file that matched (needed for the finish-time
still-exists check — see [§The probe execution contract](#the-probe-execution-contract)):
```markdown
- **Probe**: grep:TODO_AUTH -- src/auth/ — baseline: 3 matches in 2 files (src/auth/login.py, src/auth/session.py) — spec#a1b2c3d4
```
`none` never changes across the lifecycle and carries no hash (nothing to hash):
```markdown
- **Probe**: none
```

**Tech-spec call (logic.md silent):** `logic.md`'s worked example shows 4-hex-character hash
fragments (`spec#a1b2`, `file#c3d4`, `logic.md:357`) with no stated algorithm or length — these read
as placeholder text, not a literal spec. This document picks `sha256`, truncated to the first 8 hex
characters, computed over (a) the raw `--probe` argument string for `spec#`, and (b) for `test:`
probes only, the UTF-8 bytes of the nodeid's source file (everything before `::` in the nodeid) for
`file#`. Truncated-hash collision risk is irrelevant under the cooperative-worker threat model — this
digest is provenance for a markdown diff a human reads, not a security boundary
([logic.md → Threat model](./logic.md#threat-model-cooperative-worker-not-adversarial)).

**Why `spec#` is re-hashed at `finish` even though the probe spec string is immutable post-`start`**
(`finish` takes no `--probe` argument — [logic.md → Command
surface](./logic.md#command-surface)): the *string* can't change through the CLI, but nothing stops a
worker from hand-editing the `Probe:` line directly in the ledger markdown (the design doesn't
prevent worktree-side markdown edits — [logic.md → Known
limits](./logic.md#known-limits)). Re-hashing and comparing at `finish` catches exactly that
accident — a `spec#` mismatch means the `Probe:` line's verb/arg text was edited between `start` and
`finish`, and it's flagged, never blocked, consistent with every other hash check in this design.

`SCHEMA:` `Handoff` field:
```markdown
- **Handoff**: quirk @ pm/bug-7 — /Users/…/worktrees/bug-7 — repo:/Users/…/origin-quirk
```
Three components: `<dest-repo-label> @ <branch> — <worktree-abs-path> — repo:<origin-abs-path>`.

**Tech-spec call (logic.md silent) — resolving an internal tension between the worked example and
the functional requirement.** `logic.md`'s worked example literally renders the third component as
`repo:<origin-abs-path>` (`logic.md:357`), but its Scope section separately states "`reconcile` reads
the repo path from it to know where the delivered commit can be resolved" ([logic.md → In scope for
v1](./logic.md#in-scope-for-v1)) — which only makes sense if that path names the *destination*
(reconcile always runs *in* the origin already, so recording the origin's own path on itself would
be functionally inert for that purpose). This document resolves it by observing the two components
serve two different, non-conflicting jobs, and keeping both:

- `<worktree-abs-path>` is what `finish`'s worktree-root precondition compares CWD against, **and**
  what `reconcile` actually runs its `git -C <worktree-abs-path> ...` commands against. It is a
  valid checkout of the destination repo regardless of whether dispatch was same-repo or
  cross-project — `reconcile`'s functional requirement is satisfied by this component alone; no
  separate "destination repo path" field is needed.
- `repo:<origin-abs-path>`, exactly as `logic.md`'s worked example literally renders it, is
  self-identifying provenance — useful when the entry text is copied verbatim into the handoff
  packet and read far from its origin context (the packet's own separate "ledger address" field
  already carries this too; this is deliberate redundancy, not a bug, matching the design's stated
  preference for a false report being *visible* over being merely non-duplicated).

`logic.md` states three `finish` preconditions (worktree root, clean tree, probe passes —
[logic.md → Decisions Locked → Completion evidence](./logic.md#decisions-locked)) and no fourth
"origin path must match `repo:`" check. This document does not add one — see
[§Concerns](#concerns).

`<dest-repo-label>` is the basename of the resolved destination repo root (`Path(dest_root).name`) —
display-only, never parsed back by any code path.

`<branch>` follows the naming convention the worked example itself fixes:
`pm/<header-lowercase>-<id>`, e.g. `pm/bug-7`.

---

## Contracts & interfaces

*Back-link: [logic.md → The division of labor is the whole design](./logic.md#the-division-of-labor-is-the-whole-design)*

### `bin/artifact_lib.py` — public surface

Covered above under [§Parser strict vs. compatibility modes](#parser-strict-vs-compatibility-modes)
for the parsing primitives. Additional exports:

`CONTRACT:`
```python
SCHEMA_VERSION: int = 2

def hash_probe_spec(spec: str) -> str: ...          # sha256(spec.encode())[:8].hex()
def hash_file(path: Path) -> str | None: ...          # sha256 of file bytes, None if unreadable
def atomic_write(path: Path, text: str) -> None: ...   # temp file in same dir + os.replace()
def field_line(label: str, value: str) -> str: ...     # "- **{label}**: {value}"
def splice_field(entry: Entry, label: str, value: str, full_text: str) -> str: ...
    # returns full_text with `label`'s field line replaced in place if present,
    # else inserted immediately before the entry's trailing blank line.
```

`atomic_write` is the crash-safety primitive shared by every writer added in this document
(`pm.py`'s lifecycle transitions and `migrate`) — see [§The CAS transition
mechanism](#the-cas-transition-mechanism) for why this supersedes the plain `target.write_text(...)`
`artifact_append.py:203` uses today (kept as-is there; see [DO-NOT-CHANGE
fences](#do-not-change-fences)).

### `bin/pm.py` — CLI surface

`CONFIG:` top-level dispatch —
```
pm.py next      [--project-dir P]
pm.py start     ID --probe VERB:ARG [--repo SEL] [--here] [--project-dir P]
pm.py finish    ID [--project-dir P]
pm.py park      ID --reason TEXT [--project-dir P]
pm.py decide    ID --as wontfix|superseded --reason TEXT [--by ID] [--project-dir P]
pm.py reconcile [--verify] [--project-dir P]
pm.py roadmap   --show | --write PATH  [--project-dir P]
pm.py status    [--project-dir P]                 # = index output + doctor output, concatenated
pm.py index     [--project-dir P]                 # also reachable as the bare flag: pm.py --index
pm.py doctor    [--project-dir P]                 # also reachable as the bare flag: pm.py --doctor
pm.py migrate   [--project-dir P]
```
**Tech-spec call (logic.md silent):** `logic.md`'s own Read-layer prose invokes `pm.py --index`
literally ([logic.md → The read layer](./logic.md#the-read-layer)), while the Command Surface table
names `status` as the slash-command-facing verb producing "Index + doctor findings." Both are
honored: `--index`/`--doctor` are recognized as top-level flags (checked before subparser dispatch,
so `pm.py --index` and `pm.py index` are the same call), and `status` is a third subcommand that
concatenates both outputs for the richer conversational view.

`CONTRACT:` every subcommand handler has the shape
```python
def cmd_start(args: argparse.Namespace, adapter: Adapter) -> int: ...
```
returning the process exit code directly (`main()` never re-derives it) — matching the existing
convention in `bin/artifact_append.py:main` and `bin/adr_create.py:main`, where each guard clause
`return`s its own exit code inline.

### `bin/pm_adapter.py` — the adapter Protocol

*Back-link: [logic.md → The adapter contract](./logic.md#the-adapter-contract),
[logic.md → Amendments → Handoff](./logic.md#status--amendments)*

`CONTRACT:`
```python
@dataclass(frozen=True)
class WorktreeHandle:
    path: Path
    task_id: str | None          # None on the git-only fallback; see §The adapter, below

@dataclass(frozen=True)
class LaunchResult:
    run_id: str | None
    dispatch_id: str | None

@dataclass(frozen=True)
class SignalResult:
    sent: bool
    reason: str | None            # e.g. "sender_not_assignee" — never raised, always returned

class Adapter(Protocol):
    def create_worktree(self, repo: Path, name: str, base: str | None) -> WorktreeHandle: ...
    def launch(self, path: Path, prompt: str, task_id: str | None) -> LaunchResult: ...
    def signal_done(self, *, task_id: str | None, dispatch_id: str | None, outcome: str) -> SignalResult: ...
```

`create_worktree` **must not launch anything** — locked
([logic.md → The adapter contract](./logic.md#the-adapter-contract)). `signal_done` **never
raises** — every failure mode (no adapter, rejected by Orca, network error) resolves to
`SignalResult(sent=False, reason=...)`, because the signal is additive, never authoritative
([logic.md → Decisions Locked → Handoff](./logic.md#decisions-locked)); `pm.py finish`/`park` never
fail their own exit code because a signal didn't send.

**Resolving the dispatch-ID sequencing problem `logic.md` states it left open.** `logic.md`'s own
Amendments log: "orca `worker-start`'s requirement to run from a Run-bound coordinator terminal with
the dispatch ID only existing after launch — a Phase 3 sequencing problem" is listed under "Left
open and stated rather than solved" ([logic.md → Status &
amendments](./logic.md#status--amendments)) — not a Decisions Locked entry, so resolving its
mechanics is this document's job, not a locked-decision override. The packet is written **once,
before `launch`**, per the locked step order ("4. write the packet... 6. launch the worker" —
[logic.md → Job 2](./logic.md#job-2--ushering-a-started-task)). This is possible because the
run/task/dispatch IDs the packet's "return address" carries are explicitly **non-authoritative** —
"Recorded IDs do not authorize a completion signal from an arbitrary terminal" ([logic.md →
Decisions Locked → Handoff](./logic.md#decisions-locked)) — so nothing functional depends on them
being present at packet-write time:

- `run_id` and `task_id` **are** obtainable before `launch`: `run_id` via `orca orchestration
  run-current`, `task_id` via `orca orchestration task-create`, which has no launching side effect
  and is safe to run as part of `create_worktree`'s own adapter call (hence `WorktreeHandle.task_id`
  above) — decoupling task registration from worker launch, which the orca CLI already allows (they
  are separate commands: `src/cli/specs/orchestration.ts:127-141` for `task-create`,
  `src/cli/specs/orchestration-worker-specs.ts:3-31` for `worker-start`, in the `orca/hind`
  checkout).
- `dispatch_id` genuinely cannot exist before `worker-start` runs (`orca worktree create`
  intentionally omits `--agent`, so nothing launches yet — `logic.md`'s own locked constraint). The
  packet renders it as `pending — assigned at launch` (literal text) when unknown at write time.

This requires no second write to the packet and no race between "worker starts reading" and "pm.py
finishes writing" — the packet is complete (task/bar/ledger-address/write-back-contract are all
knowable pre-launch) except for one field that was never load-bearing.

### The adapter implementations

`CONTRACT:` **git-only fallback** (`NullAdapter` — the default, always-tested path, not a degraded
one):
```
create_worktree(repo, name, base) → COMMAND: git -C {repo} worktree add {path} -b pm/{name} {base or "HEAD"}
                                     → WorktreeHandle(path, task_id=None)
launch(path, prompt, task_id)      → prints `prompt` to stdout, returns LaunchResult(None, None)
signal_done(...)                   → SignalResult(sent=False, reason="no adapter")
```

`CONTRACT:` **orca adapter** — exact invocations, verified against `orca/hind`'s own CLI specs
(`src/cli/specs/core.ts:86-118` for `worktree create`, `src/cli/specs/orchestration-worker-specs.ts:3-31`
for `worker-start`, `src/cli/specs/orchestration.ts:45-73` for `send`):
```
create_worktree(repo, name, base):
  COMMAND: orca orchestration task-create --spec <task summary> --json
  COMMAND: orca worktree create --name {name} --repo {selector for repo} \
             [--base-branch {base}] --json
    # deliberately omits --agent — creation must not launch (locked)
  → WorktreeHandle(path=result.worktree.path, task_id=result.task.id)

launch(path, prompt, task_id):
  COMMAND: orca orchestration worker-start --task {task_id} \
             --worktree path:{path} --agent claude --json
    # --worktree path:<abs-path> targets the already-created worktree by its
    # "path:" selector (a valid worktree selector per orca/hind's own
    # documented selector grammar — confirmed against
    # src/cli/bundled-skill-guides.ts's "Selectors:" list, which includes
    # `path:<absolutePath>`).
  → LaunchResult(run_id=<from `orca orchestration run-current --json`>,
                 dispatch_id=result.dispatch.id)

signal_done(task_id, dispatch_id, outcome):
  COMMAND: orca orchestration send --type worker_done --outcome {outcome} \
             --task-id {task_id} --dispatch-id {dispatch_id} --json
  → exit 0                              → SignalResult(sent=True, reason=None)
  → exit 1, lifecycle.action=="rejected" → SignalResult(sent=False, reason=lifecycle.code)
    # confirmed at orca/hind's src/cli/handlers/orchestration.ts:545-551: a
    # rejected lifecycle signal sets process.exitCode = 1 and the JSON body
    # carries `lifecycle: {action: "rejected", code: "sender_not_assignee", ...}`
    # for exactly the foreign-pane case logic.md names
    # (lifecycle-reconciliation.test.ts:178-207 in that checkout).
  → any other non-zero exit             → SignalResult(sent=False, reason="adapter error: " + stderr)
```
Every `signal_done` failure mode — rejected, adapter error, no adapter at all — is swallowed into
`SignalResult(sent=False, ...)` and never raised or propagated as a `pm.py` exit-code failure,
per the "additive, never authoritative" rule. `pm.py finish`/`park` log the reason to stderr as an
informational line only.

**`--repo <selector>` resolution.** Locked: `start` dispatches "to a new child worktree of the
current repo by default; `--repo` redirects" ([logic.md → Decisions Locked →
Handoff](./logic.md#decisions-locked)). **Tech-spec call (logic.md silent):** `--repo`'s value is
passed through unmodified to whichever adapter is active — the git-only fallback interprets it as an
absolute or relative filesystem path (`git -C <that path> worktree add ...`); the orca adapter passes
it verbatim as `orca worktree create --repo <value>`, which already accepts `id:`/`name:`/`path:`
selectors (`src/cli/help.ts:253`, that checkout). `pm.py` performs no selector parsing of its own —
it is not the thing that understands orca selector grammar, the orca CLI is.

---

## The probe execution contract

*Back-link: [logic.md → The red→green baseline](./logic.md#the-redgreen-baseline),
[logic.md → What red→green does not prove](./logic.md#what-redgreen-does-not-prove)*

`CONFIG:` `QUIRK_PM_PROBE_TIMEOUT` (seconds, default `120`) bounds every probe execution.
`QUIRK_PM_TEST_RUNNER` (default `"python3 -m pytest"`) is the command prefix for `test:` probes,
`shlex.split()`-parsed then `+ [nodeid]`.

**Tech-spec call (logic.md silent):** `logic.md`'s probe table names `test:<nodeid>` and shows
pytest-nodeid-shaped examples throughout (`tests/test_auth.py::test_safari`) without stating a
runner. This document commits `test:` to pytest by default, configurable via
`QUIRK_PM_TEST_RUNNER` for a target project using a different suite (nodeid syntax then follows
whatever that runner expects — `pm.py` never parses the nodeid itself, only passes it through).
Non-pytest, non-Python target projects are a known limitation of the v1 default — noted in
[§Concerns](#concerns), not solved here.

### `test:<nodeid>` outcome mapping

Empirically verified against the installed `pytest 8.4.2` in this repo (missing-node, failing,
erroring, and passing cases each run directly):

| pytest exit code | Meaning | Recorded outcome |
|---:|---|---|
| 0 | all requested tests passed | `pass` |
| 1 | test(s) ran and failed — pytest does not distinguish an assertion failure from an unhandled exception at the exit-code level, and this contract doesn't either | `fail` |
| 4 | usage error — includes `ERROR: not found: <nodeid>` | `missing` |
| 5 | no tests collected (nodeid resolved a file but not a specific test) | `missing` |
| 2, 3, or `subprocess.TimeoutExpired` | interrupted / internal error / exceeded `QUIRK_PM_PROBE_TIMEOUT` | `error` |

**At `start`:** any outcome other than `pass` is an acceptable baseline (`fail`, `missing`, or
`error`) — `start` refuses only when the probe already `pass`es
([logic.md → Probe already green at start](./logic.md#scenarios)). **Tech-spec call (logic.md
silent):** `missing` is accepted as a valid baseline deliberately — this is the ordinary
write-the-test-first flow (the worker's task is partly "write `test_safari`, then make it pass"),
which `logic.md` doesn't call out but doesn't forbid either; refusing it would block a legitimate TDD
usage the "red→green" framing itself suggests. At `finish`: `pass` is the only passing outcome;
`fail`, `missing`, and `error` all refuse — matching the locked table exactly (`test:` "refuses when
node missing, errors, or fails" — [logic.md → The red→green
baseline](./logic.md#the-redgreen-baseline)).

### `grep:<pattern> [-- <paths>]` outcome mapping

Implemented in pure Python (`re`, no shelling out to system `grep`, keeping the stdlib-only
constraint) — walks `paths` (default: worktree root) recursively, skipping `.git/`, skipping any
file that raises `UnicodeDecodeError` under UTF-8 (treated as binary, excluded). `pattern` is a
Python regex; a match is counted **per matching line** (`re.search` per line, one count per line
regardless of multiple matches on that line — matching conventional `grep -c` semantics, not
`grep -o`'s per-occurrence count). Both `pattern` and every path are passed through `shlex.quote()`
whenever rendered into the literal `finish` command shown in the handoff packet — closing the
round-1 review's "generating a literal shell command from an arbitrary pattern/path requires
escaping that is not specified" finding directly (`review-2026-08-05-codex.md` → packet finding).

At `start`: scan, record `baseline_count` and the sorted list of every distinct file with ≥1 match.
Refuse if `baseline_count == 0` (matches nothing — the pattern doesn't discriminate this entry).
Record the file list inline in the `Probe:` field ([§Field rendering](#field-rendering--status-probe-handoff)).

At `finish`: re-scan the same `pattern`/`paths`. First, check every file in the recorded baseline
list still exists — if any is missing, refuse regardless of count ("deleting the code that carried
the symptom is not a fix" — [logic.md → The red→green
baseline](./logic.md#the-redgreen-baseline)). Then require `final_count == 0`.

### `none`

Never executed. `start` records `Probe: none` and skips baseline entirely. `finish` records nothing
new on the `Probe:` line (it never changes across the lifecycle — see [§Field
rendering](#field-rendering--status-probe-handoff)) and always "passes" the probe step, subject to
the other two `finish` preconditions (clean tree, worktree root) still applying in full.

---

## The CAS transition mechanism

*Back-link: [logic.md → Two PMs in different origin worktrees](./logic.md#scenarios),
[logic.md → Decisions Locked → Completion evidence → CAS](./logic.md#decisions-locked)*

Every `pm.py` command that mutates an entry (`start`, `finish`, `park`, `decide`, and `reconcile`'s
write-back phase) follows one procedure:

`PSEUDOCODE (justified, ≤3 lines):` acquire `flock` on `.{TARGET_FILE}.lock` (the **same** lock file
`artifact_append.py:165` already uses for that ledger file — this is what serializes `pm.py` against
concurrent `artifact_append.py` appends to the same file, not a new lock namespace); read, locate the
entry by ID via strict `parse_entries`, check `entry.status in EXPECTED_FROM_STATES[command]`; on
match, splice the new field lines and `atomic_write`; on mismatch, refuse without writing. This needs
justifying (not left to "obviously implement CAS") because "compare-and-swap" is a well-known pattern
whose correctness depends entirely on the compare and the write happening inside one held lock —
stated as prose alone, it invites a read-then-later-write race exactly like the one it exists to
close.

| Command | Requires current state | Produces | Attempt handling |
|---|---|---|---|
| `start` | `open` (absent Status), and no other `Entry` with the same ID (§Parser) | `in_progress` | attempt = 1, or previous attempt + 1 if this ID was `park`ed before |
| `finish` | `in_progress` | `delivered` (preconditions pass) or stays `in_progress` with `refused` incremented | unchanged |
| `park` | `in_progress` | `open` (Status field **removed** — matches v1 absent-means-open) | attempt number preserved via a comment `logic.md` doesn't require persisting past `open`; see [§Concerns](#concerns) |
| `decide` | any non-terminal state (`open`, `in_progress`, `delivered`) | `wontfix` \| `superseded` | unchanged |
| `reconcile` (write-back only) | `delivered`, **same** recorded commit sha as when the promotion was computed | `closed` | unchanged |

**Why "attempt" isn't a caller-supplied compare key.** `finish`/`park` take no `--attempt` flag —
there is exactly one live attempt per entry at a time under the courtesy-check model (`start`
refuses on an already-`in_progress` entry — [logic.md → Two workers dispatched for the same
entry](./logic.md#handoff-scenarios)), so "compare-and-swap on `(ID, attempt, expected status)`"
([logic.md → Decisions Locked](./logic.md#decisions-locked)) reduces in practice to comparing
`expected status` alone, with `attempt` carried forward unchanged by every command except `start`
(which increments it) — there is no scenario where a caller needs to assert a *specific* attempt
number to guard against, because the status comparison already rejects any state the caller didn't
expect.

**`park` and the "attempt number preserved" question.** `logic.md` requires `park` to "return to
`open`, keep the attempt on record" ([logic.md → Command
surface](./logic.md#command-surface)) — but `open` is defined as *absent* `Status` field
throughout this design, which has nowhere to keep an attempt number once the field is gone.
**Tech-spec call (logic.md silent):** "keep the attempt on record" is satisfied by the **refusal
count and attempt number `start` re-reads and increments on the *next* `start`** — i.e., "on record"
means "recoverable from the next transition," not "visible while `open`." A subsequent `start` on the
same ID computes its new attempt number as `(highest attempt number this ID has ever recorded, read
from git history if needed) + 1` — but since the current, un-parked Status line is gone once parked,
`pm.py` cannot read the prior attempt number from the *current* file state at all. Given `logic.md`
explicitly accepts that "a later `start` overwrites `Probe` and `Handoff` for the new attempt and the
earlier values are gone. Git history holds the prior values for anyone who needs them" ([logic.md →
Attempt and refusal counts are aggregates](./logic.md#job-2--ushering-a-started-task)), this document
makes the parallel call for the attempt *number* itself: after `park`, the next `start` on that ID
begins again at **attempt 1** — a fresh, visible attempt count that undercounts the true historical
total, exactly as the entry's own text already does for `Probe`/`Handoff`. This is flagged explicitly
in [§Concerns](#concerns) rather than silently narrowed, since it is a real information loss beyond
what `logic.md`'s own "earlier values are gone" acknowledgment covers (that passage is about
`Probe`/`Handoff` being overwritten, not about the attempt counter resetting).

**Crash-mid-transition.** `atomic_write` (§`bin/artifact_lib.py`) writes the full new file content to
a temp file in the same directory, then `os.replace()` — atomic on POSIX. A crash before the replace
leaves the original file completely untouched (the orphaned temp file is inert); a crash after is
indistinguishable from a normal completed write. **Tech-spec call (logic.md silent):** this is a
strictly stronger version of the crash-safety property `logic.md` states for `migrate` specifically
("A partial run is safe to repeat, because the marker is written last" — [logic.md → In scope for
v1](./logic.md#in-scope-for-v1)) — sequential "marker last" ordering only prevents a *torn* file if
each individual write is itself atomic, which a plain `write_text()` call is not guaranteed to be
under power loss. `atomic_write` makes the whole rewrite indivisible, so there is no ordering to get
right in the first place. Every `pm.py` writer (lifecycle transitions and `migrate` alike) uses it;
`artifact_append.py`'s existing `target.write_text(new_text)` (`bin/artifact_append.py:203`) is left
untouched — see [DO-NOT-CHANGE fences](#do-not-change-fences).

`flock` itself needs no crash-recovery logic: it is process-scoped, so a killed process (even
`SIGKILL`) releases the lock automatically — there is no stuck-lock file to clean up, unlike a
PID-file-based lock.

**The known, accepted limit this doesn't fix.** Two PMs in two different origin worktrees hold two
different lock files on two different `BUGS.md` copies — CAS prevents the same-directory race, not a
cross-worktree one. This is locked, not a defect this document introduces or can close: "CAS is
retained because it does prevent the *same-directory* race... it is simply not a distributed lock"
([logic.md → Two PMs in different origin worktrees](./logic.md#scenarios)).

---

## The `migrate` algorithm

*Back-link: [logic.md → In scope for v1 → Schema version 2](./logic.md#in-scope-for-v1)*

Runs once per ledger file (`BUGS.md`, `DEFERRED.md`, `TEST_BACKLOG.md`, `proposals.md` — **all
four**, see the version-bump call below), independently, each under its own `flock`:

1. Acquire `.{file}.lock` (same lock namespace as every other writer of that file).
2. Read current text; `detect_schema_version` (absent marker treated as legacy v1, not an error).
3. If version `== 2`: no-op, report `"{file}: already v2"`, exit 0. If version `> 2`: refuse — this
   plugin doesn't understand a newer schema — exit 8, reusing the existing schema-mismatch code
   (`bin/artifact_append.py:184-190`'s convention).
4. If version `<= 1` (including absent): replace the `<!-- schema-version: N -->` line with
   `<!-- schema-version: 2 -->` (inserting one if entirely absent) and replace the schema-comment
   block with the v2 text (§Schema v2 templates, below). **Touches no entry body** — every existing
   `## BUG-N: ...` block is copied through byte-for-byte. For `TEST_BACKLOG.md` specifically: the
   schema comment's field list gains `Logged`, but **no existing `TEST-N` entry is backfilled with a
   `Logged` date** — entries predating migration simply have none, which is the intended, already-locked
   behavior ("Entries predating the migration have no date. They sort as oldest" — [logic.md → Age
   needs one comparable scale across types](./logic.md#job-1--roadmap-and-whats-next)).
5. `atomic_write` the whole file in one `os.replace()`. **Tech-spec call (logic.md silent):** `logic.md`
   states the crash-safety mechanism as "the marker is written last" — this document instead performs
   the entire rewrite (comment block *and* marker) as one atomic swap, which is a strictly stronger
   version of the same guarantee: there is no partially-written state observable at all, rather than a
   partially-written state that happens to always read as "not yet migrated." See the identical
   argument in [§The CAS transition mechanism](#the-cas-transition-mechanism) — this is the same
   primitive, applied to the same class of problem.

**`proposals.md` also bumps to schema-version 2**, even though it gains no new fields and its schema
comment text is otherwise unchanged. **Tech-spec call (logic.md silent):** `logic.md` states
`proposals.md` "gains none of them" (the new PM fields — [logic.md → In scope for
v1](./logic.md#in-scope-for-v1)), which this document reads as "no new *fields*," not "no version
bump." Keeping all four ledger files on one shared version number avoids a permanently-special-cased
"this one file never advances" rule every future migration has to remember, for a one-line comment
change with zero behavioral cost (`proposals.md` was never in the mixed-version hazard `logic.md`
warns about in the first place, since it never gained lifecycle semantics to be mismatched about).

`ROADMAP.md` is **created**, not migrated, by `artifact_init.py` (`bin/artifact_init.py:38-48`'s
existing per-file create-or-skip loop gains one more entry) — a project with no `ROADMAP.md` simply
has an empty roadmap; `migrate` never needs to touch it, since it doesn't pre-exist.

### Schema v2 templates

`SCHEMA:` new schema-comment block for `templates/BUGS.md` (the other two ledger files follow the
identical shape — `Blocked by` and `Status`/`Probe`/`Handoff` documented once, `Logged` additionally
for `TEST_BACKLOG.md`):

```markdown
<!-- schema-version: 2 -->
<!-- BUGS.md SCHEMA (append only — do not rewrite existing entries)
Entry format:
## BUG-[N]: [Short title]
- **Observed**: [date or session ID]
- **File**: [path/to/file.ts:line]
- **Description**: [what the bug is]
- **Introduced by**: [this session / unknown / commit SHA]
- **Severity**: [critical / high / medium / low]
- **Proposed fix**: [one sentence]
- **Blocker for**: [what this would break]
- **Blocked by**: [comma-separated BUG-N/DEFER-N/TEST-N, or omit]

Required fields: title, file, description, severity.

The fields below are written only by pm.py — never by hand, never via
artifact_append.py. Absent Status means open.
- **Status**: [in_progress / delivered / closed / wontfix / superseded — see /quirk:pm:status]
- **Probe**: [set at `pm start`, updated at `pm finish`]
- **Handoff**: [set at `pm start` when dispatched]
-->
```

`SCHEMA:` `TEST_BACKLOG.md` additionally gains, in its required-fields comment block:
```markdown
- **Logged**: [date, auto-stamped like Observed/Deferred/Proposed on every other type]
```

`proposals.md`'s comment block is otherwise byte-identical to today's, with only the version marker
line changed.

### v1/v2 back-compat matrix

*Back-link: [logic.md → Additive; zero migration was wrong](./logic.md#in-scope-for-v1)*

| Scenario | Read commands (`--index`, `--next`, `--doctor`, `--status`) | Write commands (`start`/`finish`/`park`/`decide`/`reconcile`/`roadmap --write`) |
|---|---|---|
| v1 file, v2 plugin, not yet migrated | Work unmodified — every entry has no `Status` field, which already means `open` under both schema versions. No degradation, because v1 files are a strict subset of what v2 read-paths already handle. | **Refuse, exit 8**, instructing `/quirk:pm:migrate`. Writing a `Status`/`Probe`/`Handoff` line onto a file still marked v1 is exactly the mixed-version hazard `logic.md` names as the reason "additive; zero migration" was retracted ([logic.md → In scope for v1](./logic.md#in-scope-for-v1)) — a v1-only reader (an older `artifact_append.py`/`artifact_review.py` from before this work) would silently disagree with what the file now contains, with the version guard never firing to catch it. |
| v2 file, v1 plugin (a project rolled back to a pre-PM quirk install) | `artifact_append.py`'s existing `version > EXPECTED_SCHEMA_VERSION` guard (`bin/artifact_append.py:184-190`) already refuses with exit 8 — no new code needed; the mechanism generalizes automatically once `EXPECTED_SCHEMA_VERSION` bumps from 1 to 2. | Same — the v1 `artifact_append.py` refuses before ever writing. |
| Fresh project, `/quirk:artifacts:init` never run | Same "run `/quirk:artifacts:init` first" message every `bin/*.py` script already gives on a missing target file (`bin/artifact_append.py:157-163`) — reused verbatim, exit 3. | Same, exit 3. |

---

## The `reconcile` algorithm

*Back-link: [logic.md → Delivered is what the worker reported; closed is what the origin
observed](./logic.md#delivered-is-what-the-worker-reported-closed-is-what-the-origin-observed)*

**Slow work (git I/O) never happens while the artifact-file lock is held.** `reconcile` first
computes, read-only and lock-free, which entries *should* promote; only the final write-back
(updating `Status:` lines) takes the lock, briefly. **Tech-spec call (logic.md silent):** `logic.md`
doesn't state this ordering, but holding a `flock` across a network fetch would make every other
`pm.py`/`artifact_append.py` operation on that file block on network latency — an availability
regression this document avoids as a straightforward consequence of not inventing new lock-hold
duration where none is required.

```
PSEUDOCODE (justified, ≤3 lines): for each `delivered` entry (read once, strict parse, no lock
held): resolve Handoff.worktree_path; if missing on disk → "cannot evaluate — worktree missing";
else `git -C path fetch origin` (cache per unique path this run) then resolve integration_ref
(QUIRK_PM_INTEGRATION_REF, else `origin/HEAD`, else current branch — locked fallback chain) then
`git -C path merge-base --is-ancestor <sha> <integration_ref>`, mapping its exit code per the
three-way table below. This needs justifying because the "fetch once per repo, not once per entry"
memoization and the fetch-before-resolve-ref ordering are easy to get backwards and silently produce
stale results.
```

| `merge-base --is-ancestor` exit | Meaning | Recorded (locked, [logic.md →
Delivered is what the worker reported](./logic.md#delivered-is-what-the-worker-reported-closed-is-what-the-origin-observed)) |
|---:|---|---|
| 0 | reachable | promote to `closed` |
| 1 | known, not reachable | stays `delivered`; doctor: `AWAITING_INTEGRATION`, "N days" |
| 128 | object unknown in this checkout | stays `delivered`; doctor: `CANNOT_EVALUATE`, "commit not in this repo" |
| worktree path missing | *(not a git exit — checked before the git call)* | stays `delivered`; doctor: `CANNOT_EVALUATE`, "worktree missing" |
| fetch failed | *(checked before the git call)* | stays `delivered`; doctor: `CANNOT_EVALUATE`, "fetch failed" |
| any other exit | unexpected git failure | stays `delivered`; doctor: `CANNOT_EVALUATE`, "git error: {stderr excerpt}" — never promoted on an ambiguous signal |

Rebase/cherry-pick/squash (commit identity broken, ancestry legitimately returns false for landed
work): reported identically to plain "not reachable" (`AWAITING_INTEGRATION`) — there is no separate
detection for this case, because the removed commit-message-search fallback was the only mechanism
that could have distinguished it, and it was removed as unbounded and unsafe ("an old commit, a
revert, or a doc merely mentioning `BUG-7` could close the entry" — [logic.md → Rebase, cherry-pick,
and squash all break commit identity](./logic.md#delivered-is-what-the-worker-reported-closed-is-what-the-origin-observed)).
A human resolves these via `decide` once they confirm the work landed by other means.

**Write-back is itself CAS-guarded**, closing the gap between the read-only computation pass and the
locked write: an entry is promoted only if, *at write time under the lock*, it is still `delivered`
with the **same** recorded commit sha the read pass computed against. If a racing `park`/`decide`
(or a hand-edit) changed it in the interim, that entry is silently skipped this run — the underlying
git facts don't change, so the next `reconcile` invocation re-evaluates it correctly.

**`--verify`.** After exit-0 ancestry confirms closure, additionally: `git -C worktree_path worktree
add --detach <tmpdir> <integration_ref>`, re-run the entry's recorded probe against `<tmpdir>`,
`git -C worktree_path worktree remove <tmpdir> --force` in a `finally` block. A failing re-run does
**not** un-promote the entry — reachability alone is the default and the entry is already correctly
`closed` by that definition; a `--verify` failure adds a `--doctor` `POST_MERGE_PROBE_REGRESSION`
finding instead. Locked: "the default is reachability alone, because CI is the right place to catch a
post-merge regression" ([logic.md → Reachability proves the change landed, not that it
survived](./logic.md#delivered-is-what-the-worker-reported-closed-is-what-the-origin-observed)) — a
stricter `--verify` gate that could *block* closing would contradict that.

---

## The read layer — `index` / `status` / `doctor`

*Back-link: [logic.md → The read layer](./logic.md#the-read-layer)*

`hooks/load_artifact_tail.sh` is rewritten to call `pm.py --index` (replacing its current `tail -n
50` loop, `hooks/load_artifact_tail.sh:31-33`) and print its stdout, preserving the existing
gates that must survive unchanged: `CLAUDE_PROJECT_DIR` unset → silent exit 0
(`hooks/load_artifact_tail.sh:9`), no artifact files present → the exact existing
"`/quirk:artifacts:init`" suggestion (`:18-20`), and the hook **always** `exit 0` regardless of
`pm.py`'s own exit code — any `pm.py --index` failure (including "not yet migrated," "not yet
initialized," or an uncaught exception) is caught by the wrapping shell and replaced with a one-line
`"[quirk:pm] index unavailable"` fallback rather than ever propagating a non-zero exit out of the
hook.

**Bounded rendering — closing the round-1/round-2 review gap that the final logic spec still marks
`partial`** ("only 'the current' task is shown; bounded lists, all in-progress work, caps, and parse
fallback remain unspecified" — `review-2026-08-05-codex-round2.md`, closure-audit row 16).
**Tech-spec call (logic.md silent):** `logic.md` names *what* the index carries (counts with a
denominator, the current in-progress task, closed count + evidence mix — [logic.md → The read
layer](./logic.md#the-read-layer)) without specifying the literal bounded-list rendering; this
section is exactly the kind of implementation-detail gap the tech spec exists to close.

`SCHEMA:` `--index` output (plain text, one message block per hook convention):
```
[quirk:pm] BUGS 3 open (1 blocked) · DEFERRED 5 open · TEST 2 open · 4 unplaced (2 ready, 1 blocked, 1 malformed)
[quirk:pm] in_progress (2 shown / 2 total):
  - BUG-7 auth fails on safari — started 2026-08-01 (4d ago) — worktree: /Users/…/worktrees/bug-7
  - DEFER-3 rethink session storage — started 2026-07-30 (6d ago) — STALLED
[quirk:pm] delivered, awaiting integration (1 shown / 1 total):
  - BUG-2 auth cookie fix — delivered 2026-08-04 (1d ago)
[quirk:pm] closed 12 total (9 probed, 3 unverified/none)
[quirk:pm] doctor: 2 findings — run /quirk:pm:status for details
```
Caps: up to 10 `in_progress` rows and up to 5 `delivered`-awaiting-integration rows, each with title
truncated to 60 characters; beyond the cap, a trailing `"…and N more"` line — a bounded, ID-based
projection replacing the byte-count/line-count cap the current hook uses
(`hooks/load_artifact_tail.sh:26-30`'s 1MB check), applied to a smarter selection instead of a raw
tail. A ledger file that fails to parse entirely is reported as `"[quirk:pm] {file}: parse error,
skipping"` and excluded from the counts — never a crash, mirroring the existing per-file resilience
posture.

`--doctor` output: one line per finding, grouped by the severity below, always `exit 0` regardless of
finding count (`--doctor` is explicitly read-only per the Command Surface table — non-zero-on-findings
for CI composition is listed under [logic.md → Deferred to later
versions](./logic.md#deferred-ideas)'s "`--doctor` in CI," out of scope for v1).

### Doctor findings catalog

| Finding | Severity | Meaning |
|---|---|---|
| `DANGLING` | warning | `Blocked by` names a nonexistent ID or a malformed token |
| `BLOCKED_BY_PROPOSAL` | warning | `Blocked by` names a `PROPOSAL-N` (disallowed — [§Blocked by lexical rules](#blocked-by-lexical-rules)) |
| `CYCLE` | warning | a blocking cycle detected (self-reference is a length-1 cycle) |
| `DUPLICATE_ID` | warning | two headings in one file claim the same ID |
| `MALFORMED_HEADING` | warning | a heading claims an ID with no title |
| `DANGLING_ROADMAP_REF` | warning | `ROADMAP.md` references an ID with no matching entry |
| `PROPOSAL_IN_ROADMAP` | warning | `ROADMAP.md` references a `PROPOSAL-N` |
| `ROADMAP_LINE_MALFORMED` | warning | a milestone bullet doesn't match the ID-only grammar |
| `DUPLICATE_MEMBERSHIP` | notice | an ID appears in more than one milestone |
| `DUPLICATE_MILESTONE_NAME` | notice | two milestones share a display name |
| `BLOCKED_BY_DUPLICATE` | notice | the same ID listed twice in one `Blocked by` field |
| `STALLED` | informational | `in_progress` with no status change for `QUIRK_PM_STALL_DAYS` (default 7) |
| `AWAITING_INTEGRATION` | informational | `delivered`, reconcile confirms not-yet-reachable |
| `CANNOT_EVALUATE` | informational | `delivered`, reconcile could not determine reachability (see [§reconcile](#the-reconcile-algorithm) table) |
| `UNVERIFIED_DELIVERY` | informational | `delivered`/`closed` via `--probe none` — see next paragraph |
| `PROBE_SPEC_CHANGED` / `PROBE_FILE_CHANGED` | notice | hash mismatch between baseline and finish |
| `POST_MERGE_PROBE_REGRESSION` | warning | `reconcile --verify` re-run failed against the integration ref |

**Resolving "self-authored evidence" against the deferred provenance field.** `logic.md`'s Key
Decisions section names "`--doctor` flags self-authored evidence" as its own bullet ([logic.md → Key
decisions & rationale](./logic.md#key-decisions--rationale)), while `Logged by` provenance stamping
(who authored an entry) is explicitly deferred, not v1 ([logic.md → Deferred to later
versions](./logic.md#deferred-ideas)) — with no provenance field, "who wrote this" cannot be detected
at all in v1. **Tech-spec call (logic.md silent):** this document reads "self-authored evidence" as
referring to the evidence *kind*, not entry *authorship* — a `--probe none` closure is definitionally
self-reported with no independently-passing check, which is precisely what `UNVERIFIED_DELIVERY`
already captures. No new provenance mechanism is introduced; the existing finding satisfies the
Key-Decisions bullet under this reading.

---

## Exit codes

*Back-link: [logic.md → Amendments → exit-code table deferred to tech.md](./logic.md#status--amendments)*

Continues `bin/artifact_append.py`'s scheme (2/3/5/8) and implements the code the original design
promised but never shipped (`docs/specs/2026-05-04-typed-artifacts-design.md:329`'s "Corrupt entry
mid-file → exit 4," absent from `bin/artifact_append.py:126-190`'s actual codes — confirmed absent).

| Code | Meaning | Reachable from |
|---:|---|---|
| 0 | success | every command |
| 1 | unexpected internal error (uncaught exception, caught at `main()` and reported without a traceback) | every command — the safety-net catch-all |
| 2 | bad argument / bad field value / malformed `ROADMAP.md --write` content | every command; `roadmap --write`'s grammar refusals ([§ROADMAP.md formal grammar](#roadmapmd-formal-grammar)) |
| 3 | target ledger/roadmap file missing, or entry ID not found | every command targeting a specific ID or file |
| 4 | corrupt/ambiguous entry — malformed heading claiming the requested ID, or duplicate ID | `start`, `finish`, `park`, `decide` |
| 5 | lock timeout (`ARTIFACT_LOCK_TIMEOUT`, reused from `bin/artifact_append.py:166`) | every mutating command |
| 6 | CAS failure — entry not in the expected state for this transition (includes: `PROPOSAL` ID rejected) | `start`, `finish`, `park`, `decide`, `reconcile` write-back |
| 7 | project dir not found / not writable (reused from `bin/artifact_init.py`'s existing convention) | every command |
| 8 | schema-version mismatch — file newer than this plugin understands, or (write commands only) file not yet migrated to v2 | every command; `migrate` |
| 9 | probe refused — already green at `start`, or still failing at `finish` | `start`, `finish` |
| 10 | `finish` precondition failed — dirty tree, or worktree root doesn't match `Handoff` | `finish` |
| 11 | adapter/launcher failure — worktree creation or agent launch failed at the git/orca layer | `start` |

`reconcile` and `doctor`/`index`/`status` never return 4/6/9/10/11 in normal operation — they process
many entries and record per-entry outcomes in their *output*, not via aggregate process exit code, so
they stay safely composable/unattended (a script wrapping `reconcile` shouldn't fail just because
zero entries promoted this run). `--doctor` never exits non-zero for findings — see [§The read
layer](#the-read-layer--index--status--doctor).

---

## DO-NOT-CHANGE fences

*Back-link: [logic.md → bin/artifact_lib.py is extracted before any feature lands](./logic.md#key-decisions--rationale)*

| Region | Why fenced |
|---|---|
| `bin/artifact_append.py:203` (`target.write_text(new_text)`) | Left as a plain, non-atomic write deliberately — the "no behavior change" mandate on this refactor covers *parsing*, not a crash-safety upgrade nobody asked this script to gain; `pm.py`'s new writers use `atomic_write` instead, see [§The CAS transition mechanism](#the-cas-transition-mechanism). Backporting atomicity here is a defensible future improvement, not part of this work — see [§Concerns](#concerns). |
| `tests/test_artifact_append.py`, `tests/test_artifact_review.py` (entire files) | The acceptance bar for "no behavior change" in the parser convergence — every assertion in both must keep passing unmodified; see [§Parser strict vs. compatibility modes](#parser-strict-vs-compatibility-modes). |
| `tests/conftest.py`'s existing fixtures (`project_dir`, `initialized_project`, `run_script`, `BIN_DIR`, `TEMPLATES_DIR`, `REPO_ROOT`) | Load-bearing for both the typed-artifacts suite and this work; this document adds fixtures alongside them (§Testing strategy), never repurposes them. |
| `bin/artifact_init.py`'s existing `ROOT_TEMPLATES`/backup/`--force` logic (`bin/artifact_init.py:14,38-48`) | This work adds one entry to `ROOT_TEMPLATES` (`ROADMAP.md`) and nothing else in this file — the create-or-skip, backup-on-`--force`, and CLAUDE.md-snippet logic are unrelated to this feature and untouched. |
| `hooks/hooks.json` | Unchanged — this work modifies `load_artifact_tail.sh`'s body, not its registration; the `SessionStart`/`matcher: "*"` wiring (`hooks/hooks.json:14-22`) stays as-is. |
| `templates/claude_md_snippet.md` | Unrelated to PM; this work adds no new surface-routing tic phrases. |
| Every existing skill under `skills/` other than the new `skills/pm/` | Purely additive work; nothing here reads or writes another skill's files. |

---

## Always / Ask / Never

*Back-link: [logic.md → Threat model](./logic.md#threat-model-cooperative-worker-not-adversarial)*

**Always**

- Describe every check as a mistake-catcher in its own error text — never phrase a refusal as if it
  prevents deliberate circumvention. This is the threat model's own requirement, not a style
  preference: `logic.md` states "nowhere in this spec should a check be read as a guarantee."
- Route every artifact mutation — ledger fields and `ROADMAP.md` — through `bin/pm.py` or
  `bin/artifact_append.py`. Never `Edit`/`Write` an artifact file directly from a skill or command.
- Use `atomic_write` for every new write path this document introduces (`pm.py` lifecycle
  transitions, `migrate`). Never a plain `write_text()` on a ledger or roadmap file from new code.
- Compute `signal_done` results as a returned `SignalResult`, never a raised exception — a lost
  signal must never fail `finish`/`park`'s own exit code.
- Exit hooks (`load_artifact_tail.sh`) with 0 regardless of `pm.py`'s own exit code.

**Ask** (escalate to the user, not resolved unilaterally by a script)

- Roadmap ratification — `pm.py roadmap --write` performs the mechanical validated write; the
  conversation performs the ratification, per the locked "agent proposes, human ratifies" gate
  ([logic.md → Decisions Locked → Roadmap source](./logic.md#decisions-locked)).
- `decide` (`wontfix`/`superseded`) — human-gated, locked, never run unattended.
- Any conflict between this tech spec and a `logic.md` Decisions Locked entry discovered during
  implementation — amend `logic.md`'s Amendments log first, per the `writing-tech-spec` rubric's own
  feasibility-escalation rule, before changing this document.

**Never**

- Add a required third-party dependency — Python 3.9+ stdlib only, `git`/`orca` invoked via
  `subprocess`, never a binding.
- Let `pm.py` block on `signal_done` failing, or let a hook propagate a non-zero exit.
- Let `find_max_id` and `parse_entries` converge into one regex — see [§Parser strict vs.
  compatibility modes](#parser-strict-vs-compatibility-modes) for why they must stay two.
- Allow `Blocked by` to target a `PROPOSAL-N` entry — see the field-collision landmine in [§Blocked
  by lexical rules](#blocked-by-lexical-rules).
- Treat a `--verify` probe regression as grounds to un-close an already-`closed` entry.
- Rewrite an entry's *substance* fields (title, description, file, severity, etc.) from any `pm.py`
  code path — only `Status`/`Probe`/`Blocked by`/`Handoff` are ever mutated in place, per the
  append-only-substance / mutable-lifecycle split ([logic.md → Append-only applies to an entry's
  substance, not its lifecycle](./logic.md#key-decisions--rationale)).

---

## Cross-cutting

*Back-link: [logic.md → Known limits](./logic.md#known-limits)*

**Security.** None of this is a security boundary — restated because it is the single most
consequential fact in `logic.md` and the easiest one for an implementer to accidentally contradict by
phrasing a refusal message too confidently. No script here authenticates, authorizes, or sandboxes
anything; every check is a mistake-catcher against an honest worker's accidents. `secret_scan.py`-style
defense-in-depth (as `filing-requests` uses for its one genuinely irreversible action,
`github_file.py`) has no analog here, because nothing in this module performs an irreversible
outward action — `pm.py` never files an issue, pushes, or merges.

**Observability.** The entire v1 observability story is the ledger itself plus `--doctor`/`--index` —
no separate audit log, no `Logged by` provenance (deferred). A false report is visible in a diff and
in `--doctor`; that is the design's whole claim, restated at the implementation layer as: every
finding in the [doctor findings catalog](#doctor-findings-catalog) is computed fresh from the files
on disk, never cached, never trusted from a prior run.

**Data migration.** Covered in full under [§The `migrate`
algorithm](#the-migrate-algorithm) and [§v1/v2 back-compat matrix](#v1v2-back-compat-matrix).

**Rollback.** Every `pm.py` write is a full-file `atomic_write` — recoverable via `git checkout` on
the ledger/roadmap file like any other tracked change, same as today. `start`'s worktree creation has
no automatic rollback on a later failure (a probe that unexpectedly passes leaves the worktree in
place *deliberately*, per [logic.md → The created worktree is left in place](./logic.md#job-2--ushering-a-started-task));
an adapter failure during `launch` (exit 11) leaves the worktree created but the ledger still `open`
(the ledger write, step 5, happens *after* the probe runs but the exact ordering relative to `launch`,
step 6, means a `launch` failure is caught before the ledger is written — `start`'s internal sequence
in this document is: create → probe → **write ledger + packet** → launch, so a `launch` failure after
a successful probe leaves `in_progress` correctly recorded with an intact `Handoff`, recoverable by
re-running `launch` manually against the same worktree using the adapter's own CLI, or by `park`ing
and retrying `start --here` against the same code). This reordering (ledger-write before launch,
rather than logic.md's illustrative step numbering which shows packet-write at step 4 and launch at
step 6 with no explicit statement about *ledger*-write's position relative to launch) is a
**Tech-spec call (logic.md silent):** logic.md fixes packet-before-launch and probe-before-ledger
(implicitly, since the ledger records the probe's baseline result) but is silent on ledger-vs-launch
ordering specifically; writing the ledger before attempting launch means a launch failure is always
recoverable from ledger state alone, which failing to do so would not guarantee.

---

## Testing strategy

*Back-link: [logic.md → Amendments → fault-injection matrix deferred to tech.md](./logic.md#status--amendments)*

### Test infrastructure

`CONTRACT:` `tests/conftest.py` gains, alongside the existing fixtures (unchanged, DO-NOT-CHANGE):
```python
@pytest.fixture
def pm_project(initialized_project: Path) -> Path:
    """initialized_project, additionally migrated to schema v2 and given an empty ROADMAP.md."""

@pytest.fixture
def fake_git_repo(tmp_path: Path) -> Path:
    """A real `git init`-ed repo with one commit, for worktree/reconcile tests — no network."""

def run_pm(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke bin/pm.py in a child process; mirrors the existing run_script helper."""

def stub_orca_cli(tmp_path: Path, responses: dict) -> Path:
    """Write an executable shell/Python stub named `orca` that echoes canned JSON per subcommand,
    for orca-adapter tests with no real orca install or network."""
```

### Per-area coverage (fixture-driven, no model in the loop)

- **`test_artifact_lib.py`** — every row of [§Parser strict vs. compatibility
  modes](#parser-strict-vs-compatibility-modes)'s divergence table (titleless heading, duplicate ID);
  `hash_probe_spec`/`hash_file` determinism; `atomic_write` leaves the original file untouched when
  interrupted before `os.replace()` (simulated via monkeypatching `os.replace` to raise); every
  existing `test_artifact_append.py`/`test_artifact_review.py` fixture re-run directly against the
  moved functions.
- **`test_pm_ready.py`** — the full urgency table (§Data flow → Job 1); `unplaced` counted and broken
  out ready/blocked/malformed on a fixture with all three; the `-1` milestone-rank escape hatch for a
  critical bug in no milestone; `ROADMAP.md` grammar (malformed line, duplicate membership,
  `PROPOSAL` reference, dangling reference) both at write-time (refused) and read-time (`--doctor`
  finding); `Blocked by` lexical rules table in full, including the `PROPOSAL`-as-blocker rejection
  and the length-1 self-reference cycle; `CYCLE` detection on a 2-entry and a 3-entry cycle.
- **`test_pm_lifecycle.py`** — every transition row in [§The CAS transition
  mechanism](#the-cas-transition-mechanism)'s table; a CAS race fixture (two `finish` calls against
  the same entry from two threads, asserting exactly one succeeds and the other gets exit 6 — mirrors
  `test_concurrent_appends_do_not_collide_on_id`'s threading pattern,
  `tests/test_artifact_append.py:181-205`); crash-mid-transition (monkeypatch `os.replace` to raise
  mid-`atomic_write`, assert the file is byte-identical to its pre-write state); every exit code in
  [§Exit codes](#exit-codes) reached by at least one fixture; `PROPOSAL` ID rejected by
  `start`/`finish`/`park`/`decide` (exit 6); `decide` from each of `open`/`in_progress`/`delivered`;
  `park` resets the next `start`'s attempt number to 1 (documenting the [§Concerns](#concerns) call).
- **`test_pm_probes.py`** — the full `test:` pytest-exit-code mapping table (start-time `missing`
  accepted as baseline, finish-time `missing`/`fail`/`error` all refuse); `grep:` baseline-count-zero
  refusal, final-count-nonzero refusal, baseline-file-deleted refusal even when count is zero;
  `none`'s Probe field never changes across start→finish; `spec#`/`file#` hash mismatch detection
  (hand-edit the `Probe:` line between start and finish, assert `PROBE_SPEC_CHANGED` fires and finish
  still succeeds); probe timeout (`QUIRK_PM_PROBE_TIMEOUT=1` against a sleeping test) recorded as
  `error`.
- **`test_pm_handoff.py`** — `NullAdapter`'s exact `git worktree add` invocation against
  `fake_git_repo`; `create_worktree` never launches (assert no process started); packet written once,
  before launch, with `dispatch_id` rendered as the literal `"pending — assigned at launch"` string
  under the git-only adapter (which never resolves it); the packet's copied entry text is fenced and
  marked untrusted; the write-back contract's three obligations appear verbatim in the packet;
  `--repo`/`--here` redirect worktree target correctly; probe-passes-at-dispatch refuses before
  `launch` is ever called (assert launch mock uncalled).
- **`test_pm_orca_adapter.py`** — against `stub_orca_cli`: `create_worktree` never passes `--agent`;
  `launch` calls `worker-start --worktree path:<path>` targeting the exact path `create_worktree`
  returned; `signal_done` maps the stub's `sender_not_assignee` JSON response to
  `SignalResult(sent=False, reason="sender_not_assignee")` without raising; any non-JSON/non-zero
  stub response is swallowed the same way; `run_id`/`task_id` are populated pre-launch, `dispatch_id`
  only post-launch.
- **`test_pm_reconcile.py`** — the full three-way exit table (0/1/128, plus worktree-missing and
  fetch-failed as additional `CANNOT_EVALUATE` reasons) against `fake_git_repo`; fetch is called
  exactly once per unique `Handoff` path across a multi-entry run; `--verify`'s temporary detached
  worktree is always removed, including when the probe re-run itself fails; a race fixture where an
  entry's status changes between the read pass and the write-back pass (assert it's skipped, not
  double-promoted or crashed).
- **`test_pm_migrate.py`** — idempotent no-op on an already-v2 file (byte-identical output);
  partial-run resume (kill the process — via a monkeypatched `os.replace` raising — mid-migration,
  assert the file still reads as v1 and a second `migrate` call completes cleanly); `proposals.md`'s
  version bump with unchanged schema-comment text otherwise; refusal (exit 8) on a hypothetical v3
  file; `TEST_BACKLOG.md` migration adds `Logged` to the schema comment without touching any existing
  `TEST-N` entry body (byte-for-byte body comparison pre/post).
- **`test_pm_index_doctor.py`** — bounded rendering caps (11 in_progress entries → 10 shown + "…and 1
  more"); parse-error-in-one-file doesn't crash the index for the other three; every row of the
  [doctor findings catalog](#doctor-findings-catalog) reached by at least one fixture; `--doctor`
  exits 0 with findings present; the hook wrapper's exit-0 guarantee even when `pm.py --index` itself
  raises (simulated via a broken fixture project).

### Session-only behaviors (not script-provable)

- The `/quirk:pm:roadmap` skill's actual milestone-grouping judgment (which entries go where) — code
  computes the ready-set and validates the *grammar* of whatever the agent proposes; it never
  proposes the grouping itself.
- `/quirk:pm:next`'s one-candidate recommendation and its stated rationale — code computes the
  shortlist and its order; the model's argument for one candidate is not fixture-provable.
- Whether a worker actually reads the handoff packet and honors the write-back contract — `logic.md`'s
  own stated limit ([logic.md → Known limits](./logic.md#known-limits)): "nothing compels a worker to
  read the packet... a worker that ignores the packet produces an entry that stalls — visible, but
  only after the fact." Fixture tests can prove the packet's *content* is correct; they cannot prove
  a live agent reads it.

The acceptance bar: every script-provable behavior above has a passing fixture test, and every
session-only behavior is named here rather than silently assumed covered.

---

## Non-goals

*Back-link: [logic.md → Scope & non-goals](./logic.md#scope--non-goals)*

- Not specifying `skills/pm/SKILL.md`'s interview/recommendation prose, or the nine command files'
  exact wording — implementer's call against `logic.md`'s Data flow section.
- Not implementing a non-pytest `test:` runner beyond the `QUIRK_PM_TEST_RUNNER` override point — see
  [§Concerns](#concerns).
- Not adding `--doctor` CI exit-code semantics, `Logged by` provenance, difflib dedup, or GitHub
  promotion — all explicitly [Deferred to later versions](./logic.md#deferred-ideas) in `logic.md`.
- Not touching `hooks/hooks.json`'s registration, `templates/claude_md_snippet.md`, or any existing
  skill other than the new `skills/pm/` — see [DO-NOT-CHANGE fences](#do-not-change-fences).
- Not backporting `atomic_write` crash-safety to `artifact_append.py`'s existing write path — see
  [§Concerns](#concerns).
- Not building a repository-global ledger store, a distributed lock, or any mechanism that would make
  the cross-worktree race in [§The CAS transition mechanism](#the-cas-transition-mechanism)
  disappear — explicitly rejected in `logic.md` as giving up the reviewable-in-a-diff property the
  whole design is built on.
- Not implementing GitLab/Jira-equivalent integration ref resolution, or any launcher besides the
  git-only fallback and the orca adapter.

---

## Concerns

Observations that don't rise to a Decisions-Locked contradiction, but that a fresh implementer
should see rather than discover mid-build.

1. **`park`'s attempt-number reset.** [§The CAS transition mechanism](#the-cas-transition-mechanism)
   resolves "keep the attempt on record" by resetting the visible attempt counter to 1 on the next
   `start` after a `park`, since `open` (absent `Status`) has nowhere to persist it. This narrows
   "on record" further than `logic.md`'s wording suggests, in the same direction `logic.md` already
   accepts for `Probe`/`Handoff` ("earlier values are gone... git history holds them") but not
   explicitly stated for the attempt *count* itself. Worth a locked-decision amendment if the
   distinction matters in practice.
2. **`test:` is pytest-shaped by default.** `QUIRK_PM_TEST_RUNNER` makes it overridable, but nodeid
   syntax, the outcome-mapping table (§The probe execution contract), and the empirically-derived
   exit-code semantics are all pytest-specific. A JS/Jest or other-ecosystem target project gets a
   working override point, not a working default.
3. **`Handoff`'s `repo:` component is provenance only, never a `finish` precondition.** `logic.md`
   names exactly three `finish` preconditions; this document adds no fourth "origin path must match"
   check even though the data to perform one now exists on the entry. A future amendment could add
   it as a genuine mistake-catcher (catches `finish --project-dir` pointed at the wrong project
   entirely) without contradicting anything currently locked.
4. **`artifact_append.py`'s write path stays non-atomic.** `pm.py`'s new writes use `atomic_write`;
   the pre-existing append path (`bin/artifact_append.py:203`) does not, per the DO-NOT-CHANGE fence.
   The two scripts now have different crash-safety properties for the same files — worth a follow-up
   `DEFER` entry, not fixed here.
5. **A single `QUIRK_PM_INTEGRATION_REF` override doesn't vary per destination repo.** For
   cross-project dispatch where the origin and destination use different default-branch names, a
   global override (if set) applies uniformly and may name the wrong ref in the foreign repo. The
   *default* (no override) resolves correctly per-repo automatically; only an explicit override has
   this edge case, and `logic.md` doesn't address per-project overrides at all.

---

## Open questions

None. Every ambiguity this document encountered while authoring is resolved above and marked
**Tech-spec call (logic.md silent)** at the point of resolution, per the rubric's instruction not to
leave TBD placeholders in the body. Where a resolution felt closer to a genuine behavioral choice than
an implementation detail (`park`'s attempt reset, the `Handoff.repo:` precondition), it is recorded
under [§Concerns](#concerns) instead of left unresolved, so a later amendment has a specific,
actionable starting point rather than a blank.

---

## Traceability

| Section | logic.md anchor |
|---|---|
| Parser strict vs. compatibility modes | bin/artifact_lib.py is extracted before any feature lands |
| ROADMAP.md formal grammar | In scope for v1; Milestone rank for the escape hatch |
| Blocked by lexical rules | An unresolvable blocker blocks; Satisfaction is an allowlist |
| Field rendering (Status/Probe/Handoff) | Data flow → Job 2; Decisions Locked → Completion evidence |
| Contracts & interfaces (adapter) | The adapter contract; Amendments → Handoff |
| The probe execution contract | The red→green baseline; What red→green does not prove |
| The CAS transition mechanism | Two PMs in different origin worktrees; Decisions Locked → CAS |
| The migrate algorithm | In scope for v1 → Schema version 2 |
| The reconcile algorithm | Delivered is what the worker reported; closed is what the origin observed |
| The read layer | The read layer |
| Exit codes | Amendments → exit-code table deferred to tech.md |
| Testing strategy | Amendments → fault-injection matrix deferred to tech.md |
| Non-goals | Scope & non-goals |
