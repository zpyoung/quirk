---
description: Adversarially review a diff, spec, plan, or written claim. Runs a deterministic pre-pass, a promote/refute two-stage with a cross-family reviewer, and an evidence gate, then reports a verdict with findings.
---

Adversarially review a target. `$ARGUMENTS` is an optional path, git range (`a..b`), or `WORKTREE`;
when empty, review the uncommitted changes plus the branch diff against main.

Invoke the `quirk:adversarial-review` skill and follow its data flow. The skill owns the protocol;
this command is the entry point.

Optional flags in `$ARGUMENTS`, passed through: `--profile`, `--lens`, `--depth`, `--model`.

Resolve the script once:

```bash
SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/scripts/adversarial-review"
WORK="$(mktemp -d)"
```

Run the pipeline in order — `resolve`, `prepass`, `select-model`, the promote and refute dispatches,
`gate`, then `manifest` — as the skill specifies. Do not stop early on a non-zero exit from
`prepass` (exit 1 means a check failed, which is a finding) or from `select-model` (exit 1 means no
ladder rung resolved, which the gate turns into `NOT_REVIEWABLE`).

Handle the `gate` result by exit code:

1. On exit 0 (`PASS`): report the verdict, the reviewer alias with its `independence` flag, and the
   suppressed count. Only `LOW` findings survived, or none. If `suppressed_count` is high relative
   to the number of findings raised, say so — a `PASS` reached by killing everything is not a `PASS`
   reached by finding nothing.
2. On exit 1 (`NEEDS_FIXES`): render the summary and every surviving finding. Do not fix anything —
   this skill reports; the user decides.
3. On exit 3 (`CRITICAL_ISSUES`): lead with the CRITICAL findings. Say plainly that the artifact
   should not ship as-is.
4. On exit 4 (`NOT_REVIEWABLE`): state that the review **did not happen** and why — no reviewer
   resolved at any ladder rung, or the pre-pass could not run and the core claims are unfalsifiable.
   Never report this as a pass. Offer the remediation that matches the cause: authenticate `pi`, or
   pass `--model` explicitly, or narrow the target to something checkable.
5. On exit 2, non-JSON stdout, or no stdout at all: the run failed. Relay stderr verbatim, retry
   once, then walk the model ladder, then stop and report the block.

Render at most 10 lines of summary above the findings, every line derived from the gate's JSON
rather than authored independently. Then emit the findings array and the manifest.

At `deep` depth, check `contested[]` before reporting. A non-empty array means findings are being
withheld pending the tiebreak stage — route them, merge the rulings, and re-run `gate`.

User input: $ARGUMENTS
