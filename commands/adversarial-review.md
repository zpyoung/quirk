---
description: Adversarially review a diff, spec, plan, or written claim. Runs a deterministic pre-pass, a promote/refute two-stage with a cross-family reviewer, and an evidence gate, then reports a verdict with findings.
---

Invoke the `quirk:adversarial-review` skill and follow its data flow to review the following:

$ARGUMENTS

Notes:
- `$ARGUMENTS` is an optional target — a path, a git range (`a..b`), or `WORKTREE`. Empty means `WORKTREE`: the uncommitted changes, as the skill defines them. To review a branch, pass the range.
- Flags in `$ARGUMENTS` pass straight through to the skill: `--profile`, `--lens`, `--depth`, `--model`. Anything not recognized as a flag is the target.
- The skill owns the protocol, the verdict contract, and how findings are reported. This command only routes to it — do not restate its rules here.
