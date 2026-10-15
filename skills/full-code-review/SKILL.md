---
name: full-code-review
description: Use when asked for a full, multi-lens code review of a GitHub pull request, a GitLab merge request, a branch, or local changes ("full review", "full code review", "review this PR", "review this MR"). Runs up to 14 specialist lenses in parallel (correctness, safety, risk, claim verification, scope, data layer, cross-repo impact, conventions, comments, observability, resilience, and three test lenses), merges them into one deduped, severity-ranked report with an HTML triage page, remembers triage decisions across re-reviews, and posts only human-approved findings (author inline comments, or one batched reviewer review). Advisory only; it never approves or merges on its own.
user-invocable: true
argument-hint: '[--change <number> | --branch <name> | --local] [-R <project>] [--forge github|gitlab|none] [--pack <dir>] [--seat author|reviewer] [--fresh] [--no-escalate] [--add-guidance "<note>"] [--format html|md|both] [--no-open]'
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# Full code review

Run **one** review across up to 14 lenses and deliver a single deduped,
severity-ranked report. The review is advisory: it never approves, requests changes,
merges, or posts without an explicit human choice.

The same machinery serves two detected seats:

- **Author seat**: your own change request, branch, or local changes. Triage is Will
  fix / Fix later / Needs detail / Ignore, and approved findings become inline comments.
- **Reviewer seat**: someone else's change request. Triage is Blocking / Non-blocking /
  Question / Drop, and approved findings become one batched review.

The seat is never configured: it comes from the change author and the authenticated
forge user, and is announced before review work starts.

Re-reviews use a local decision ledger plus a read-only cross-check of the change's
discussions. Lenses always review the full diff independently; only the coordinator
sees prior findings.

## Setup

Resolve bundled files from the plugin root and use a per-run scratch directory outside
the reviewed repository:

```bash
SCRIPTS="${CLAUDE_PLUGIN_ROOT}/skills/full-code-review/scripts"
REFS="${CLAUDE_PLUGIN_ROOT}/skills/full-code-review/references"
REVIEW_RUN_DIR="${REVIEW_OUT_DIR:-$(mktemp -d -t quirk-review.XXXXXX)}"
CONTEXT="$REVIEW_RUN_DIR/review-context.json"
SOURCE_MANIFEST="$REVIEW_RUN_DIR/review-source.json"
MEMORY_SCRIPT="$SCRIPTS/review_memory.py"
```

The ledger lives at `${XDG_STATE_HOME:-$HOME/.local/state}/quirk/review-memory/`. It keeps
finding prose and hashed anchors, never plaintext anchor source, and prunes targets
untouched for 90 days. `--fresh` discards prior decisions, not live evidence that a note
is already posted.

Forge access goes through `gh` (GitHub) or `glab` (GitLab); they own authentication.
A review with no supported forge still runs and delivers locally.

### Flags

| Flag | Meaning |
|---|---|
| `--change <number>` / `--branch <name>` / `--local` | What to review. A branch auto-discovers its open change request. |
| `-R <project>` | Project path when running outside its checkout. |
| `--forge github\|gitlab\|none` | Override forge detection. |
| `--pack <dir>` | Use this org pack instead of the user pack for this run. |
| `--seat author\|reviewer` | Only when both you and another author committed to the change. |
| `--fresh` | Discard remembered triage decisions for this target. |
| `--no-escalate` | Keep every lens on its default model tier. |
| `--format html\|md\|both`, `--no-open` | Render options. |
| `--add-guidance "<note>"` | Capture a review lesson, then stop. |

### Preflight: syntax colouring

The report colours code with Pygments when the `python3` that runs the scripts can
import it, and falls back to a built-in set (Python, Bash, JSON, YAML, SQL, diff)
otherwise. Check once, before Step 1:

```bash
python3 -c "import pygments" 2>/dev/null && echo pygments || echo missing
```

If it prints `missing` and the session is interactive, ask one multiple-choice
question: install now (`python3 -m pip install --user pygments`, then re-check; on a pip
refusal show the error and continue) or continue without it. Never install without that
choice, ask at most once per run, and never let colouring block the review.

## Fast path: `--add-guidance "<note>"`

Capture only and stop. Ask once where the lesson belongs (the repo's `REVIEW.md`, the
project pack, or the user pack), then:

```bash
python3 "$SCRIPTS/add_guidance.py" --note "<note>" \
  --target review-md|project-pack|user-pack --git-root "$(git rev-parse --show-toplevel)"
```

Surface `path` and `commit_hint`. Never commit for the user.

## Step 1: prepare the diff and detect the seat

```bash
python3 "$SCRIPTS/prepare_diff.py" --change <number> [-R <project>] [--forge <name>] --out "$CONTEXT"
python3 "$SCRIPTS/prepare_diff.py" --branch <name> [--forge <name>] --out "$CONTEXT"
python3 "$SCRIPTS/prepare_diff.py" --local --out "$CONTEXT"
```

The script detects the forge from the git remote (github.com and gitlab.com directly; a
self-hosted host by which of `gh`/`glab` is authenticated for it), fetches the canonical
diff and refs, resolves the change author and authenticated user, rejects an incoherent
or moving snapshot, and writes `seat`, `forge`, and the change identity into the
context. **State its result immediately:**

> Detected **<author|reviewer> seat**: <PR #n on GitHub | MR !n on GitLab> is authored by @<author>;
> authenticated as @<user>.

If the script stops with seat `ambiguous`, both you and another author committed to the
change: ask once which seat the user wants and rerun with `--seat author` or
`--seat reviewer` (non-interactive runs stop and name the flag). If
`change.mixed_authorship` is `null`, commit authors could not be read; record that as an
Assumption. If identity is incomplete, the seat is `unknown`, or the script reports a
head race, stop. Never guess: the seat controls what gets posted. Local and non-forge reviews are
author seat. **The script exits non-zero and writes no context file when no diff source
succeeded**; stop and report the printed error. Never fan out on a partial or missing
diff.

Read the printed metadata (`forge`, `source`, `mode`, `refs`, `changed_files`, `size`,
`test_files`, `source_files`, `has_description`, `batched`, and the coverage fields).
**Check the coverage fields before fanning out** (definitions in
`$REFS/orchestration.md`):

- `diff_unavailable` and `not_text_reviewable`: content that **did not reach the
  lenses**. Never let a clean report imply those files were checked.
- `untracked_files` and `file_list_recovery`: content that **is** in the diff; report
  them as provenance notes.

## Step 2: size gate

| | Files changed | Lines changed |
|---|---|---|
| **Warn** | > 30 | > 600 |
| **Hard block** | > 75 | > 2000 |

**Hard block**: stop and output exactly:

> ⛔ **Change too large to review reliably** — N files, N lines changed.
>
> A review at this size produces findings too shallow to be actionable. Please split
> the change before requesting a review. If splitting is impractical, ask a human
> reviewer instead.

**Warn**: put this at the top of the report and continue:

> ⚠️ **Large change** — N files, N lines changed. Review depth may be reduced for areas
> with many small or mechanical changes. Consider splitting it for a more thorough pass.

Note the size and any notice in the Summary either way.

## Step 3: select the source root

**Author seat**: use the current repository root.

**Reviewer seat**: the mutation probe executes the change's code, so offer it only when
`change.is_fork` is `false` and `change.author_trusted` is `true`; otherwise don't ask,
and record why. When it may be offered, ask every run (consent never persists). Then
borrow a detached worktree at the exact change head:

```bash
python3 "$SCRIPTS/borrow_review_source.py" acquire \
  --context "$CONTEXT" --repo . --out "$SOURCE_MANIFEST" [--allow-mutation-probe]
```

It verifies the local clone is the same host and project, fetches the change head,
checks the full SHA, and creates a detached worktree without touching the caller's
branch, index, or working tree. If no matching clone exists, ask before either choice:
`--allow-temp-clone` (a shallow temporary clone), or `--diff-only --reason "<why>"`.

Read `path`, `kind`, `mutation_consent`, and any `mutation_refused` reason from the
manifest; the script refuses consent on its own for forks and untrusted authors. For `worktree` or
`temp-clone`, set `REVIEW_SOURCE_ROOT=path` and run all source reads, guidance
discovery, and lenses there. For `diff-only`, never read the reviewer's own checkout as
a substitute: every finding is `verified: false`, source-dependent lenses are skipped
and named, and the reason goes in `run.source_access_reason`.

**Always release the manifest in a finally path**, including cancellation and failure:

```bash
python3 "$SCRIPTS/borrow_review_source.py" release --manifest "$SOURCE_MANIFEST"
```

## Step 4: policy, guidance, scope intent, and memory

**Policy.** Resolve the layers in `$REFS/policy.md` and drop generated files before
anything else reads the diff:

```bash
python3 "$SCRIPTS/resolve_policy.py" --context "$CONTEXT" --source-root "$REVIEW_SOURCE_ROOT" \
  --lenses-dir "$REFS/lenses" --out "$REVIEW_RUN_DIR/policy.json" --apply \
  [--pack <dir>] [--policy-ref <target branch SHA, reviewer seat only>]
```

Exit 2 means a malformed pack or `REVIEW.md`; show the named file and line and stop.
`policy.json` fixes the lenses that run (`lenses`, each with its checklist path and
model), `skipped`, `severity_floor`, `escalation`, `critical_paths`, `cross_family`,
`cross_repo`, and `guidance_files`. Re-check the Step 2 size gate against the filtered
`size`, and list `excluded_generated` in the Summary.

**Repo conventions.** Against `REVIEW_SOURCE_ROOT`:

```bash
python3 -c "import json,sys;print('\n'.join(json.load(open(sys.argv[1]))['changed_files']))" \
  "$CONTEXT" > "$REVIEW_RUN_DIR/changed.txt"
python3 "$SCRIPTS/discover_guidance.py" --git-root "$REVIEW_SOURCE_ROOT" \
  --changed-files "$REVIEW_RUN_DIR/changed.txt"
```

This returns the repo's own conventions (`.claude/skills`, the `CLAUDE.md` hierarchy,
`.claude/rules`, `AGENTS.md`/`CONVENTIONS.md`). The `conventions` lens consumes these
together with `policy.guidance_files` (pack guidance and `REVIEW.md` prose).
A repo may keep review knowledge in `references/` beside each `SKILL.md`: read every
path in `repo_skill_reference_indexes` first and only the references they map to the
changed files; with no index, select by path relevance and never read all of them. If
`repo_skill_references_dropped` is above 0, say coverage was capped. In diff-only mode,
state that repo-local guidance could not be read.

**Scope intent.** Judge whether `change.description` states an intent the hunks can be
held against (an unfilled template says nothing; a one-line goal may be enough):

- Description states intent: summarize it as `scope_intent.statement` with
  `source: "description"`; do not prompt.
- Absent or too thin: ask **once**, pre-filled with `scope_intent.guess`, to confirm or
  edit. In reviewer seat, ask the reviewer to confirm your reading, never to author the
  intent. Store it with `source: "user"`.
- Declined or non-interactive: keep the guess with `source: "guess"` and an Assumption.
  Never halt or skip `scope` for this.

Write `statement` and `source` back into `$CONTEXT`, preserving every other field,
**before** the risk lens or fan-out. For local and branch-only runs the inferred intent
is an Assumption, not a missing-description finding.

**Coordinator-only memory.** Load a snapshot before any lens runs:

```bash
python3 "$MEMORY_SCRIPT" load --context "$CONTEXT" --repo "$REVIEW_SOURCE_ROOT" \
  --dimension correctness --dimension safety --dimension risk --dimension adversarial \
  --dimension scope --dimension db --dimension cross-repo --dimension conventions \
  --dimension comments --dimension observability --dimension resilience \
  --dimension test-adequacy --dimension tests --dimension test-coverage \
  --guidance <file> --out "$REVIEW_RUN_DIR/memory-snapshot.json" [--fresh]
```

Repeat `--guidance` for every file whose contents supplied review guidance; pass the
complete roster, not just today's applicable lenses. In diff-only mode use the caller
repo for `--repo`. Surface warnings and invalidation reasons. A failed discussion fetch
does not cancel the review or lose remembered decisions, but **blocks every forge write**
until a fresh cross-check succeeds. Never pass the snapshot, ledger, discussion bodies,
or previous reports to a lens; the coordinator may extract only `unchanged_files` and
the prior head SHA for the neutral annotation in `orchestration.md`.

## Step 5: fan out the lenses

`policy.json` lists the lenses to run, each with its checklist path, run condition, and
model; `$REFS/orchestration.md` holds the finding schema, escalation, model fallback, and
the verification gate. **Run `risk` first, alone**: give it `policy.critical_paths`, and
its rating sets verification depth for everyone else. Then dispatch every applicable
lens **in parallel** with the `Agent` tool, giving each the context file path, its
checklist, the finding schema, the risk level, and the source root, and setting `model`
from the policy (escalated per `orchestration.md` when `policy.escalation` is true and
`--no-escalate` was not passed). Record the model each lens actually ran on.

If `batched`, `risk`, `adversarial`, and `scope` each run once over the whole diff; every
other lens runs per batch. Every lens applies the **verification gate**: no Must or
Should fix from the diff alone; read source at the correct ref in the selected source
root, never the reviewer's own checkout. Diff-only is the explicit exception, and its
findings stay unverified.

The three test lenses may **prove** their findings with the mutation probe
(`$REFS/lenses/_mutation-probe.md`): only with consent, only inside the source root,
production-only, bounded, self-reverting, never committed. In reviewer seat it runs only
when the current manifest says `mutation_consent: true`; refusal is not an error.

## Step 6: coordinate

**Incomplete runs.** A lens that still fails after the model-fallback retry goes in
`run.dimensions_failed`, and the report is incomplete: it is never presented as clean.

Per `orchestration.md`: dedup by `file:line` (keep the highest severity, merge lens
tags), drop speculative and linter-style nits, calibrate severity (description-only
fixes are always `Nit`; verified correctness findings are `Should fix` or higher unless
unreachable or cosmetic), rank, aggregate assumptions, and reduce across batches. Keep
memory out of dedup, verification, and severity. Use the lexically first lens as the
singular `dimension` after merging tags, consistently across runs.

## Step 7: author `report.json`

Set `REVIEW_OUT_DIR` to the session's scratch directory. Author the structured findings
and narrative blocks defined in `$REFS/html-report.md` (Summary, Risk Assessment, Claim
Verification, Findings, Assumptions, Recommendations) and write
`$REVIEW_RUN_DIR/review-<slug>-report.json`, never into the reviewed repo. Always write
`schema_version: 1`. Give every finding a one-sentence `impact` (at most 200 characters)
and a one-line `fix_md` (at most 160); an over-cap or multi-line value fails render, so
rewrite it, never truncate. Write code-change recommendations as ` ```diff ` fences.

`run` also carries `incomplete`, `dimensions_failed`, `models`, `verification`,
`excluded_generated`, `policy_sources` (from `policy.sources`), and `severity_floor`
(from `policy.severity_floor`); findings below the floor render but never post.

`meta` carries `target` (`change`, `branch`, or `local`), and for a change request
`forge`, `number`, and `project`; reviewer reports also carry `seat: "reviewer"` and the
full lowercase `head_sha`, and `run` carries `source_access`, `source_access_reason`,
and `mutation_consent`. Set `meta.source_branch`, `meta.web_url` (change requests only),
and, in author seat, `meta.repo_root` so the triage handoff can find the code later.
Leave out any value you don't have. `run.dimensions_run` lists lenses that completed;
`run.dimensions_skipped` lists every missing or failed pass.

Reconcile into a separate final report; never hand-author memory fields:

```bash
python3 "$MEMORY_SCRIPT" reconcile \
  --report "$REVIEW_RUN_DIR/review-<slug>-report.json" --context "$CONTEXT" \
  --snapshot "$REVIEW_RUN_DIR/memory-snapshot.json" \
  --out "$REVIEW_RUN_DIR/review-<slug>-memory.json"
REPORT_JSON="$REVIEW_RUN_DIR/review-<slug>-memory.json"
```

Exact unique fingerprints carry decisions; fuzzy candidates, ambiguous anchors, and
resolved matches need explicit triage; a missing anchor fails toward new. "Appears
fixed" is an observation, never permission to resolve a discussion.

## Step 8: render

```bash
python3 "$SCRIPTS/render_report.py" --in "$REPORT_JSON" --format <html|md|both> [--no-open]
```

Keep the renderer's `order`, `seat`, `head_sha`, paths, and warnings. Print only a short
terminal digest: tally and verdict, lenses run and skipped, one line per Must/Should,
and the artifact paths.

## Step 9: triage

```bash
python3 "$SCRIPTS/validate_triage.py" --report "$REPORT_JSON" \
  --paste "$REVIEW_RUN_DIR/triage.md" --out "$REVIEW_RUN_DIR/decisions.json"
```

The validator rejects target or mode mismatches, reordered groups, wrong counts,
duplicate or missing IDs, and anchor or severity forgery before returning any decision.
The paste ends with a handoff section the validator never reads and nothing posts from.
Reviewer seat with findings requires a valid paste (**no severity fallback**). A
zero-findings page has no triage controls; after explicit confirmation to post the clean
overview, create its bound empty artifact with `--zero-findings` instead of `--paste`.

After every valid paste, persist decisions even if the user declines delivery:

```bash
python3 "$MEMORY_SCRIPT" save --report "$REPORT_JSON" --decisions "$REVIEW_RUN_DIR/decisions.json"
```

Keep the report unchanged after validation; the decisions artifact is bound to it.

## Step 10: deliver

Follow `$REFS/posting.md`. With no supported forge, delivery is the rendered report and
`report.json` path; nothing posts. Headless runs stop after the report.

**Author seat**: valid dispositions drive the batch; with no paste, every finding at or
above `policy.severity_floor` is preselected. Findings below the floor never post. Run the live duplicate `check`, build every body with
`comment_body.py author`, preview, and post only after approval. Save a receipt for
each confirmed create. Never edit, reply to, or resolve an old note.

**Reviewer seat**: stage from the trusted report and normalized decisions:

```bash
python3 "$SCRIPTS/post_reviewer_review.py" stage --report "$REPORT_JSON" \
  --decisions "$REVIEW_RUN_DIR/decisions.json" --context "$CONTEXT" \
  --out "$REVIEW_RUN_DIR/staged-review.json" [--allow-unaffected]
```

Staging revalidates identity and refs, refuses to stage over any existing draft, and
records every created ID. A partial failure never publishes and prints exact
**user-run** cleanup commands; the agent never runs them. If the head moved, show the
affected and unaffected findings and offer a re-run, or `--allow-unaffected` only after
explicit approval. Show the full preview, omitted items, warnings, and IDs, ask for
final approval, and only then:

```bash
python3 "$SCRIPTS/post_reviewer_review.py" publish --staged "$REVIEW_RUN_DIR/staged-review.json" --confirm
```

Publish revalidates again and requires the live draft set to equal the staged set
exactly; any drift aborts. Finally **offer**, never infer:

```bash
python3 "$SCRIPTS/post_reviewer_review.py" complete --staged "$REVIEW_RUN_DIR/staged-review.json" \
  --action approve|request-changes|comment-only
```

Any Blocking finding suggests request-changes; otherwise approval may be suggested. A
completion failure never undoes or misreports the published review.

## Degradation

`$REFS/degradation.md` lists every degraded path and what the report must say about
it. The short version: a degraded review still runs, and the report never claims
coverage it did not have.

## Boundaries

- No **lasting** change to reviewed code beyond approved comments. The sole code-edit
  exception is the consented mutation probe, which is transient, production-only,
  self-reverting, and never committed.
- Never auto-posts, approves, requests changes, or merges. Delivery is always offered.
- Never installs a package without the user's explicit choice.
- Never executes cleanup DELETEs; prints them for the user.
- Never resolves threads. The only reply it posts is a support reply the reviewer
  approved at triage; responding to review comments is `quirk:receiving-code-review`.
- Reads checklists only from this skill and from policy packs; a review is reproducible
  from its inputs.
