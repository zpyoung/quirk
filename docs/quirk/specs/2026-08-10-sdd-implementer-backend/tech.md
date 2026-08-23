# Tech spec — selectable implementer backend

## Status

Draft. Logic spec: [logic.md](logic.md). All paths below are relative to the repository root.
Line anchors were verified against the live tree on 2026-08-13; where they correct a stale anchor
in the logic spec, the correction is noted inline rather than silently substituted.

## Architecture

→ logic.md § Conceptual model, § Design.

Five files change; one is created. Everything is markdown except one Node script. No build step,
no dependency changes, no launcher change.

| File | Action | Carries |
| --- | --- | --- |
| `skills/subagent-driven-development/SKILL.md` | modify | Backend record, preflight questions, Dispatch block, wave-level audit, Step 8 `model` input, amended failure routing |
| `skills/subagent-driven-development/assets/pi-worker-delta.md` | **create** | The pi-only prompt delta (trailer contract, no-commit, condensed TDD) |
| `skills/pi-dev/scripts/pi-watch/pi-watch.mjs` | modify | `--cwd` and `--require-trailer` flags, exit 6 |
| `skills/pi-dev/scripts/pi-watch/README.md` | modify | Flags table + exit-code table rows |
| `skills/pi-dev/SKILL.md` | modify | Common-flags examples for the two new flags |

Relations: SDD's Step 5 Dispatch block is the only consumer of the new pi-watch flags and the new
delta asset. `quirk:adversarial-review` is **read, never written** — SDD's Step 8 gains a `model`
input row that the composition contract already accepts
(`skills/adversarial-review/assets/composition-contract.md:14`). The pi-watch launcher
(`skills/pi-dev/scripts/pi-watch/pi-watch`, bash) forwards all argv untouched
(`pi-watch:112` — `exec node "$PLUGIN_DIR/pi-watch.mjs" "$@"`), so new `.mjs` flags need zero
launcher work and propagate via `claude plugin update quirk` (`skills/pi-dev/SKILL.md:123`).

## Code references

### `skills/subagent-driven-development/SKILL.md` (416 lines)

→ logic.md § Design, each subsection as noted.

- `:36-47` — `## Roles` table and family-purpose prose. → logic.md § Roles table (Step 0 header).
  *Anchor correction:* there is no Step 0; the table precedes Step 1 under `## Roles`. Rows
  `:41-43` (Implementer / Reviewer ×3 / Fixer) all go stale; prose `:45-47` ("Reviewers are a
  different model family from implementers on purpose") stays true but gains the deliberate
  same-family exception.
- `:77-106` — `### Step 1: Preflight`. → logic.md § Preflight (Step 1). Git checks `:79-83` keep.
  `:88-96` (reviewer-reachability floor) is rewritten: `pi-watch --check codex` (`:91`) now gates
  *offering* the pi-codex implementer option; the reviewer check becomes
  `pi-watch --check "$REVIEWER_ALIAS"`. `:98-102` (the `--provider openai-codex --model
  gpt-5.6-sol --thinking high` pin, the "`--alias codex` is not sufficient" warning, and the
  dangling `quirk:code-reviewer` reference at `:101`) is **removed** per logic.md § Preflight
  "Removed"/"Fixed" — the fallback role `:101` served is replaced by the `Task`-path routing
  specified under § Preflight sequence below, not left uncovered. Run-journal paragraph `:104-106` gains the backend record and `TASK_HEAD_<n>`
  fields.
- `:153-165` — `### Step 5: Dispatch`. → logic.md § Dispatch block (Step 5). `:161-162` (staging)
  becomes the common preamble; the Dispatch block's two bindings insert after it. `:164-165` (the
  foreground rule citing the 3/3 stall) is **amended, not deleted** — the replacement states the
  new gate (tree state) and why the old rule's evidence supports it
  (`docs/quirk/specs/2026-07-21-sdd-captain-control-plane-design.md:288`).
- `:167-211` — `### Step 6: Audit, accept, commit, merge`. → logic.md § Audit (Step 6).
  `:169-170` ("The order *is* the gate … none of them moves") is amended with the wave-level
  hoist, carrying its reason. Audit commands `:176-180` are unchanged and become per-live-worktree.
  `:172-174` ("Implementers do not commit") gains the HEAD-verification step.
- `:246-257` — Step 8 per-invocation input table. → logic.md § Review (Step 8) and fixers
  (Step 9). Gains one row (`model`); `author_family` row `:257` reads the recorded value.
- `:320-322` — `manifest.reviewer.independence` reader guidance. **No change** — it already
  handles `reduced`.
- `:332-334` — Step 9 fixer dispatch. Gains a pointer to the Step 5 Dispatch block.
- `:357-358` — the worker-report vocabulary rule ("A report you cannot validate against that
  vocabulary is `FAILED`."). **This is the amendment logic.md flags as most consequential** —
  replaced by the advisory-report rule and its observation/outcome table (logic.md § Dispatch
  block, table at logic.md:153-158).
- `:360-370` — Failure routing table. Gains six rows (logic.md § Failure routing — new rows).
- `:379-392` — Red Flags table. Gains three rows (logic.md § Red Flags — new rows). The `Never`
  bullet `:400` concerns *reviewer* output and is untouched.
- `:412` — Integration bullet for `quirk:pi-dev` widens to cover implementer dispatch.

### `skills/subagent-driven-development/assets/pi-worker-delta.md` (new, target ~30 lines)

→ logic.md § Prompt assets. Sibling of `implementer-prompt.md` (86 lines) and `fixer-prompt.md`
(69 lines), both **unchanged**. Content contract under § Contracts below.

### `skills/pi-dev/scripts/pi-watch/pi-watch.mjs` (414 lines)

→ logic.md § pi-watch changes.

- `:129-139` — `opts` object: add `cwd: null` and `requireTrailer: null`.
- `:140-147` — `takeValue(flag, i)`: reuse as-is for both new flags (exits 2 on missing value).
- `:148-165` — parse loop. New `else if` branches must sit **before** the `a.startsWith("--")`
  catch-all at `:163` (branches after it are unreachable). Exemplar shape: `:150`
  (`--alias`).
- `:363` — `const cwd = process.cwd();` — the **single** `process.cwd()` call site. *Anchor
  correction to logic.md § pi-watch changes:* `:384` (`SessionManager.inMemory(cwd)`) and `:376`
  (`createAgentSession({ cwd, … })`) reference this const, they do not call `process.cwd()`
  again. Overriding the one assignment covers both consumers.
- `:388-396` — `session.subscribe` handler; `text_delta` chunks stream to stdout at `:390` and
  are not retained. The trailer scan needs the assistant text accumulated (see contract).
- `:398` — `await session.prompt(opts.prompt)`; the trailer scan inserts between here and the
  flush block.
- `:399-406` — flush pattern (`Promise.all` over stdout/stderr writes) documented as guarding a
  truncation bug; the exit-6 path must use the same pattern. `:405` — the `"  ✔ done\n"` line the
  matched trailer value is appended to.
- Exit codes in use: 0 (`:162,:185,:316,:407`), 1 (`:413`), 2 (`:144,:163,:169,:173,:177,:258,
  :282,:335,:340`), 3 (`:348`), 4 (`:217,:222`), 5 (`:265,:325`). **6 is unused** — confirmed by
  exhaustive grep; it becomes the missing-trailer code.
- `skills/pi-dev/reference/sdk-mode.md:88` — `session.messages` (`AgentMessage[]`) is the
  SDK-documented alternative to delta accumulation.

### `skills/pi-dev/scripts/pi-watch/README.md` (124 lines)

- `:90-102` — Flags table: +2 rows (`--cwd <dir>`, `--require-trailer <KEY>`).
- `:104-115` — Exit codes table: +1 row (6).

### `skills/pi-dev/SKILL.md` (149 lines)

- `:63-72` — "Common flags" block: add one usage line per new flag.
- `:140` — the raw-`pi` statement ("Pi has no `--cd` flag…") stays **true and untouched**; it
  describes the raw binary, not pi-watch.

## Contracts & interfaces

### Backend record

→ logic.md § Conceptual model.

```
SCHEMA: run-journal additions (journal lives in scratch, outside the repo — SKILL.md:104-106)
  IMPLEMENTER    : "claude-task" | "pi-codex"          # user choice at preflight
  AUTHOR_FAMILY  : "anthropic" | "openai"              # derived: claude-task → anthropic, pi-codex → openai
  REVIEWER_ALIAS : "codex" | "gemini" | "terra" | "opus" | "sonnet" | "flash" | "task-fallback"
                                                       # six aliases from adversarial-review's
                                                       # ALIAS_LADDER (scripts/adversarial-review:
                                                       # 853-860); task-fallback recorded when
                                                       # preflight verified no alias reachable for
                                                       # either pairing — Step 8 then omits `model`
  TASK_HEAD_<n>  : commit sha                          # each worktree's HEAD at dispatch
```

Invariants: resolved once at preflight, immutable for the run; every later step reads, none
re-derives. Any *alias* recorded in `REVIEWER_ALIAS` is drawn from `adversarial-review`'s 6-alias
table, never `pi-watch`'s 11 (`pi-watch.mjs:35-124`) — `select_reviewer` raises `UsageError` on
anything outside its own set (`scripts/adversarial-review:914-916`), which surfaces as exit 2 with
no JSON. `task-fallback` is the one non-alias state the field can hold, recorded only when
preflight verified no alias was reachable for either pairing, in which case Step 8 omits `model`.

### Preflight sequence (Step 1 rewrite)

→ logic.md § Preflight (Step 1), steps 1-6 verbatim; this is prose in SKILL.md, not code. Both
choices are elicited via `AskUserQuestion` (logic.md § Decisions Locked, Selection granularity —
a skill argument was rejected because the `quirk:brainstorming` entry path passes none). Error
behavior: a reviewer alias that fails `pi-watch --check "$REVIEWER_ALIAS"` triggers the
implementer-flip offer **only when the flipped pairing's reviewer is known reachable**; if neither
pairing resolves, route to `adversarial-review`'s `Task` path
(`skills/adversarial-review/SKILL.md:376-378`; *anchor correction:* logic spec's `:914` cite for
the backstop is `scripts/adversarial-review:914`, the `UsageError` — the Task-path prose lives in
that skill's SKILL.md) and warn once. Reviewer question option sets: author `anthropic` → `codex`
(recommended), `gemini`; author `openai` → `opus` (recommended), `gemini`; same-family picks
selectable but labeled as degrading independence.

### Dispatch block (Step 5)

→ logic.md § Dispatch block (Step 5).

Common preamble (both bindings): stage `implementer-prompt.md` with its six variables
(`{{TASK}} {{CONTRACT}} {{ACCEPTANCE}} {{SCOPE_FILES}} {{WORKDIR}} {{FENCES}}`,
`assets/implementer-prompt.md:3-4`), one worktree per task from `WAVE_BASE`, created serially,
then record `TASK_HEAD_<n>`:

```
COMMAND: git -C "$WT" rev-parse HEAD   # record as TASK_HEAD_<n> at dispatch
```

**Claude binding** — `Task` subagent, Sonnet, foreground, one per task in a single message.
Unchanged from today.

**pi binding** — append `assets/pi-worker-delta.md` to the staged prompt (implementer-only
section included), then per task:

```
COMMAND: gtimeout 1800 pi-watch --cwd "$WT" --alias codex \
  --tools read,bash,edit,write --require-trailer STATUS "$(cat "$PROMPT")"
```

One Bash call per task, `run_in_background: true`. Postconditions the orchestrator may rely on:
`gtimeout` guarantees termination and an exit code; completion is decidable from tree state alone
(a lost re-invocation costs a status word, never the wave). Exit-code reading: 0 = trailer
present and well-formed (value echoed on the stderr done line); 6 = no validated status — fall
through to tree evaluation; anything else = dispatch-level failure, routed per the existing
pi-watch failure signatures (`skills/pi-dev/SKILL.md:34-39` for check codes; run codes per
README).

### Worker-report rule (the SKILL.md:357-358 amendment)

→ logic.md § Dispatch block (Step 5), including the four-row observation/outcome table
(logic.md:153-158), reproduced into SKILL.md verbatim. The replacement text must preserve: the
vocabulary `DONE | NEEDS_CONTEXT | BLOCKED | FAILED` stays the request; the *gate* moves to tree
state (HEAD-check → scope audit → acceptance); a validated `BLOCKED`/`NEEDS_CONTEXT` still routes
as today because it carries information the tree cannot.

### Audit (Step 6 rewrite)

→ logic.md § Audit (Step 6). Order contract, unconditional for both backends:

```
CONTRACT: wave returns → HEAD-check all live trees → scope-audit all live trees
          → then per task: acceptance → commit → merge
```

- HEAD-check: each live worktree's `git -C "$WT" rev-parse HEAD` equals its `TASK_HEAD_<n>`.
  Mismatch → stop that task, surface; no soft reset. Stated as a detection heuristic, not a
  guarantee (a `commit` + `reset --soft` evades it; the working-tree-based audit and acceptance
  still hold).
- Scope audit: existing commands (`SKILL.md:176-180`) run in **every** live worktree, each
  against its **own** task's `scope.files`. One pass — it subsumes the per-task audit.
- **Retry re-entry invariant:** *no tree's diff reaches acceptance without an audit that observed
  that diff.* Both retry paths (`SKILL.md:362`, `:364`) re-run HEAD-check and scope-audit on that
  tree before acceptance.

### Step 8 input table

One new row and one changed row (table at `SKILL.md:248-257`):

```
SCHEMA: | `model` | the recorded `REVIEWER_ALIAS` — only when preflight verified it reachable;
        |         | omitted when the record holds `task-fallback` |
        | `author_family` | the recorded `AUTHOR_FAMILY` |   # was: "the model family that implemented the work"
```

Behavior note carried into the prose: an explicit `model` builds a single-candidate list — no
ladder walk, failure reported as `resolved: false` → `NOT_REVIEWABLE`
(`scripts/adversarial-review:930-934`, `:963-972`) — which is why preflight's alias check is
load-bearing and why `model` is passed only when preflight verified the recorded alias reachable.
When the record holds `task-fallback` — no alias verified reachable for either pairing — `model`
is omitted entirely; `adversarial-review`'s own ladder and `Task` backstop govern instead. A
same-family pick warns once and is expected to stamp `manifest.reviewer.independence: reduced`
(`scripts/adversarial-review:959`), which Step 9 already reads (`SKILL.md:320-322`).

### `pi-worker-delta.md` content contract

→ logic.md § Prompt assets. One file, two audiences:

- Common section (all pi workers): the `STATUS: <word>` trailer — final line, one key, the four
  legal values, prose detail *above* it; the no-commit rule restated with the HEAD check named as
  mechanical verification; a note that no `Skill` tool exists.
- Implementer-only section: condensed red-green TDD block (write failing test → watch it fail →
  implement → watch it pass), replacing the `quirk:test-driven-development` reference a pi worker
  cannot resolve. Delimited so the orchestrator can omit it for fixers:

```
CONTRACT: <!-- IMPLEMENTER-ONLY --> … <!-- /IMPLEMENTER-ONLY -->
          orchestrator appends the whole file for implementers,
          everything outside the markers for fixers
```

### `pi-watch --cwd <dir>`

```
CONTRACT: value-taking flag via takeValue() (exit 2 on missing value, pi-watch.mjs:140-147)
  precondition : <dir> exists and is a directory
  violation    : usage error → stderr message → exit 2. NEVER fall back to process.cwd() —
                 a silent fallback recreates the exact contamination this flag exists to kill
  effect       : const cwd = opts.cwd ?? process.cwd()   (the :363 assignment; consumers :376, :384
                 follow automatically)
  default      : absent flag → process.cwd(), byte-identical to today
```

### `pi-watch --require-trailer <KEY>`

```
CONTRACT: value-taking flag via takeValue()
  scan input   : exactly the assistant text written to stdout this run (accumulate text_delta
                 chunks at :389-390, or read session.messages after :398 — implementer's choice;
                 the stdout contract defines the observable)
  scan         : take the last 3 non-empty lines; for each, trim whitespace, strip leading/
                 trailing runs of *, _, ` ; match against the pattern below; scan backward from
                 the final line — first match wins
  KEY          : matched literally (regex-escape it); value is capture group 1
  on match     : exit path unchanged (0); stderr done line becomes "  ✔ done  <KEY>: <value>\n"
  on no match  : write "  ✖ missing trailer <KEY>\n" to stderr, flush via the same Promise.all
                 pattern as :403-406 (the truncation guard), exit 6
  scope        : runs only on the normal-completion path after session.prompt() resolves;
                 runtime errors still exit 1; --check / --list-aliases short-circuits unaffected
  default      : absent flag → no scan, no accumulation requirement, exit behavior identical
                 to today. Exit 6 is unreachable without the flag — no existing caller can
                 observe it
```

```
REGEX: ^KEY: (\S+)$        # KEY substituted literally after escaping; applied per stripped line
```

## Data models / schemas

- Run-journal additions: § Backend record above. The journal's location and existing fields
  (`SKILL.md:104-106`) are unchanged.
- `GateResult` / manifest shapes: owned by `adversarial-review`
  (`skills/adversarial-review/assets/composition-contract.md:118-120`) — consumed, not modified.
- Worker status vocabulary: `DONE | NEEDS_CONTEXT | BLOCKED | FAILED`, unchanged as a
  *vocabulary*; only the missing-report consequence changes (§ Worker-report rule).

## DO-NOT-CHANGE fences

| Region | Why fenced |
| --- | --- |
| `skills/adversarial-review/**` (all of it — script, SKILL.md, contract, profiles) | Reviewer dispatch mechanism is that skill's business (logic.md § Scope and non-goals). SDD passes `model` through an input the contract already defines; nothing on the callee side needs to move. |
| `skills/subagent-driven-development/assets/implementer-prompt.md`, `assets/fixer-prompt.md` | Logic spec locks them unchanged (§ Prompt assets) — the delta file exists precisely so the shared core never forks. |
| `skills/subagent-driven-development/assets/reviewer-prompt.md` | Redirect stub; silent on implementer backends, nothing here to update. |
| `skills/pi-dev/scripts/pi-watch/pi-watch` (bash launcher) | Untouched ⇒ `.mjs`-only change ⇒ users get it via `claude plugin update quirk` with no reinstall (`skills/pi-dev/SKILL.md:123`). Touching it silently breaks every installed copy until re-`install`. |
| pi-watch exit codes 0-5 semantics | Existing callers key off them — `adversarial-review`'s preflight shells `pi-watch --check` (`scripts/adversarial-review:862`) and SDD's Step 1/8 read them. 6 is additive only. |
| pi-watch stdout contract (assistant text and nothing else, `pi-watch.mjs:12-16`, README) | Callers parse stdout as the report; the trailer echo goes to stderr for exactly this reason. |
| Step 6 per-task gate order (audit → accept → commit → merge) | Logic spec preserves it exactly (§ Audit); the hoist changes *when* the sequence starts, never its internal order. |
| `ALIAS_LADDER` (`scripts/adversarial-review:853-860`) and pi-watch `ALIASES` (`pi-watch.mjs:35-124`) | The 6-vs-11 namespace split is load-bearing for preflight's option set; widening either table is a separate design decision. |

## Always / Ask / Never

**Always**

- Draw reviewer options from `adversarial-review`'s 6 aliases, never pi-watch's 11.
- Record `TASK_HEAD_<n>` at dispatch for every worktree, both backends.
- Run HEAD-check and scope audit unconditionally — Claude runs too (logic.md § Audit: "branching
  would buy nothing").
- Re-audit any retried task's tree before its acceptance step.
- `gtimeout`-wrap every pi dispatch (liveness: it is what makes completion decidable).
- Flush stdout/stderr via the `Promise.all` pattern before *any* new exit path in pi-watch.mjs.
- Keep the trailer echo on stderr; keep stdout pure assistant text.

**Ask (delegated to the implementer)**

- Delta-accumulation vs `session.messages` for the trailer scan input.
- Exact prose wording of amended SKILL.md sections, provided every locked clause survives
  (reconcile row-by-row against logic.md § Decisions Locked — compression sheds operative
  clauses).
- Ordering of the two new parse branches relative to each other; help-text wording in
  `printHelp()` (`pi-watch.mjs:197-205`) and README phrasing.
- Whether `--check`'s informational ignore-line (`pi-watch.mjs:190-195`) mentions the new flags.

**Never**

- Fall back to `process.cwd()` when `--cwd` is present but invalid.
- Teach pi-watch the status vocabulary — `--require-trailer` verifies existence and shape only;
  the calling skill owns legal values (logic.md § Decisions Locked, Prompt portability).
- Widen the pi implementer tool grant beyond `read,bash,edit,write`.
- Reuse exit codes 0-5 for the trailer failure, or emit 6 from any other path.
- Let a worker's report gate acceptance — tree state gates; the report diagnoses.
- Edit `adversarial-review` to accommodate this spec.

## Cross-cutting

- **Containment/security.** A pi implementer holds full user-level filesystem access
  (`skills/pi-dev/SKILL.md:97`, README:88) — the prompt is not a boundary; the wave-level audit
  is. `--cwd` exists to make cross-tree contamination *attributable* at dispatch rather than
  discoverable-but-anonymous at audit (logic.md § pi-watch changes).
- **Observability.** The run journal records the backend record, `TASK_HEAD_<n>`, and a note
  whenever a task is accepted with no validated status. The stderr done-line echo makes the
  trailer value visible in dispatch logs without touching stdout.
- **Rollback.** All changes are docs plus one script; no migration. `git revert` restores
  everything; `.mjs` reverts propagate the same way updates do.
- **Compatibility.** Both flags default-off; absent them, pi-watch behavior is byte-identical.
  Exit 6 is unobservable to existing callers.

## Testing strategy

pi-watch has no test harness; verification is command-level. Metered calls are flagged.

- **Syntax gate (free):** `node --check skills/pi-dev/scripts/pi-watch/pi-watch.mjs` after every
  edit.
- **`--cwd` (one metered call + one free):**
  - free: `pi-watch --cwd /nonexistent --alias codex "x"` → exit 2, no dispatch.
  - metered: `pi-watch --cwd <tmpdir> --alias haiku --tools read,bash "run pwd and print it"` →
    output names `<tmpdir>`.
- **`--require-trailer` (two metered calls):** with `--alias haiku`:
  - prompt "Reply with exactly: STATUS: DONE" + `--require-trailer STATUS` → exit 0, stderr done
    line carries `STATUS: DONE`.
  - prompt "Reply with exactly: hello" + `--require-trailer STATUS` → exit 6.
  - free negatives: `--require-trailer` with no value → exit 2; no `--require-trailer` → exit 0
    path untouched.
- **Regression (free):** `pi-watch --list-aliases`, `pi-watch --check codex`, `pi-watch --where`
  all behave exactly as before the change.
- **SKILL.md edits:** no runnable acceptance. The bar: every anchor cited in this spec still
  resolves post-edit (grep), every logic.md § Decisions Locked clause survives row-by-row, and
  the diff passes this project's own adversarial review before merge.
- **The 3-line scan tolerance** (logic.md § pi-watch changes rationale) remains a judgment call
  validated only by the metered trailer tests above plus first dogfood use — logic.md already
  flags it; do not silently widen or narrow the window during implementation.

## Non-goals

→ logic.md § Scope and non-goals, restated here only as it bounds *this document*:

- No changes to `quirk:executing-plans`, no `--timeout` flag, no `pi-sonnet`/`pi-opus`
  implementer aliases, no per-wave or per-task backend selection.
- No test harness for pi-watch is introduced (deliberate: command-level verification above; a
  harness is its own project).
- No reconciliation of `SKILL.md:88-102`'s direct-pin mechanism with Step 8's delegation beyond
  what the preflight rewrite removes — the pin paragraph dies with this change, which *is* the
  reconciliation.
- This spec does not restate rationale; every "why" lives in logic.md and is linked, not copied.
