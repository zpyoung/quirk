# Multi-Agent Orchestration with Headless Pi

Pi has no opinion on multi-agent topology. It ships as a single agent; orchestration is something you build on top using the headless modes.

This document covers the underlying primitives for building a multi-worker pipeline with adversarial review, integration tests, in-place vs worktree mode, model matrix, and cycle caps.

## The canonical pattern

```
Orchestrator (SDK AgentSession or interactive pi)
  ├─ spawns: pi --mode rpc --no-session  (worker A — backend slice)
  ├─ spawns: pi --mode rpc --no-session  (worker B — frontend slice)
  └─ spawns: pi --mode rpc --no-session  (worker C — review pass)

Coordination: orchestrator → `prompt` commands → workers
              workers → `agent_end` events → orchestrator
```

## Topology choices

### Two-tier (orchestrator + workers)

Most useful pattern. Orchestrator decomposes the task and dispatches one worker per slice. Workers run in parallel when slices are file-disjoint, sequential when they share files.

### Three-tier (orchestrator → team leads → workers)

Useful when slice count exceeds what a single orchestrator can manage cleanly. Each team lead is itself a pi RPC subprocess that the orchestrator dispatches to; the team lead in turn spawns its own worker subprocesses. Pi places no constraints on this — it just costs more subprocesses.

## Parallelism

### Node.js: `Promise.all` over RPC subprocesses

```typescript
const workers = slices.map(slice => spawnRpcWorker(slice));
const results = await Promise.all(workers.map(w => w.runToCompletion()));
```

Each worker is its own pi subprocess with its own state and its own LLM API connection. The orchestrator just multiplexes JSONL streams.

### Shell: tmux session matrix

For a non-Node orchestrator, run each worker in a tmux pane and harvest output via tmux's pipe-pane or per-worker log files.

## Filesystem isolation

Pi has **no built-in sandbox**. If two workers run in the same cwd at the same time, their edits will interleave and overwrite each other.

Options, ranked by safety:

1. **Git worktrees** — one worktree per worker, all branched off the same base SHA. Workers run in parallel; orchestrator merges branches afterward.
   - **Serialize `git worktree add`** ([anthropics/claude-code#34645](https://github.com/anthropics/claude-code/issues/34645)) — concurrent invocations race on `.git/config.lock`. After all worktrees exist, workers run parallel.
2. **Containers / VMs** — heavier but stronger isolation; supports multi-repo.
3. **Sequential workers in the same cwd** — simplest, but no parallelism.
4. **`pi -e ./sandbox` extension** — exists but adds setup overhead; not enabled by default.

## Coordination patterns

### Fan-out / fan-in

Orchestrator → N parallel workers → orchestrator waits for all `agent_end` → consolidates results into next step.

### Pipeline

Each stage is a separate pi invocation, output of stage N is `@`-included as input to stage N+1:

```bash
pi --print --no-session --offline --tools read --model flash \
  "Summarize the architecture" > summary.md

pi --print --no-session --offline --tools read,bash,edit,write --model sonnet \
  @summary.md "Implement the auth module per the summary"
```

### Adversarial review

Worker (full toolset) makes edits. Reviewer (`--no-tools`) reads only the materialized diff and emits a JSON verdict. Different provider/model is the standard practice — same-provider review tends to share the worker's blind spots.

## Failure handling at scale

Same rules as single-worker (see main `SKILL.md`):

1. Auth/billing failures abort the whole run — they hit every worker the same way; don't burn budget on retries.
2. Rate limits are retriable with backoff.
3. Timeouts (`gtimeout` exit 124) kill that slice only.
4. Unparseable reviewer output → treat as `NEEDS_FIX` with a synthetic finding; never count as PASS.

In parallel mode, on abort: track each worker's wrapper PID at dispatch time, then `kill -TERM` the wrapper and `pkill -TERM -P <pid>` for safety, escalating to `KILL` after 5 seconds. `kill $(jobs -p)` alone is unreliable because SIGTERM may not propagate through nested `bash -c` wrappers to the inner pi process. `gtimeout --foreground` helps because it keeps the process group attached so signals reach all the way down.

## Token-usage aggregation across workers

Per-worker, scan each `events.jsonl` for any `usage`/`tokens`/`contextUsage` field (best-effort — schema is not officially stable). Aggregate by phase, by slice, by cycle. Mark "not captured" rather than fabricating where pi didn't emit anything matching.

## Reproducibility

Do NOT use `--continue` / `--session <id>` for resumption in orchestrated runs. Re-dispatch with prior context inlined into the prompt instead. Reasons:

- Session state can change format between pi versions.
- Inlined context is auditable in the prompt log.
- It avoids hidden coupling between dispatches.

## Cost discipline

- Cap each worker's budget — `gtimeout` for wall-clock, prompt design for token cap (until `--max-turns` / `--max-tokens` ship).
- Use `--no-session` everywhere in orchestration: session writes cost disk and complicate reproducibility.
- Use `--offline` to skip the startup update probe — small but real on parallel batches.
- Cheap models for pre-analysis / extraction; expensive models for the actual edit step. The print-mode pipeline pattern makes this trivial.

## Building blocks for a full orchestration loop

A production orchestration layer on top of headless pi typically encodes:

- Slice decomposition with `task_type` / `complexity` model matrix
- In-place vs worktree mode with iCloud / clean-cwd / protected-branch gates
- Cycle-1 → review → cycle-2 → integration → test-fix flow
- Per-cycle JSONL/stderr/exit-code/commit-sha capture
- Reviewer JSON parse cascade with synthetic-finding fallback
- Auth/billing/rate-limit failure short-circuit
- Cleanup (worktrees, branches, log dirs)

Each of these maps onto the primitives in this skill (canonical dispatch recipe, failure detection, reviewer JSON cascade, token-usage extraction, RPC framing, SDK session/branch APIs). Compose them at the orchestration layer of your choice — Node SDK, Python RPC client, shell script — based on what host the orchestrator runs in.
