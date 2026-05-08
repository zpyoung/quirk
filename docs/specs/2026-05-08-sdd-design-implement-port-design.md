# Subagent-Driven Development — `/design:implement` Feature Port Design Spec

- **Date:** 2026-05-08
- **Plugin:** `quirk`
- **Affected skill:** `quirk:subagent-driven-development` (`quirk/skills/subagent-driven-development/SKILL.md`)
- **Companion changes:** `quirk:writing-plans` (lightweight plan-format extension), `quirk:using-git-worktrees` (integration usage)
- **Status:** approved for implementation planning

## 1. Problem

`quirk:subagent-driven-development` (SDD) executes implementation plans by dispatching one fresh subagent per task with a two-stage review (spec compliance → code quality). It is **strictly sequential** — its current Red Flags forbid parallel implementer dispatch on the assumption that concurrent subagents will conflict on the working tree. This is a real correctness guarantee but a steep efficiency cost: independent tasks that could run concurrently are forced to serialize.

The standalone `/design:implement` command (`~/Library/Mobile Documents/com~apple~CloudDocs/AI Agent/claude/commands/design/implement.md`) demonstrates two capabilities SDD lacks:

1. **Adaptive parallel execution** with a persistent `Team` of cooperative agents and file-cluster fix consolidation.
2. **Codex adversarial review** via `mcp__pal__clink` (cli_name=`codex`, role=`codereviewer`) as a third independent voice that reads files directly and flags spec/implementation gaps.

This spec ports those two capabilities into SDD while preserving SDD's "fresh subagent per task" core principle, and adds a third execution mode — **worktree-isolated parallel** — that uses `quirk:using-git-worktrees` to give parallel implementers physical filesystem isolation, eliminating the conflict question entirely. The orchestrator picks the right mode per wave; sequential is reserved for tasks with hard declared dependencies.

## 2. Scope

**In scope:**
- Three new execution modes added to SDD: **in-place parallel**, **worktree-isolated parallel**, **Team-mode parallel** (the rare cooperative case from `/design:implement`).
- Wave-based scheduler: orchestrator computes waves from declared dependencies, picks one mode per wave.
- A new third per-task review pass: **Codex adversarial review** (Claude path via PAL clink; Pi path via `pi -p` codex).
- `assets/codex-adversarial-prompt.md` and `assets/pi-codex-adversarial-prompt.md` prompt templates.
- Rolling auto-merge for worktree mode with a fresh **merge resolver** subagent on true conflicts.
- `assets/merge-resolver-prompt.md` and `assets/pi-merge-resolver-prompt.md` prompt templates.
- Lightweight, optional plan-format extension in `quirk:writing-plans`: `dependencies`, `independent`, `scope.files`, `cooperative` task fields. All optional; existing plans keep working.
- SKILL.md rewrite of: When to Use, Process, Runtime Selection, Prompt Templates, Red Flags, Integration sections.
- 2-cycle cap on Codex adversarial fix loop (mirrors `/design:implement`).

**Out of scope (deferred):**
- `--profile quality|balanced|budget` flag from `/design:implement`.
- Multi-design / multi-plan batch processing.
- Direct integration verification commands (`pnpm typecheck`, `pnpm test:e2e`) replacing the final whole-branch reviewer.
- Component+FR/NFR framing replacing SDD's task framing.
- `--force-team` or `--isolate` style override flags (orchestrator-picks is the v1 model).
- Cycle caps on the existing spec-compliance and code-quality review loops (those stay unbounded as today).
- Replacing or modifying the final whole-branch reviewer (stays `quirk:code-reviewer` on Claude, regardless of runtime).

## 3. Design decisions (locked from brainstorm)

| ID | Decision | Rationale |
|---|---|---|
| Q1 | Port specific features into SDD; SDD stays primary skill | Avoid merge/delegate complexity; keep SDD's per-task spine intact. |
| Q2 | Port (a) adaptive parallel execution and (b) Codex adversarial review only | Highest-leverage features; defer profile flag, multi-design batch, integration verification, FR/NFR framing. |
| Q3 | Codex adversarial slot = 3rd per-task pass, after spec compliance + code quality | Each existing reviewer keeps its current role; Codex catches what the others miss; complementary not redundant. |
| Q4 | Wave gate: plan declares first → orchestrator infers from declared scope when silent → serial fallback when ambiguous | Layered defaults: most accurate when plan is explicit; works on existing plans; safe fallback. |
| Q5 | Review timing in parallel mode: per-implementer chain fires as each finishes; chains run concurrently across the wave | Highest throughput; preserves SDD's per-task quality model; no wave-level review barrier. |
| Q6 | Conflict definition: only true overlapping-hunk git conflicts count; touching the same file is fine | Permissive parallelism; orchestrator handles only real conflicts via auto-resolution. |
| Q7 | Support all three parallel modes (in-place, worktree, Team); orchestrator picks per wave | Maximum efficiency: cheap in-place for tiny disjoint waves, isolated worktree for default multi-task, Team for rare cooperative cases. |
| Q8 | Drop Team mode is **not** chosen — Team kept for cooperative-interface negotiation cases | Rare but real; keeps full `/design:implement` capability set available without forcing it as default. |
| Q9 | Codex fix loop capped at 2 cycles; existing spec/quality loops stay unbounded | Mirrors `/design:implement`; bounds the new pass without changing existing review semantics. |

## 4. Architecture

### 4.1 Wave scheduling

After Runtime Selection, before any Task dispatch, the orchestrator runs a new **Step 0b — Compute waves**:

```text
Inputs:
  - Parsed task list from plan (each task has: id, title, body, optional dependencies/independent/scope/cooperative)
  - Runtime choice (Claude or Pi) — from existing Step 0 question

Algorithm:
  1. Topological sort tasks by declared `dependencies` field. Tasks with no deps are eligible for the first wave.
  2. Group eligible tasks into a wave such that every task in the wave is independent of every other task in the wave (no declared deps between them).
  3. For tasks that don't declare independence/deps explicitly: orchestrator inspects declared scope (e.g., `scope.files`, "Files Affected", "Touches" hints) and groups tasks with disjoint declared scope into the same wave. Tasks with no scope hints fall through to a singleton wave (sequential).
  4. After a wave completes (all tasks merged back / all reviews ✅), recompute eligible set and form the next wave.
```

`quirk:writing-plans` is extended (additive) with optional fields:

```yaml
- id: T1
  title: Implement hook installer
  independent: true
  scope:
    files: [bin/install-hook.sh, tests/test_install_hook.py]
  # ...
- id: T2
  title: Add recovery modes
  dependencies: [T1]
  cooperative: false
  # ...
```

All four fields (`independent`, `dependencies`, `scope.files`, `cooperative`) are optional. Plans without them produce singleton waves (= today's sequential behavior).

### 4.2 Per-wave mode decision

```text
for each wave:
  if |wave| == 1:
    mode = SEQUENTIAL
  elif any task in wave has cooperative: true:
    mode = TEAM
  elif |wave| <= N_INPLACE_THRESHOLD AND scopes provably disjoint at file level:
    mode = IN_PLACE_PARALLEL
  else:
    mode = WORKTREE_PARALLEL  # default for 2+ independent tasks
```

`N_INPLACE_THRESHOLD` defaults to **2**. "Provably disjoint at file level" means every task in the wave declares `scope.files` and no two tasks share any file path.

### 4.3 Mode mechanics

#### SEQUENTIAL (existing)
Single Task call; existing per-task pipeline (implementer → spec → quality → **Codex** → mark complete).

#### IN_PLACE_PARALLEL
1. Orchestrator dispatches all wave implementers in **one message turn** via multiple `Task` calls (or multiple `pi -p` invocations on the Pi path).
2. All implementers operate on the current branch in the current worktree.
3. As each implementer finishes, its three-pass review chain fires concurrently (per-implementer, not wave-batched).
4. By gate (4.2), in-place is only used when scopes are **provably disjoint at file level** — concurrent edits to the same file cannot happen, so the merge resolver is not invoked in this mode. If the gate is somehow violated and an implementer reports a `git` conflict during commit, the wave is aborted and the user is escalated to (this is a gate bug, not a normal flow).

#### WORKTREE_PARALLEL (default for 2+ independent tasks)
1. For each task in the wave, orchestrator creates a worktree on a task-named branch via `quirk:using-git-worktrees`. Branch naming convention: `<parent-branch>/sdd/<task-id>`.
2. All wave implementers dispatched in **one message turn**, each into its own worktree.
3. Per-task review chain (spec → quality → Codex) runs **inside the worktree on the implementer's commits**, before merge. Reviewers see clean isolated diffs.
4. When a task's chain ✅, orchestrator runs **rolling auto-merge**: `git merge --no-ff <branch>` from the parent branch. Merges are sequential (one at a time) as tasks finish; no wave-level barrier.
5. On true overlapping-hunk conflict during merge: orchestrator dispatches the merge resolver subagent. Worktree is preserved until resolution.
6. After successful merge, worktree is torn down via `quirk:using-git-worktrees`.

#### TEAM (rare, opt-in via `cooperative: true`)
Adopts `/design:implement`'s Team-mode pattern verbatim: TeamCreate → spawn all wave implementers in one message turn → TaskList coordination → SendMessage for cross-component negotiation → TeamDelete after wave completes. Per-task review chain fires per implementer as each completes. This is the only mode where a "fresh subagent per task" guarantee is relaxed within a wave; the relaxation is justified only when tasks need live negotiation.

### 4.4 Review chain extension

Per-task review pipeline (all modes):

```text
implementer
  → spec compliance reviewer       (existing)
  → code quality reviewer          (existing)
  → Codex adversarial reviewer     (NEW — gap-finding, severity-tagged)
  → mark task complete
```

Codex adversarial reviewer:
- **Claude path:** `mcp__pal__clink` with `cli_name="codex"`, `role="codereviewer"`, `absolute_file_paths=[<implementer's files>]`, prompt = `assets/codex-adversarial-prompt.md` (adapted from `/design:implement`'s Codex Review Prompt — adversarial gap-finder, not a validator).
- **Pi path:** `pi -p` codex (`openai-codex/gpt-5.3-codex:xhigh`) with `--tools read,bash` (read-only review), prompt = `assets/pi-codex-adversarial-prompt.md`.
- Output: SEVERITY-tagged findings (`CRITICAL | HIGH | MEDIUM | LOW`), file:line citations, suggested fixes, `VERDICT: PASS | NEEDS_FIXES | CRITICAL_ISSUES`.
- **Fix loop:** CRITICAL/HIGH findings are fixed by the **same implementer subagent** (re-dispatched with the findings). After fix, Codex re-reviews. **Cap: 2 cycles.** After cycle 2, remaining CRITICAL/HIGH are reported as unresolved and the task is marked complete with a flag for the final whole-branch reviewer to revisit. MEDIUM noted in final report. LOW/NONE → task complete.

### 4.5 Merge resolver (worktree mode only)

Triggered when `git merge` reports conflicts:

```text
Merge resolver subagent receives:
  - both branches' diffs
  - list of conflict markers and affected files
  - task spec context for both involved tasks

Job:
  - Read both sides of each conflict
  - Pick the correct resolution (or synthesize a merged version)
  - Commit the resolution
  - Report SUCCESS | UNRESOLVABLE
```

If `UNRESOLVABLE`: orchestrator escalates to user with a structured report; the worktree and conflicted state are preserved. The user can resolve manually or abort the wave.

Claude path: `Task` (general-purpose) + `assets/merge-resolver-prompt.md`.
Pi path: `pi -p` codex + `assets/pi-merge-resolver-prompt.md`.

### 4.6 Updated runtime matrix

| Role | Claude path | Pi path |
|---|---|---|
| Implementer | `Task` (general-purpose) + `assets/implementer-prompt.md` | `pi -p` codex + `assets/pi-implementer-prompt.md` |
| Spec reviewer | `Task` (general-purpose) + `assets/spec-reviewer-prompt.md` | `pi -p` gemini + `assets/pi-spec-reviewer-prompt.md` |
| Code-quality reviewer | `Task` (quirk:code-reviewer) + `assets/code-quality-reviewer-prompt.md` | `pi -p` gemini + `assets/pi-code-quality-reviewer-prompt.md` |
| **Codex adversarial reviewer (NEW)** | `mcp__pal__clink` (codex, codereviewer) + `assets/codex-adversarial-prompt.md` | `pi -p` codex (`--tools read,bash`) + `assets/pi-codex-adversarial-prompt.md` |
| **Merge resolver (NEW, worktree mode only)** | `Task` (general-purpose) + `assets/merge-resolver-prompt.md` | `pi -p` codex + `assets/pi-merge-resolver-prompt.md` |
| Final whole-branch reviewer | `Task` (quirk:code-reviewer) — unchanged | `Task` (quirk:code-reviewer) — unchanged |

## 5. Process flow (revised)

```text
Step 0   — Ask: pi or Claude runtime?
Step 0b  — Read plan, extract tasks, compute waves (NEW)
Step 1   — For each wave:
             a) Pick mode per 4.2
             b) If WORKTREE_PARALLEL: create worktrees via quirk:using-git-worktrees
             c) Dispatch all wave implementers in one message turn (or single Task call for SEQUENTIAL)
             d) For each implementer: as it finishes, run per-task review chain (spec → quality → Codex)
             e) Handle reviewer NEEDS_FIX → re-dispatch implementer → re-review (Codex capped at 2 cycles)
             f) On task ✅ in WORKTREE mode: rolling auto-merge to parent branch; teardown worktree
             g) On true merge conflict: dispatch merge resolver; on UNRESOLVABLE, escalate
             h) Mark each task complete in TodoWrite as its chain ✅ + (in worktree mode) merge ✅
Step 2   — After all waves complete: dispatch final whole-branch reviewer (Claude quirk:code-reviewer, regardless of runtime — unchanged)
Step 3   — Use quirk:finishing-a-development-branch
```

## 6. Red Flags (revised)

**Removed:**
- ~~"Dispatch multiple implementation subagents in parallel (conflicts)"~~

**Added:**
- "Skip the wave gate / dispatch parallel implementers without computing a wave"
- "Run reviews against a merged branch instead of the worktree's pre-merge commits"
- "Auto-merge a worktree branch before its review chain has ✅"
- "Force resolve a merge conflict manually as orchestrator instead of dispatching the merge resolver"
- "Exceed 2 Codex adversarial fix cycles"

**Kept:**
- All existing per-task discipline red flags (skip reviews, accept "close enough", etc.)
- "Start implementation on main/master branch without explicit user consent"

## 7. Integration

**Required workflow skills (unchanged set; usage shifts):**
- `quirk:using-git-worktrees` — **now load-bearing** in WORKTREE_PARALLEL mode (per-task worktree creation/teardown)
- `quirk:writing-plans` — gets the optional plan-format extension (Section 4.1)
- `quirk:requesting-code-review` — review template for reviewer subagents
- `quirk:finishing-a-development-branch` — terminal step

**Required when pi runtime is selected:**
- `quirk:pi-dev` — canonical hardened dispatch recipe; failure detection now also covers Codex (pi) and merge resolver (pi) workers

**Subagents should use:**
- `quirk:test-driven-development` — unchanged

## 8. Implementation surface

Files added or modified:

```text
quirk/skills/subagent-driven-development/
├── SKILL.md                                      [REWRITTEN: When to Use, Process, Runtime, Red Flags, Integration]
├── assets/
│   ├── implementer-prompt.md                     [unchanged]
│   ├── spec-reviewer-prompt.md                   [unchanged]
│   ├── code-quality-reviewer-prompt.md           [unchanged]
│   ├── pi-implementer-prompt.md                  [unchanged]
│   ├── pi-spec-reviewer-prompt.md                [unchanged]
│   ├── pi-code-quality-reviewer-prompt.md        [unchanged]
│   ├── codex-adversarial-prompt.md               [NEW]
│   ├── pi-codex-adversarial-prompt.md            [NEW]
│   ├── merge-resolver-prompt.md                  [NEW]
│   └── pi-merge-resolver-prompt.md               [NEW]

quirk/skills/writing-plans/
└── SKILL.md                                      [LIGHT EDIT: document optional task fields]
```

No changes to `quirk:using-git-worktrees`, `quirk:pi-dev`, `quirk:code-reviewer`, or `quirk:finishing-a-development-branch`.

## 9. Success criteria

- SDD detects plans with `independent`/`dependencies`/`scope.files` fields and forms multi-task waves correctly.
- SDD on plans without these fields behaves identically to today (singleton waves → sequential).
- WORKTREE_PARALLEL: parallel implementers operate in isolated worktrees, all per-task reviews run pre-merge, rolling auto-merge succeeds for non-conflicting branches.
- Merge resolver subagent is dispatched on true conflicts and either resolves or escalates cleanly (worktree preserved on UNRESOLVABLE).
- Codex adversarial review fires after spec compliance + code quality on every task, in every mode, on both runtimes.
- Codex fix loop respects the 2-cycle cap; unresolved CRITICAL/HIGH findings carry forward to the final whole-branch reviewer.
- Final whole-branch reviewer remains `quirk:code-reviewer` on Claude, regardless of runtime selection.
- All new prompt templates referenced from SKILL.md exist and are syntactically consistent with existing assets.

## 10. Deferred ideas

- `--profile quality|balanced|budget` flag (from `/design:implement`).
- Multi-design / multi-plan batch processing.
- Direct integration verification commands (`pnpm typecheck`, `pnpm test:e2e`) bypassing the final whole-branch reviewer.
- Component+FR/NFR framing alongside or replacing task framing.
- `--force-team` / `--isolate` user-overrides for mode selection.
- Caps on the spec-compliance and code-quality fix loops.
- Cross-task / cross-wave Codex review (over the whole wave's combined files, in addition to per-task).
- File-cluster fix consolidation (`/design:implement`'s anti-conflict guard) — not needed because conflicts are eliminated by worktree isolation in v1.
