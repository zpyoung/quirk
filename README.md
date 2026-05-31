# quirk

Core skills library for Claude Code: TDD, debugging, collaboration patterns, typed artifacts, and proven techniques.

Version: **5.7.0**

## What ships

- **16 skills** under `skills/` covering TDD, systematic debugging, brainstorming, plan writing, code review, parallel agent dispatch, [parallel divergent ideation (ADHD)](./skills/adhd/SKILL.md), and more.
- **Typed artifacts** (added in 5.1.0) — surface-routing for observations Claude cannot act on. See below.

## Installation

Install via the quirk-dev marketplace (`.claude-plugin/marketplace.json`).

## Typed artifacts

A discipline for routing deferred observations into structured markdown files instead of burying them in prose ("pre-existing", "out of scope", "skipped for brevity").

### Quick start

In your project, run:

```
/quirk:artifacts:init
```

That scaffolds `BUGS.md`, `DEFERRED.md`, `TEST_BACKLOG.md`, `proposals.md`, and `docs/adr/`. It also appends a 5-line trigger snippet to your project's `CLAUDE.md` (use `--no-claude-md` to skip that).

### Slash commands

| Command | Purpose |
|---|---|
| `/quirk:artifacts:init` | Scaffold artifact files into the current project |
| `/quirk:artifacts:bug` | Append a BUG-N entry to BUGS.md |
| `/quirk:artifacts:defer` | Append a DEFER-N entry to DEFERRED.md |
| `/quirk:artifacts:test-skip` | Append a TEST-N entry to TEST_BACKLOG.md |
| `/quirk:artifacts:triage` | Classify an observation and append to the right file |
| `/quirk:artifacts:adr` | Create a new Architecture Decision Record |
| `/quirk:artifacts:review-artifacts` | Read-only summary of all entries |

### Hooks

Three lifecycle hooks (warn-only, never block):

- **SessionStart** loads tail of artifact files (or suggests `/init` if none exist).
- **PostToolUse** lints written files for tic phrases ("pre-existing", etc.).
- **Stop** posts a wrap-up reminder.

All three gate on artifact-file presence — they are inert no-ops in projects that haven't run `/quirk:artifacts:init`.

### Design + spec

See `docs/specs/2026-05-04-typed-artifacts-design.md`.

## Development

```bash
python3 -m pytest -q
```

Stdlib-only Python 3.9+. No third-party dependencies.
