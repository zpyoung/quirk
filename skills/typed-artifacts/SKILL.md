---
name: typed-artifacts
description: Use when about to write hedging language like "pre-existing", "out of scope", "future work", "skipped for brevity", or "architectural concern" — instead, route the observation to a typed artifact (BUGS.md, DEFERRED.md, TEST_BACKLOG.md, proposals.md) or an ADR. Also use when the user invokes /quirk:artifacts:* commands or asks how to log a bug, defer a task, or record a decision.
---

# Typed Artifacts: Surface Routing

When you notice something you cannot act on in this session, do NOT bury it in prose. Route it to a typed artifact via one of the slash commands.

## The routing table

| If you're about to write… | Use this command | Lands in |
|---|---|---|
| "pre-existing", "already existed", "introduced before" | `/quirk:artifacts:bug` | `BUGS.md` |
| "out of scope", "future work", "larger refactor needed" | `/quirk:artifacts:defer` | `DEFERRED.md` |
| "skipped for brevity", "tests can be added later" | `/quirk:artifacts:test-skip` | `TEST_BACKLOG.md` |
| "worth reconsidering", "architectural concern", "worth revisiting" | `/quirk:artifacts:triage` (proposal) | `proposals.md` |
| "we made an architectural decision" | `/quirk:artifacts:adr` | `docs/adr/NNNN-*.md` |
| Don't know which fits | `/quirk:artifacts:triage` | one of the above |

After appending, **continue the current task**. Do NOT stop to discuss the routing entry unless severity is `critical`. The artifact is the discussion.

## Schemas (summary)

Full schemas live in the `templates/` directory of the quirk plugin. Required fields per artifact:

- **BUGS.md** (BUG-N): title, file (path:line), description, severity (critical/high/medium/low)
- **DEFERRED.md** (DEFER-N): title, why_deferred, priority (P1/P2/P3/P4)
- **TEST_BACKLOG.md** (TEST-N): title, file_under_test, reason_skipped
- **proposals.md** (PROPOSAL-N): title, context, recommendation
- **docs/adr/NNNN-*.md** (Nygard): title, status (proposed → accepted → superseded)

The mutation scripts re-validate required fields. Missing fields surface as a clarifying question — never invent values.

## When NOT to route

- The observation is the work you're doing right now → fix it, don't log it.
- The observation is a bug **you just introduced this session** → fix it, don't log it. The "Introduced by" field on BUGS.md is for things that pre-date your session.
- The observation is information about the user's intent → ask, don't log.

## First-time setup

If the user hasn't run `/quirk:artifacts:init` in this project yet, suggest it. Without artifact files in the project root, the append commands will exit 3.

## Review cadences

(Declared in the user's CLAUDE.md when `/init` runs.)

- BUGS.md — every PR
- DEFERRED.md — every sprint planning
- TEST_BACKLOG.md — every 2 weeks
- proposals.md / docs/adr/ — monthly with architect

Use `/quirk:artifacts:review-artifacts` to scan all four files in one read-only pass.
