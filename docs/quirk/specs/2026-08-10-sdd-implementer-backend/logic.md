# Selectable implementer backend for subagent-driven-development

## Status

Draft.

## Problem

`quirk:subagent-driven-development` hard-codes its worker fleet. Implementers and fixers are Sonnet
subagents dispatched via `Task`; reviewers are pinned to `--provider openai-codex --model
gpt-5.6-sol --thinking high`. A user who wants codex to *write* the code has no lever, and the one
place the skill mentions an alternative — a fallback to "Claude `quirk:code-reviewer` subagents" —
names a skill that does not exist in `skills/`.

The naive change (add a flag, dispatch pi instead of `Task`) breaks three things that are not
visible from Step 5:

1. **Reviewer independence.** Step 8 passes `author_family` to `quirk:adversarial-review`, whose
   `select-model` deliberately resolves a family *different* from the author's. With implementers
   flipped to codex and the reviewer still pinned to `gpt-5.6-sol`, the loop silently becomes a
   same-family self-review — the exact failure the skill is built to prevent.
2. **Containment.** `pi` has no sandbox and `pi-watch.mjs:363` hard-codes `process.cwd()`. A pi
   implementer holds full user-level filesystem access, and Step 6's per-task scope audit only
   diffs *inside* the task's own tree, so a write into a sibling worktree is structurally
   invisible to it.
3. **Prompt resolvability.** `implementer-prompt.md` instructs the worker to "Follow
   quirk:test-driven-development". A pi worker has no `Skill` tool and cannot resolve that
   reference.

## Conceptual model

The run acquires a **backend record**, resolved once during preflight and immutable for the run:

| Field | Values | Derivation |
| --- | --- | --- |
| `IMPLEMENTER` | `claude-task` \| `pi-codex` | User choice at preflight |
| `AUTHOR_FAMILY` | `anthropic` \| `openai` | Mechanical from `IMPLEMENTER` |
| `REVIEWER_ALIAS` | a pi alias | User choice at preflight, cross-family options offered first |

The record is written to the run journal beside `RUN_BASE`. Every later step **reads** it; no step
re-derives it.

Exactly one seam branches on `IMPLEMENTER`: a **Dispatch** block in Step 5. Step 9's fixers point at
that block rather than restating it. Steps 6 and 8 consume recorded values and do not branch at all.

Counting the branch points is what selected this shape. Only "dispatch a worker" genuinely differs
between backends; everything else either reads a recorded value or should apply to both paths
regardless of who wrote the code.

## Data flow

Preflight resolves the backend record and writes it to the run journal. Decomposition is unchanged —
tasks carry contracts, acceptance commands, `dependencies`, and `scope.files` exactly as today, and
none of those fields mention a backend.

At dispatch, the orchestrator stages the shared prompt core, appends the pi delta when
`IMPLEMENTER` is `pi-codex`, and hands each task to the binding named by the Dispatch block. Workers
return a status; the pi path additionally returns an exit code that encodes whether the status was
well-formed.

Once the whole wave has returned, the orchestrator verifies every live worktree's HEAD against the
value recorded at dispatch, then scope-audits every live worktree against its owning task's
`scope.files`. Only then does per-task acceptance, commit, and merge proceed.

At review, the orchestrator passes the recorded `AUTHOR_FAMILY` and `REVIEWER_ALIAS` into
`quirk:adversarial-review` as `author_family` and `model`. The reviewer's dispatch mechanism, ladder
resolution, and `Task` backstop remain that skill's business.

## Design

### Preflight (Step 1)

Ordered, because step 4's option set depends on step 3's result:

1. Existing git checks — branch, dirty tree, `RUN_BASE`.
2. **Implementer question.** Claude subagents (recommended) or pi codex. `pi-codex` is offered only
   when `pi-watch --check codex` exits 0.
3. Derive `AUTHOR_FAMILY`: `claude-task → anthropic`, `pi-codex → openai`.
4. **Reviewer-alias question.** Cross-family options first. Author `anthropic` → `codex`
   (recommended), `gemini`. Author `openai` → `opus` (recommended), `gemini`. Same-family picks stay
   selectable but are labeled as degrading independence.

   **Options are drawn only from `quirk:adversarial-review`'s own alias table**, not from
   `pi-watch`'s. The two namespaces differ: `pi-watch` knows 11 aliases
   (`pi-watch.mjs:35–124`), `adversarial-review` knows 6 — `codex, gemini, terra, opus, sonnet,
   flash` (`scripts/adversarial-review:853–860`) — and `select_reviewer` raises `UsageError` on
   anything outside its own set (`:914`), which `main` converts to **exit 2 with no JSON on
   stdout** (`:2195`). An alias like `haiku` is a natural same-family Anthropic pick that
   `pi-watch --check` would green-light and Step 8 would then crash on deterministically, burning
   the retry budget on a config mismatch. The offered set is therefore the intersection, which is
   `adversarial-review`'s table.
5. `pi-watch --check "$REVIEWER_ALIAS"`. On failure, offer the implementer flip — but only when the
   flipped pairing actually resolves. If neither pairing resolves, fall back to
   `quirk:adversarial-review`'s documented `Task` path and warn once.

   This check is **load-bearing, not a convenience**. An explicit `model` makes
   `select_reviewer` build a single-candidate list — "tried alone, and its failure is reported
   rather than papered over with a fallback" (`:930–934`). Supplying a reviewer alias therefore
   *disables* the ladder walk that would otherwise recover from an unreachable rung, so an
   unverified alias yields `NOT_REVIEWABLE` with nothing behind it.
6. Record all three fields in the run journal.

**Removed:** the `--provider openai-codex --model gpt-5.6-sol --thinking high` pin and the prose
around it, including the `--alias codex is not sufficient` warning that only made sense under a pin.

**Fixed:** the dangling `quirk:code-reviewer` fallback (`SKILL.md:101`). The real fallback is
`quirk:adversarial-review`'s `Task` path. Note the precise defect: `quirk:code-reviewer` was never a
skill, only a `Task` naming convention borrowed from `quirk:requesting-code-review` — the reference
is dangling either way, but the spec should not claim a skill was deleted.

### Roles table (Step 0 header)

`SKILL.md:41–43` states Implementer and Fixer as "Sonnet subagent via `Task`" and Reviewer as
"`gpt-5.6-sol` high via `pi-watch`". All three rows go stale under this change: the first two become
backend-dependent, and the third becomes a user-picked alias. The Reviewer row was already stale
before this spec — Step 8 has delegated dispatch to `adversarial-review`'s own resolution for some
time, so the literal model pin described a mechanism that no longer ran. The table is in edit scope.

### Dispatch block (Step 5)

Common to both bindings: stage the prompt, create one worktree per task from `WAVE_BASE`, create
worktrees **serially**, and record each worktree's HEAD as `TASK_HEAD_<n>` at dispatch time.

**Claude binding.** `Task` subagent, Sonnet, foreground, one per task in a single message.
Unchanged from today.

**pi binding.** Append `assets/pi-worker-delta.md` to the staged prompt, then per task:

```bash
gtimeout 1800 pi-watch --cwd "$WT" --alias codex \
  --tools read,bash,edit,write --require-trailer STATUS "$(cat "$PROMPT")"
```

Dispatched with `run_in_background: true`, one Bash call per task. The Bash tool caps foreground
calls at 600s, which an implementer-scale task can exceed; a task killed at the ceiling leaves a
partial dirty worktree the audit will reject.

**The tree is the source of truth; the worker's report is advisory.** This is the amendment that
makes background dispatch safe, and it is what Step 5's foreground rule gets modified by — not a
carve-out claiming background Bash is exempt.

The record behind that rule documents failures on *both* paths in one sentence: "3/3 captains
stalled on background-dispatch re-invocation, one fix-worker report was lost to a foreground
timeout (commit survived)"
(`docs/quirk/specs/2026-07-21-sdd-captain-control-plane-design.md:288`). It describes the background
stall generically, not as `Task`-specific, so any argument that backgrounded Bash is categorically
different is unsupported by the only evidence there is. The parenthetical is the useful part:
**the commit survived.** The work was never at risk, because the orchestrator — not the worker —
audits the diff and runs acceptance.

So the gate becomes tree state, and the report becomes diagnosis:

| Observation | Outcome |
| --- | --- |
| Report absent or unvalidatable, audit clean, acceptance passes | **Accept.** Record that no validated status was received. |
| Report absent or unvalidatable, acceptance fails | `FAILED`; retry once, as today |
| Report says `DONE`, acceptance fails | `FAILED` — unchanged; a claim never overrides a run |
| Report says `BLOCKED` / `NEEDS_CONTEXT` | Route as today. These carry information the tree cannot. |

This amends `SKILL.md:357–358` ("A report you cannot validate against that vocabulary is `FAILED`").
That rule was written for a control plane where the orchestrator had only the worker's word; it
still has the diff and the acceptance commands, so the rule was belt-and-braces rather than the
gate. What is genuinely lost: a worker that returns `BLOCKED` for a real reason — an out-of-scope
dependency, a fence collision — degrades to "acceptance failed, retry" when its report goes missing.
That is a worse diagnosis, not an unsafe outcome, and it is the price of surviving both recorded
failure modes.

`gtimeout`/`timeout` wrapping follows `quirk:pi-dev`, which already prescribes it because `pi` has
no built-in timeout. Under background dispatch it is additionally **load-bearing for liveness**:
it is what guarantees every dispatch terminates and produces an exit code, so a hung worker becomes
a timed-out one rather than a wave that never completes. And because completion is decidable from
the tree, a lost re-invocation notification no longer strands the run the way it stranded 3/3 —
the orchestrator can determine what happened by looking, instead of waiting to be told.

### Prompt assets

`implementer-prompt.md` and `fixer-prompt.md` are **unchanged**. One new asset,
`assets/pi-worker-delta.md`, is appended on the pi path:

- **All pi workers** — the `STATUS: <word>` trailer requirement (final line, one key, four legal
  values, prose detail above it); the no-commit rule restated with the HEAD check named as a
  mechanical verification; a note that no `Skill` tool is available.
- **Implementers only**, in a marked section — a condensed red-green TDD block replacing the
  `quirk:test-driven-development` reference a pi worker cannot resolve.

One file rather than two, because the fixer delta is a strict subset of the implementer delta. This
is the conditional-block pattern rejected for the prompt core, accepted here at ~30 lines with one
marked section rather than across 400.

### Audit (Step 6)

Two additions, both **unconditional** — they apply to Claude runs too. Contamination is not
backend-specific and the commands are cheap, so branching would buy nothing and would leave the
Claude path with a weaker audit for no reason.

**HEAD verification.** Each worktree's HEAD must equal its recorded `TASK_HEAD_<n>`. A moved HEAD
means the worker committed and bypassed the audit: the task stops. No soft reset — absorbing the
violation would discard the signal that a worker ignored an explicit instruction.

This is a **detection heuristic, not a guarantee**, and the spec states it as such. It catches a
plain commit and a `--amend`; it does not catch a commit followed by `git reset --soft` back to
`TASK_HEAD_<n>`, which restores the checked value while leaving the tree exactly as committed. The
downstream safety property survives that gap regardless: the scope audit, acceptance, and commit
all operate on the true working-tree diff, not on commit history. What is lost is the signal that a
worker ignored an instruction — worth having, not worth a stronger mechanism.

**Wave-level scope audit.** The per-task audit is hoisted to run for every live worktree once the
whole wave has returned, each checked against **its own** task's `scope.files`. A path outside its
owner's declared scope is a violation regardless of which worker wrote it. The report names the
victim rather than the culprit; that is sufficient, because the response is the same either way —
stop the wave and re-plan.

These are one pass, not two: auditing every worktree against its owner's scope subsumes the per-task
audit.

Step 6's order becomes:

> wave returns → HEAD-check all trees → scope-audit all trees → **then per task:** acceptance →
> commit → merge

The per-task gate order (audit → accept → commit → merge) is preserved exactly. What changes is that
no task commits until the whole wave has returned. The skill currently states that this order never
moves, so the change is written as a deliberate amendment carrying its reason, not slipped in.

**Retries re-enter the audit.** The invariant the hoist must preserve is: *no tree's diff reaches
acceptance without an audit that observed that diff.* The wave-level pass satisfies it for first
attempts only. Both existing retry paths — `Implementer BLOCKED / FAILED → retry once with a fresh
worker` and `Task acceptance fails → retry once` (`SKILL.md:362`, `:364`) — produce a *new* diff
after the wave-level pass has already completed, and under a naive hoist nothing would ever audit
it. A retried task therefore re-runs HEAD-check and scope-audit against its own tree before its
acceptance step.

This is the defect the hoist introduces if written carelessly, and it is the one that matters most:
a retried pi worker is exactly the case where an unsandboxed writer gets a second, unobserved pass
at the tree.

Cost: slight serialization at wave end, bounded because the build/test gate already waits for the
full wave. Sequential tasks see no change — one tree means the wave-level audit and the per-task
audit are the same operation.

### Review (Step 8) and fixers (Step 9)

Step 8's input table gains `model`, set to `REVIEWER_ALIAS`. `author_family` reads the recorded value
instead of assuming `anthropic`. A same-family reviewer pick warns once and is expected to stamp
`manifest.reviewer.independence: reduced`, which Step 9 already reads.

`quirk:adversarial-review` accepts `model` as a pi alias that overrides family selection. It does
**not** walk a ladder within that alias — `select_reviewer` builds a single-candidate list from it
and reports failure rather than falling back (`scripts/adversarial-review:930–934`), and each alias
maps to one fixed triple (`:853–860`). An explicit user choice therefore *replaces* ladder
resolution rather than composing with it, which is why preflight must verify the alias itself.

Step 9 fixers use the binding named by the Dispatch block — a pointer, not a restatement.

### pi-watch changes

| Flag | Behavior |
| --- | --- |
| `--cwd <dir>` | Sets the session working directory instead of inheriting `process.cwd()` (`pi-watch.mjs:363`, `:384`) |
| `--require-trailer <KEY>` | Scan backward through the last **3** non-empty assistant lines for `^KEY: (\S+)$`, stripping surrounding markdown emphasis and backticks first. First match wins. The value is echoed to stderr on the `✔ done` line. Exit **6** when no line matches. |

Exit codes 0–5 are already in use; 6 is free.

The three-line backward scan exists because a strict last-line match is fragile against ordinary
model behavior, not against bugs: a trailing sign-off or a bolded status line makes the literal
final line not the trailer, and the resulting exit 6 is *deterministic* — the retry draws the same
model with the same tic and fails identically. Tolerating a short tail costs nothing and removes a
failure mode retry cannot clear.

`--require-trailer` is deliberately **generic**. Teaching `pi-watch` the vocabulary
`DONE | NEEDS_CONTEXT | BLOCKED | FAILED` would put this skill's return contract inside a
general-purpose wrapper that `quirk:adversarial-review` and ad-hoc dispatches also use. The wrapper
verifies that a trailer *exists and is well-formed*; the calling skill owns which values are legal.

`--cwd` is the higher-value change of the two. Without it every worktree dispatch is a
`(cd "$WT" && pi-watch …)` subshell whose failure mode is silent: a `cd` that does not fire runs the
implementer against the main tree, which is precisely the contamination the wave-level audit can
detect but not attribute.

Both flags are documented in `pi-dev/SKILL.md` (usage block and flags table) and the pi-watch README.
`.mjs` changes propagate via `claude plugin update quirk` with no reinstall; only launcher-script
changes require re-running `install`.

## Behavior and scenarios

**Default run, nothing chosen.** Preflight recommends Claude subagents and `codex` as reviewer. The
run behaves as it does today, with two additions: HEAD verification and a wave-level rather than
per-task scope audit.

**pi-codex implementers, codex unavailable at preflight.** `pi-watch --check codex` fails, so the
implementer question offers only Claude subagents. No dead end is ever presented.

**pi-codex implementers, no Anthropic reviewer reachable.** Preflight offers the flip to Claude
implementers, since that pairing's reviewer (`codex`) is known reachable. If the user declines, the
run proceeds through `adversarial-review`'s `Task` path with a single warning.

**A pi worker commits its own work.** HEAD verification catches it before any audit runs. The task
stops and is surfaced; it is not silently reset.

**A pi worker writes into a sibling worktree.** The wave-level audit reports a path outside the
*victim's* declared scope. The wave stops and is re-planned. The orchestrator cannot name the
culprit, and does not try to.

**A pi worker omits its status trailer.** `pi-watch` exits 6. The orchestrator has no validated
status, so it falls through to tree evaluation: HEAD-check, scope audit, acceptance. Green means the
task is accepted with a journal note that no status was received; red means `FAILED` and one retry.
A missing status word is not itself a defect.

**The harness never re-invokes on a backgrounded dispatch.** `gtimeout` has already bounded the job,
so it is not still running. The orchestrator determines completion by inspecting the tree, which is
the gate anyway. This is the failure that stranded 3/3 workers in the first dogfood run; it now
costs a status word rather than the wave.

**A user picks a same-family reviewer deliberately.** Allowed. Preflight warns once; the manifest
stamps `independence: reduced`; Step 9 reads that field and weighs the `PASS` accordingly.

## Failure routing — new rows

| Situation | Response |
| --- | --- |
| `pi-watch` exit 6 (trailer missing or malformed) | No validated status. Fall through to tree evaluation: audit and run acceptance, accept on green, `FAILED` on red. Record the missing status. |
| Background dispatch never re-invokes the orchestrator | `gtimeout` bounds every dispatch, so the job terminates regardless; completion is decidable from the tree rather than from a notification |
| Any task retried after the wave-level audit | Re-run HEAD-check and scope-audit on that tree before its acceptance step |
| Worktree HEAD moved since dispatch | Worker committed and bypassed the audit; stop the task, surface |
| Cross-worktree contamination at wave end | Stop the wave, re-plan — same response as any scope violation |
| Reviewer alias unreachable at preflight | Offer the implementer flip; else `Task` path with a warning |

## Red Flags — new rows

| Rationalization | Why it fails |
| --- | --- |
| "pi workers are told to stay in the worktree, so the boundary holds." | The prompt is not a boundary; the audit is. pi has no sandbox, which is exactly why the audit went wave-level. |
| "The report clearly says DONE — close enough." | A claim never overrides a run. `DONE` with failing acceptance is `FAILED`, exactly as before; making the report advisory relaxed what a *missing* report costs, not what a *false* one buys. |
| "No report came back, so the task failed." | Absent is not failed. Audit the tree and run acceptance — the recorded dogfood failure lost a report while the commit survived, and treating that as a failure discards finished work. |

## Scope and non-goals

- **`quirk:executing-plans` is untouched.** It exists as the no-subagents fallback and runs
  sequentially in-session; adding a dispatch backend there changes what the skill is for and needs
  its own design pass. See Deferred Ideas.
- **No `pi-sonnet` / `pi-opus` implementer options.** Routing Claude models through pi buys nothing
  over `Task` subagents, loses permission gating, and adds metered spend.
- **No `--timeout` flag on pi-watch.** `quirk:pi-dev` already prescribes `gtimeout`/`timeout`
  wrapping, so the capability exists today without changing the wrapper.
- **Reviewer dispatch mechanism stays `quirk:adversarial-review`'s business.** This skill supplies
  an alias and a family; it does not choose between `pi-watch` and `Task` for reviewers.
- **No per-wave or per-task backend selection.** One choice per run.

## Decisions Locked

**Selection granularity**
- Backend is chosen once per run and fixed for the branch. Per-wave and per-task were rejected
  because they make the final loop's `RUN_BASE..HEAD` diff mixed-family, leaving no honest
  `author_family` for the most important review of the run.
- The choice is elicited by `AskUserQuestion` at preflight. A skill argument was rejected because
  `quirk:brainstorming` hands off without arguments, so on the main entry path the lever would not
  exist.
- Step 9 fixers inherit the implementer choice, keeping everything written into the branch
  single-family. "Fixers follow the reviewer family" was rejected explicitly: in round N+1 that
  reviewer would be reviewing its own family's fix.
- Default with no preference stated: Claude Sonnet subagents. Status quo, no metered spend, no
  behavior change for existing runs.

**Reviewer-family coupling**
- The reviewer is a second explicit `AskUserQuestion`, not a mechanical derivation. Deriving it
  silently was rejected in favor of making a deliberate same-family run possible and visible.
- Preflight checks only the chosen reviewer's alias, after the implementer choice is known.
- When the chosen reviewer family has no reachable model, preflight offers to flip the implementer
  choice — independence is load-bearing, the implementer preference is not.
- A codex-implemented branch is reviewed by whatever `select-model` resolves, with
  `adversarial-review`'s `Task` path as the backstop when pi cannot run at all.

**Containment and audit**
- pi implementer tool grant: `read,bash,edit,write`. `bash` is required because the TDD method
  depends on the worker watching its own test fail.
- The scope audit runs at wave end against every live worktree, each checked against its own task's
  scope.
- pi implementers may run parallel waves under the existing disjoint-scope rule. The rule does not
  care which model is writing.
- Dispatch is a backgrounded Bash call per task, because the 600s foreground ceiling cannot hold an
  implementer-scale task.
- The worker's report is advisory; tree state is the gate. Chosen over a background carve-out
  (whose justification the incident record does not support) and over staying foreground (the path
  that already lost a report in that same run). This is the only option that survives both
  documented failure modes, and it amends `SKILL.md:357–358`.

**Prompt portability**
- Shared prompt core plus one small pi delta file, appended by the orchestrator. Two fully
  self-contained files were rejected as the drift failure this skill's own Red Flags table warns
  about.
- The TDD discipline is inlined into the delta as a condensed red-green block, not pasted verbatim
  from `quirk:test-driven-development` (a pasted copy diverges silently) and not dropped (the two
  backends would build differently, invisibly).
- Status is extracted via a generic `--require-trailer` in `pi-watch`, with the implementer emitting
  `STATUS: <word>` on its own final line.

**pi-watch scope**
- `--cwd <dir>` and `--require-trailer <KEY>` are in scope. `--timeout` is not.

**Preflight option set**
- Two implementer options: Claude subagents, pi codex.

**Sibling skills**
- `quirk:executing-plans` does not get the backend choice this round.

## Industry Insights

(Offline mode — no research swarm was dispatched.) This work is internal to quirk's own skill
architecture rather than a domain with external literature, and the operating instructions for this
session prohibit dispatching subagents unless requested. Every constraint in this spec was derived
by reading the repository directly:

- `skills/subagent-driven-development/SKILL.md` — the review loop's `author_family` coupling and the
  gpt-5.6-sol pin.
- `skills/adversarial-review/assets/composition-contract.md` — `select-model` resolves a family
  different from the author's; `model` is a pi alias that overrides family selection.
- `skills/pi-dev/scripts/pi-watch/pi-watch.mjs:363` — `process.cwd()` is hard-coded; exit codes 0–5
  are taken.
- `skills/pi-dev/SKILL.md` — pi has no sandbox, no `--cd`, and no built-in timeout; `.mjs` updates
  propagate without reinstall.

## Deferred Ideas

- **Backend choice for `quirk:executing-plans`.** `pi-watch` is a bash dispatch, so it works on
  platforms with no `Task` tool at all. This would turn `executing-plans` from the degraded path
  into a parallel-capable one — a genuinely compelling change that roughly doubles this project's
  scope and rewrites a skill's stated purpose. Needs its own design pass.
- **A `FILES:` trailer alongside `STATUS:`.** A worker's self-reported file list, compared against
  the real diff, would make a claim/reality mismatch its own signal. Deferred because multi-key
  trailers make `--require-trailer` less trivially generic.
- **`--timeout` on `pi-watch`.** Deferred in favor of `gtimeout` wrapping, which works today.

## Glossary

| Term | Meaning |
| --- | --- |
| **Backend record** | The `IMPLEMENTER` / `AUTHOR_FAMILY` / `REVIEWER_ALIAS` triple resolved at preflight and stored in the run journal |
| **Dispatch block** | The single section of Step 5 that branches on `IMPLEMENTER`; referenced by Step 9 |
| **pi delta** | `assets/pi-worker-delta.md`, appended to the shared prompt core on the pi path |
| **Trailer** | A `KEY: value` line required as a worker's final output line, verified by `pi-watch --require-trailer` |
| **Wave-level audit** | Scope-auditing every live worktree against its own task's scope once the whole wave has returned |
| **Implementer flip** | Preflight's offer to change the implementer choice when the chosen reviewer family is unreachable, preserving cross-family independence |

## Status & amendments

**Amendments:**

- **2026-08-10** — Fable review round. Reviewer options constrained to `adversarial-review`'s
  6-alias table; corrected the claim that an explicit `model` walks a ladder (it does not, which
  makes preflight load-bearing); retried tasks re-enter the audit; `--require-trailer` widened to a
  3-line backward scan; HEAD verification restated as a heuristic; stale Roles table added to edit
  scope.
- **2026-08-10** — Dispatch decision reopened and changed. The original background carve-out
  asserted a `Task`-specific root cause the incident record does not support. Replaced with: tree
  state is the gate, the worker's report is advisory. This amends `SKILL.md:357–358` and is the
  most consequential change in this spec — flagged for the tech spec to treat as its own task.
