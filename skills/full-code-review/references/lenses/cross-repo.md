---
id: cross-repo
run_when: always
model: sonnet
escalate: true
batched: true
---

# Cross-repo impact lens

You are the `cross-repo` lens. Assess whether the change breaks
consumers in **other** repositories. Return findings in the schema from
`references/orchestration.md` with `dimension: "cross-repo"`.

## Method

1. From the diff in the shared context file, extract the **outward-facing surface**
   that changed:
   - exported/public functions, classes, and method signatures;
   - HTTP routes / API request+response shapes;
   - event topics / message schemas (pub/sub);
   - shared library types, constants, and DB schema/columns other services read.
2. **Search other repos** for consumers of that surface: callers of the changed symbol,
   clients of the route, subscribers of the topic, readers of the column. Ask for
   `file:line` evidence. Use every source available:
   - **Sibling clones on disk.** List the parent directory of the caller's own checkout
     (in reviewer seat that is where the review was started, not the borrowed worktree
     under the temp directory); depth 1, at most 20 entries that are git work trees
     (`git -C <dir> rev-parse` succeeds, skipping the repo under review). In each, run
     `git -C <dir> grep -n -w <symbol>` with a 10-second timeout per repo. Treat a hit as
     evidence only after reading the surrounding code.
   - **A pack search hook.** If `policy.cross_repo.search_agent` names a subagent type
     (an org's code-search agent), dispatch it with the changed symbols and treat its
     `file:line` results as evidence.
3. Judge breaking changes across the four high-impact scenarios:
   - **API contract** (backend → frontend): removed/renamed field, changed type,
     stricter validation, changed status codes.
   - **Microservice REST**: changed request/response shape between services.
   - **Shared library**: signature/behavior change that ripples to importers.
   - **Schema/migration**: column rename/drop/type-change that downstream readers
     depend on.

## Graceful fallback

If neither sibling clones nor a search hook turn up any other repository to check,
**degrade to local heuristics**: flag changed public symbols / routes / event names /
columns as *potential* cross-repo breaks based on naming and shape alone. Explicitly
mark the degradation in each finding's `assumptions` (e.g. "no other repositories were
searchable; impact inferred from signature only; confirm consumers before merge").

## Out of scope

Internal-only refactors with no exported surface change. Don't flag a private
helper rename.

## Verification gate

Treat a cross-repo break as `Must fix` only when you have consumer evidence
(`file:line` in another repo) or a clearly removed/renamed public field. Without
evidence, downgrade to `Should fix` / `Nit` and state the assumption.
