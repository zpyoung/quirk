# quirk

Core skills library for Claude Code: TDD, debugging, collaboration patterns, typed artifacts, and proven techniques.

Version: **2026.7.9**

## What ships

- **27 skills** under `skills/` covering TDD, systematic debugging, brainstorming (which produces a logic spec), deep-research/brainstorming exploration (with a `--involve` user-inclusion dial: checkpoints, mid-run steering, and idea-gate co-creation), divergent ideation, the two-document spec rubric (logic spec + tech spec) and plan writing, scannable-prose revision, code review, a full multi-lens pre-merge review for GitHub and GitLab, adversarial review (typed profiles, a promote/refute two-stage, and an evidence gate), parallel agent dispatch, guided bug/feature/code-change filing with provenance-marked artifacts, gating simplification behind a correctness check, and more.
- **Typed artifacts** (added in 5.1.0) — surface-routing for observations Claude cannot act on. See below.

## Installation

Install via the quirk-dev marketplace (`.claude-plugin/marketplace.json`).

## Deep code review

`/quirk:full-code-review --deep [minutes]` adds bounded area finders, cross-file
contract checking, and fresh candidate verification to the standard review.
The default budget is 60 minutes. Eligible runs ask before executing repros in
throwaway copies; plausible findings stay visible but cannot be posted.
See the [deep-mode runbook](skills/full-code-review/references/deep.md).

`--since <ref>` reviews only the changes after `<ref>`, such as the fix commits made since
the last review's head SHA. A delta review is report only: it loads no memory and posts nothing.

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

### Logic spec + tech spec

See `docs/specs/2026-05-04-typed-artifacts-design.md` (historical, pre-restructure).
Current specs live under `docs/quirk/specs/YYYY-MM-DD-<topic>/`: `logic.md` always,
`tech.md` when warranted. Brainstorming offers an interactive logic-spec format once;
Markdown remains the default. Interactive specs keep `logic.json` as the source,
generate `logic.md`, and use a local `review.html` for decisions and sign-off.
The page and decision exports are not committed. See
[the interactive rubric](skills/writing-specs/interactive-logic-spec.md).

## HTML artifacts and the visual companion

The `writing-html-artifacts` skill builds offline, single-file HTML pages from templates and
vendored libraries, and runs the brainstorming visual companion: a small local Python server
that shows option screens in a browser and sends clicks back to the agent. Brainstorming and
exploring-ideas both use it. Markdown stays the canonical source for specs; the companion needs
Python 3 only.

## Development

```bash
python3 -m pytest -q
```

The renderer runs on Python 3.9+ with only the standard library; producing an
interactive spec requires no Node install or build. Contributors rebuilding the
prebuilt review page use the pinned `pnpm` dependencies in
`skills/writing-specs/interactive/app/` (`pnpm install --frozen-lockfile &&
pnpm run build && pnpm run check`).
