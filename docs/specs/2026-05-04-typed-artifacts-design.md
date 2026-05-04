# Typed Artifacts — Design Spec

- **Date:** 2026-05-04
- **Plugin:** `quirk` (existing) → version bump 5.0.7 → 5.1.0
- **Feature module:** typed-artifacts (additive)
- **Status:** approved for implementation planning

## 1. Problem

Claude Code sessions generate two kinds of output: work that gets done, and observations the model surfaces but cannot act on (deferred bugs, architectural concerns, skipped tests, out-of-scope issues). The second category has no sanctioned destination in a default workflow, so the model improvises — burying observations in prose, coining tics like "pre-existing" or "out of scope," or silently dropping them. Suppression via CLAUDE.md prohibition fails structurally: the observation gets generated first, and without a typed destination the suppression either produces a different tic or loses the signal.

The discipline this spec implements — **Surface Routing via Typed Artifacts** — pairs every prohibition with a structured file destination. The model doesn't stop noticing; it routes. Each artifact has a fixed schema, append-only semantics during work, named ownership, and a back-link to triggering context.

## 2. Scope

**In scope (v1):**
- Five artifact types: `BUGS.md`, `DEFERRED.md`, `TEST_BACKLOG.md`, `proposals.md`, plus `docs/adr/` directory (Nygard ADRs).
- Seven slash commands under `/quirk:artifacts:*`.
- One skill (`typed-artifacts`) carrying rules + schemas.
- Three lifecycle hooks: SessionStart, PostToolUse, Stop. All warn-only, none block.
- Four Python mutation scripts (stdlib-only, Python 3.9+).
- Templates for each artifact + tic-phrase config + CLAUDE.md trigger snippet.

**Out of scope (deferred to v2):**
- `SECURITY_NOTES.md`, `PERF_NOTES.md`, `TECH_DEBT.md` (additional artifact types).
- Configurable artifact location (always project root in v1).
- Cross-repo `workflow.json` artifact routing.
- `/promote`, `/artifact-cleanup`, `/artifact-status` commands.
- Lifecycle transitions on ADR status (creation only in v1).
- UserPromptSubmit hook injecting artifact index every turn.

## 3. Design decisions (locked from brainstorm)

| ID | Decision | Rationale |
|---|---|---|
| Q1 | Core 4 artifacts + ADR directory | Hits research-named tic categories; SECURITY/PERF/TECH_DEBT deferred until pattern proves out. |
| Q2 | Artifacts live in user's project root | Visibility is the antidote to artifact rot; PR review is the natural cadence. |
| Q3 | Hooks warn-only, never block | Block-on-violation inherits a known PostToolUse-context-injection bug; warn-only preserves flow. |
| Q4 | SessionStart detect-and-suggest, opt-in `/init` | Discoverable nudge without surprise project mutation. |
| Q5 | Skill + lightweight CLAUDE.md trigger | Progressive disclosure: 5-line CLAUDE.md trigger + on-demand skill carries the schema weight. |
| Q6 | Per-artifact shortcuts + triage + review + init | `/triage` for ad-hoc routing, shortcuts for common case, `/adr` structurally distinct. |
| Q7 | Plugin module name: `typed-artifacts` (inside quirk) | Concrete-deliverable naming; matches user's marketplace conventions. |
| Q8 | Slash command namespace: `/quirk:artifacts:*` | Subdir `commands/artifacts/`; tab-completion groups all 7. |
| Approach | Script-backed (Approach 2) | Determinism on appends matters; pure-prompt risks ID collisions and schema drift. |

## 4. Architecture

The plugin becomes an additive module inside `~/ProjectWorkspaces/quirk-workspace/quirk/`. Quirk's existing 15 skills are untouched. New directories are introduced for the first time: `commands/`, `hooks/`, `bin/`, `templates/`.

```
quirk/                                   (existing plugin, additions only)
├── .claude-plugin/plugin.json           # bump version → 5.1.0; add keyword
├── skills/
│   ├── ...existing 16 skills...
│   └── typed-artifacts/SKILL.md         # NEW — surface-routing rules + schemas
├── commands/                            # NEW (no commands existed in quirk)
│   └── artifacts/
│       ├── init.md
│       ├── triage.md
│       ├── review-artifacts.md
│       ├── bug.md     defer.md     test-skip.md     adr.md
├── hooks/                               # NEW
│   ├── hooks.json                       # SessionStart, PostToolUse, Stop
│   ├── load_artifact_tail.sh
│   ├── lint_tics.sh
│   └── wrap_session.sh
├── bin/                                 # NEW (Python 3.9+, stdlib-only)
│   ├── artifact_append.py
│   ├── adr_create.py
│   ├── artifact_init.py
│   └── artifact_review.py
└── templates/                           # NEW
    ├── BUGS.md         DEFERRED.md
    ├── TEST_BACKLOG.md proposals.md
    ├── adr/0000-record-architecture-decisions.md
    ├── claude_md_snippet.md
    └── tic_phrases.json
```

### Architecture-level guarantees

1. **Determinism on writes.** Every artifact mutation routes through `bin/*.py`. Claude never edits artifact files directly via Edit/Write. ID counters, required fields, and append-only invariants are enforced in code.
2. **Inert-by-default in non-typed-artifacts projects.** All hooks gate on file presence (`[[ -f "$CLAUDE_PROJECT_DIR/BUGS.md" ]]`) and exit 0 silently when artifacts haven't been initialized. Net cost in a fresh quirk project: one filesystem stat per hook event. Existing quirk users see no behavior change until they run `/quirk:artifacts:init`.
3. **Hooks observe but never block.** Every hook script ends in `exit 0`. A flaky linter cannot trap the user.

### Boundary clarity

| Unit | Talks to | Talks back via |
|---|---|---|
| Slash commands | the user | one-line confirmations |
| Skill | Claude (on description match) | rules table + schema reference |
| Hooks | Claude Code lifecycle | `systemMessage` (warn-only) |
| Mutation scripts | the filesystem | exit codes + stdout/stderr |
| Templates | nothing (inert) | source-of-truth for `/init` |

Each unit testable in isolation.

## 5. Components

### 5.1 Plugin manifest (`.claude-plugin/plugin.json`)
- Bump `version` to `5.1.0`.
- Add `"typed-artifacts"` and `"surface-routing"` to `keywords`.
- No structural schema additions.

### 5.2 Skill (`skills/typed-artifacts/SKILL.md`)
Single skill carrying:
- Surface-routing rules table (tic phrase → artifact destination).
- All five schemas (BUGS, DEFERRED, TEST_BACKLOG, proposals, ADR) — by reference to `templates/`, not duplicated.
- Tic-phrase → artifact-type mapping.
- Worked example entries.
- `description` frontmatter listing trigger phrases ("typed artifact," "BUGS.md," "route observation," "log a bug," "out of scope," "skipped test").

**Interface:** progressive disclosure via `Skill` tool.
**Depends on:** `templates/` (for canonical schema text).

### 5.3 Slash commands (`commands/artifacts/*.md`)

| Command | Delegates to | Required args | Behavior |
|---|---|---|---|
| `init.md` | `bin/artifact_init.py` | none | Idempotent scaffold: artifact files + ADR-0000 + appends snippet to user CLAUDE.md (with confirmation) |
| `bug.md` | `bin/artifact_append.py bug …` | file:line, description, severity | Append BUG-N entry |
| `defer.md` | `bin/artifact_append.py defer …` | title, why-deferred, priority | Append DEFER-N entry |
| `test-skip.md` | `bin/artifact_append.py test-skip …` | file-under-test, reason-skipped | Append TEST-N entry |
| `triage.md` | `bin/artifact_append.py <category> …` | observation text | Prompt classifies category, then dispatches |
| `adr.md` | `bin/adr_create.py …` | title | Creates new `docs/adr/NNNN-kebab-title.md` from Nygard template |
| `review-artifacts.md` | `bin/artifact_review.py` | none | Read-only scan; lists unresolved entries grouped by priority |

Each command file is 20–60 lines: parse `$ARGUMENTS`, invoke script via `Bash`, relay confirmation. Missing-argument handling via single clarifying question rather than guessing.

### 5.4 Hooks (`hooks/hooks.json` + `.sh` scripts)

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "*",
      "hooks": [{ "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/load_artifact_tail.sh" }]
    }],
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{ "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/lint_tics.sh" }]
    }],
    "Stop": [{
      "matcher": "*",
      "hooks": [{ "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/wrap_session.sh" }]
    }]
  }
}
```

| Script | Purpose | On no-artifacts | On error |
|---|---|---|---|
| `load_artifact_tail.sh` | Cat tail of artifact files (~50 lines, 1MB cap); else suggest `/init` via systemMessage | Suggest init | Exit 0 silent |
| `lint_tics.sh` | Grep modified file for tic phrases from `tic_phrases.json`; emit systemMessage on match | Skip | Exit 0 silent |
| `wrap_session.sh` | Wrap-up reminder via systemMessage | Skip | Exit 0 silent |

**Universal hook contract:** all paths exit 0. No script blocks.

### 5.5 Mutation scripts (`bin/*.py`)

Four CLI scripts, stdlib-only, Python 3.9+, `from __future__ import annotations` at top.

**`artifact_append.py <type> --field key=value …`**
- Reads target artifact in `$CLAUDE_PROJECT_DIR/`.
- Parses existing entries, finds `max(<TYPE>-N)`, appends `<TYPE>-(N+1)`.
- Schema is a single dict at top of `artifact_append.py` (one entry per artifact type), kept in sync with the templates' schema-comment headers.
- Validates required fields; missing → exit 2.
- Atomic via `flock` on `.<artifact>.lock` (5s timeout → exit 5).
- Schema-version check; mismatch → exit 8.

**`adr_create.py --title "…" [--status proposed]`**
- Globs `docs/adr/[0-9][0-9][0-9][0-9]-*.md` for max NNNN.
- Creates `NNNN-kebab-title.md` from Nygard template.
- Empty kebab → exit 2; collision → retry up to 3×.

**`artifact_init.py [--force] [--no-claude-md]`**
- Copies `templates/` → `$CWD` (refuses overwrite without `--force`).
- Creates `docs/adr/` and ADR-0000 if missing.
- Appends `claude_md_snippet.md` to existing `CLAUDE.md` (or creates one) unless `--no-claude-md`. Detects existing snippet via `<!-- quirk-typed-artifacts:trigger -->` marker.
- Idempotent: re-run shows what's already present, fills gaps only.
- `--force` backs up to `BUGS.md.bak.<timestamp>` before overwriting.

**`artifact_review.py`**
- Read-only.
- Walks BUGS, DEFERRED, TEST_BACKLOG, proposals, `docs/adr/`.
- Outputs grouped summary (priority × file) on stdout.
- No mutation.

**Interface:** standard CLI (`argparse`). All scripts pure; testable via fixtures.
**Depends on:** stdlib only.

### 5.6 Templates (`templates/`)

Inert source-of-truth files copied verbatim by `artifact_init.py`. Each carries its schema as a top-of-file comment block (research's "schema at the top" pattern) and a `<!-- schema-version: 1 -->` marker. `tic_phrases.json` is a list of regex patterns the linter greps for. `claude_md_snippet.md` is the 5-line trigger appended to user CLAUDE.md.

## 6. Schemas

All schemas marked `<!-- schema-version: 1 -->`. All artifacts are append-only via the mutation scripts — i.e., scripts never rewrite or reorder existing entries. Manual user edits (fixing a typo in BUG-3, marking PROPOSAL-7 as accepted) are explicitly allowed; the scripts re-parse the file on every run, so manual changes don't break subsequent appends.

### BUGS.md entry
```markdown
## BUG-[N]: [Short title]
- **Observed**: [date or session ID]
- **File**: [path/to/file.ts:line]
- **Description**: [what the bug is]
- **Introduced by**: [this session / unknown / commit SHA]
- **Severity**: [critical / high / medium / low]
- **Proposed fix**: [one sentence]
- **Blocker for**: [what this would break]
```
Required: title, file, description, severity. Others optional but encouraged.

### DEFERRED.md entry
```markdown
## DEFER-[N]: [Task title]
- **Deferred**: [date]
- **Session context**: [what triggered this]
- **Why deferred**: [out of scope / blocked on / requires decision]
- **Estimated effort**: [S/M/L]
- **Priority**: [P1–P4]
- **Proposed owner**: [Claude / name / unassigned]
```
Required: title, why-deferred, priority.

### TEST_BACKLOG.md entry
```markdown
## TEST-[N]: [Function or behavior to test]
- **File under test**: [path]
- **Test type**: [unit / integration / e2e]
- **Reason skipped**: [time / complexity / mocking required / TBD]
- **Edge cases to cover**: [list]
- **Priority**: [P1–P4]
```
Required: file-under-test, reason-skipped.

### proposals.md entry
```markdown
## PROPOSAL-[N]: [Title]
- **Proposed**: [date]
- **Context**: [neutral description]
- **Options considered**: [Option A / Option B / ...]
- **Recommendation**: [with rationale]
- **Decision required from**: [human / team / architect]
- **Status**: [proposed / accepted / rejected / superseded]
```
Required: title, context, recommendation.

### ADR (`docs/adr/NNNN-kebab-title.md`)
Michael Nygard template:
```markdown
# NNNN. [Title]

- **Status:** proposed
- **Date:** [YYYY-MM-DD]

## Context
[neutral, pre-decision facts]

## Decision
[the decision]

## Consequences
[positive / negative / neutral]
```
Required: title, status. Lifecycle transitions (accepted/superseded) handled via plain edits in v1.

## 7. Data flows

### 7.1 First-time setup
```
SessionStart → load_artifact_tail.sh: artifacts missing → systemMessage suggests /init
User: /quirk:artifacts:init
  → artifact_init.py: copy templates, create ADR-0000, append CLAUDE.md snippet
  → confirmation summary
```

### 7.2 Append-an-entry (hot path)
```
User: /quirk:artifacts:bug auth fails on safari, login.ts:42, severity=high
  → command parses $ARGUMENTS
  → artifact_append.py bug --file=... --description=... --severity=high
  → flock → read BUGS.md → max BUG-N → append BUG-(N+1) → release lock
  → stdout: "BUG-7: auth fails on safari"
  → command relays: "Logged BUG-7 → BUGS.md"
```

### 7.3 Triage (auto-classification)
```
User: /quirk:artifacts:triage "OAuth retry loop edge case"
  → command prompt: classify (bug/defer/test-skip/proposal), extract fields per chosen schema
  → invoke artifact_append.py <category> ...
  → joins 7.2 from script invocation. Script re-validates required fields per schema.
```
**Misclassification handling:** the script re-validates required fields but does not second-guess the category. If Claude routes a bug as a defer, the entry lands in `DEFERRED.md` and the user can move it manually (artifacts are plain markdown). The skill instructs Claude to ask one clarifying question rather than guess between two equally valid categories.

### 7.4 ADR creation
```
User: /quirk:artifacts:adr "Switch session storage from JWT to opaque tokens"
  → adr_create.py --title "..."
  → glob docs/adr/[0-9]{4}-*.md → next NNNN → kebab(title) → write file
  → stdout: "ADR-0008: Switch session storage..."
```

### 7.5 Background enforcement
```
PostToolUse on Edit|Write → lint_tics.sh:
    grep tic patterns → match → systemMessage warning → exit 0
                     → no match → exit 0

Stop → wrap_session.sh:
    artifacts present → systemMessage("Route any unrouted observations") → exit 0
    artifacts absent  → exit 0
```

### Invariants enforced

1. **Atomic mutation.** `flock` on every artifact write; concurrent calls cannot collide on `<TYPE>-N` IDs.
2. **Read-then-write.** Scripts re-parse the file on every invocation. No cached counters.
3. **Hooks never block.** All paths exit 0.

## 8. Error handling

### `artifact_append.py`
| Failure | Exit | Message |
|---|---:|---|
| Missing required field | 2 | `Missing required field: severity. See schema in templates/BUGS.md` |
| Unknown artifact type | 2 | `Unknown type 'bgu'. Valid: bug, defer, test-skip, proposal` |
| Target file missing | 3 | `BUGS.md not found in $CWD. Run /quirk:artifacts:init first.` |
| Corrupt entry mid-file | 4 | `Could not parse BUGS.md (last good: BUG-6 at line 84)` — no append |
| Lock contention >5s | 5 | `Could not acquire lock. Retry.` |
| Disk/permission | 6 | passthrough OS error |
| Schema-version mismatch | 8 | `Schema v2 file, plugin understands v1. Upgrade quirk.` |

### `artifact_init.py`
- Existing artifact → skip with `BUGS.md already present (N entries) — skipped.`
- Existing CLAUDE.md trigger marker → skip snippet append.
- Missing CLAUDE.md → create with snippet only.
- `--force` → backup existing to `<file>.bak.<timestamp>` before overwrite.
- Project dir not writable → exit 7, no partial state.

### `adr_create.py`
- Missing `docs/adr/` → create.
- Empty kebab title → exit 2.
- NNNN-collision (race) → retry up to 3× → exit 5.

### Hooks (universal contract: `exit 0` always)
- `tic_phrases.json` missing/invalid → skip lint, exit 0.
- `grep` not on PATH → skip lint, exit 0.
- `$CLAUDE_PROJECT_DIR` unset → skip, exit 0.
- Binary file modified → skip lint, exit 0.
- Artifact >1MB → skip tail load, log warning, exit 0.

### Slash commands
- Missing arguments → ask user one clarifying question, do not guess.
- Triage ambiguous → surface both options to user, do not pick.
- Script non-zero exit → relay stderr verbatim + plain-language summary + remediation hint.

### Schema versioning
- Templates carry `<!-- schema-version: 1 -->` marker.
- `artifact_append.py` refuses to append against newer schema than it knows about (exit 8).
- Older schemas auto-handled by including all known fields.
- This is the one place the design accepts a deliberate hard fail — silent corruption is unacceptable.

## 9. Testing

| Layer | Tool | LOC budget | Pass bar |
|---|---|---:|---|
| `bin/*.py` unit | pytest | ~400 | 100% line coverage |
| `hooks/*.sh` | bats or sh | ~150 | All branches, all `exit 0` |
| Skill | pytest (regex) | ~50 | Frontmatter + schema match |
| Commands | pytest (regex) | ~30 | Script paths + `$ARGUMENTS` |
| E2E fixture | pytest | ~100 | Final file state matches snapshot |

### Unit-test coverage targets

**`artifact_append.py`:** empty artifact → BUG-1; sequential → BUG-7; gaps (BUG-3, BUG-7, BUG-12) → BUG-13; missing required field → exit 2 file unchanged; corrupt entry → exit 4 file unchanged; flock contention → exit 5; schema mismatch → exit 8; unicode preserved.

**`adr_create.py`:** empty `docs/adr/` → 0001; existing 0001..0007 → 0008; punctuation in title kebab-cased; empty kebab → exit 2; collision retry succeeds.

**`artifact_init.py`:** empty project → all created; re-run → all skipped; `--force` → backup + overwrite; `--no-claude-md` → CLAUDE.md untouched; existing CLAUDE.md without snippet → snippet appended; existing snippet → no duplicate.

**`artifact_review.py`:** mixed-priority entries → grouped output correct; empty files → "no entries"; corrupt entry → flagged not crashed.

### Hook tests
Each script: artifact-present path, artifact-absent path, error-condition path. Assert `exit 0` on all paths.

### Skill test
Static checks: frontmatter present; description contains trigger phrases; schema references match `templates/`; no broken links.

### Slash command tests
Static regex checks: each `commands/artifacts/*.md` references the correct script path under `${CLAUDE_PLUGIN_ROOT}/bin/` and provides `$ARGUMENTS` handling.

### E2E fixture
`tests/fixtures/empty-project/` → tmpdir → run `init` → `bug` → `defer` → `test-skip` → `adr` → `review`. Assert final file states match `tests/fixtures/expected-final/`.

### Explicitly out of test scope
- Hooks firing in real Claude Code sessions (covered by manual smoke).
- LLM behavior under routing rules (ad-hoc evals during development).
- PostToolUse `systemMessage` actually visible to Claude (known harness limitation; design assumes warning surfaces but discipline still works if it doesn't).

## 10. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Artifact rot (entries accumulate, never reviewed) | High | `claude_md_snippet.md` declares review cadences; `/review-artifacts` makes review one command. Research-flagged failure mode #1. |
| Schema drift across plugin versions | Medium | Schema-version marker + hard-fail exit 8 on mismatch. |
| False routing (entries land in wrong artifact) | Medium | `/triage` accepts cross-references; lower-cost than over-strict classification. Wrong artifact > no artifact. |
| User finds hooks too noisy | Medium | All hooks gate on file presence; warn-only. User can disable per-project by removing artifact files (revert to no-op state). |
| PostToolUse `systemMessage` not visible to Claude (known issue) | Known | Design assumes warning surfaces; fallback is user manually correcting course. |
| Quirk users surprised by new hooks running on every session | Low | Hooks no-op when artifacts absent (one stat per event). Documented in 5.1.0 release notes. |

## 11. Implementation order (suggested for the plan phase)

1. `bin/artifact_append.py` + unit tests (the foundation; everything else delegates here).
2. `templates/` (schemas + tic_phrases.json + CLAUDE.md snippet).
3. `bin/artifact_init.py` + tests.
4. `bin/adr_create.py` + tests.
5. `bin/artifact_review.py` + tests.
6. Slash commands (`commands/artifacts/*.md`).
7. Skill (`skills/typed-artifacts/SKILL.md`).
8. Hooks (`hooks/hooks.json` + three `.sh` scripts) + tests.
9. E2E fixture test.
10. Manifest version bump + README update + 5.1.0 release notes.

## 12. Open questions deferred to v2

- Should `/triage` learn user's classification preferences over time (per-project tic-mapping)?
- Should artifact entries link bidirectionally to the commits that resolve them?
- Should `proposals.md` entries auto-promote to `docs/adr/` on status change?
- Is `workflow.json` cross-repo routing worth the config layer once 2+ projects share an artifact home?

---

**Spec version:** 1
**Schema versions:** all artifacts v1
**Brainstorm session:** 2026-05-04
