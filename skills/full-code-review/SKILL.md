---
name: review-mr-combined
description: "[Beta] Run a comprehensive code review on a GitLab MR, a branch, or local changes. Bundles the Recharge review standard (correctness, production safety/security, test adequacy, risk assessment, adversarial claim verification) together with sakura's added dimensions (scope and separable concerns, DB queries and hot-path performance, cross-repo impact, conventions/reuse, code-comment quality, observability, production resilience, test quality, missing-test coverage) and fans them out as parallel specialist passes, producing one deduped, severity-ranked report with an Assumptions section. Self-contained — no external review skills are read at runtime. Detects the author or reviewer seat: author mode drives local-fix decisions and gated inline posting, reviewer mode reviews an isolated MR-head worktree and publishes approved findings as one atomic draft-note review. Invoke on 'combined review', 'full review', 'review this MR'."
user-invocable: true
argument-hint: '[<mr-iid> | <branch> | --local] [-R <project>] [--fresh] [--add-guidance "<note>"] [--format html|md|both] [--no-open] [--no-opus]'
allowed-tools: Bash, Read, Grep, Glob, Task
---

# Review MR — Combined

Run **one** code review across 14 dimensions and deliver a single deduped,
severity-ranked report.

Every checklist is **bundled** in `references/dimensions/` — the review reads nothing
off disk outside this skill, so it is reproducible and has no install-order
dependency. The Recharge org standard (correctness, safety/security, test adequacy,
risk, adversarial claim verification) is carried here alongside sakura's own
dimensions; `references/provenance.md` records the upstream baseline each bundled
checklist tracks and how to check it for drift.

The same review machine supports two detected seats:

- **Author seat** — your own MR/branch/local changes; triage is Will fix / Fix later /
  Ignore / Needs detail and the existing author delivery flow is unchanged.
- **Reviewer seat** — another user's MR; triage is Blocking / Non-blocking / Question /
  Drop and approved findings become one batched GitLab review.

The seat is never configured manually. It comes from the MR author and authenticated
GitLab user, and must be announced before review work starts.

Re-reviews use a local decision ledger plus a read-only MR discussion cross-check.
Specialists still review the full diff independently; only the coordinator sees prior
findings. Exact matches restore triage decisions and markers in the authenticated
identity's own notes prevent duplicate inline notes. Resolved threads and possible
regressions remain visible for a new decision.

> **Status: Beta.** The mechanics are unit- and smoke-tested. Keep final posting and
> completion explicitly human-gated.

## Two path homes (important)

- **`scripts/…` and `references/…`** (orchestration, dimensions, report template,
  posting, provenance) are read from **this skill's own directory** (the active skill
  location — the same place as this SKILL.md).
- **Sakura-tracked repo guidance is read/written in your sakura SOURCE CLONE**, not
  the skill's installed copy. The installed copy lives in the plugin cache, which
  `update-sakura` and the `post-merge` hook **wipe** — anything written there is lost
  and never git-tracked.

Resolve bundled `scripts/…` and `references/…` relative to this SKILL.md. Repository
guidance is read from the sakura **source clone**, not the installed plugin cache:

```bash
SAKURA_HOME="${SAKURA_HOME:-$HOME/.claude/sakura}"
GUIDANCE_DIR="$SAKURA_HOME/plugins/sakura/skills/review-mr-combined/references/repo-guidance"
```

Use a per-run scratch directory outside the reviewed repository:

```bash
REVIEW_RUN_DIR="${REVIEW_OUT_DIR:-$(mktemp -d -t sakura-review.XXXXXX)}"
CONTEXT="$REVIEW_RUN_DIR/review-context.json"
SOURCE_MANIFEST="$REVIEW_RUN_DIR/review-source.json"
```

Memory uses `../../shared/mr/review_memory.py` relative to this skill's directory.
Its ledger lives at `${XDG_STATE_HOME:-$HOME/.local/state}/sakura/review-memory/`,
outside both the reviewed repository and the replaceable plugin cache. It retains
finding prose and hashed anchors, not plaintext anchor source, and prunes targets
untouched for 90 days on write. Worktrees share normalized-origin/target identity;
local and branch targets remain distinct. `--fresh` discards prior decisions, not
live evidence that a note is already posted.

`glab auth status` must succeed for MR review and delivery.

### Preflight — syntax colouring

The report colours code with Pygments when the `python3` that runs the scripts can
import it, and falls back to a small built-in set (Python, Bash, JSON, YAML, SQL,
diff) otherwise — TypeScript, Vue, Go, and the rest then render uncoloured. Check
once, before Step 1, so the question never lands mid-review:

```bash
python3 -c "import pygments" 2>/dev/null && echo pygments || echo missing
```

If it prints `missing` and the session is interactive, ask the user one
multiple-choice question before continuing:

- **Install Pygments now** — run `python3 -m pip install --user pygments` with the
  same `python3`, then re-run the check. If pip refuses (for example an
  `externally-managed-environment` error), show the error, suggest the user install it
  their usual way, and continue with built-in colouring.
- **Continue without it** — built-in colouring for this run.

Never install without that explicit choice. Ask at most once per run; a
non-interactive run continues without it. Either way the review proceeds — colouring
never blocks it. The renderer's stdout reports `highlighter` (`pygments` or `builtin`)
and adds a warning when it fell back.

## Fast path — `--add-guidance "<note>"`

Capture only and stop. The note must land in the tracked sakura source clone:

```bash
[ -d "$SAKURA_HOME/.git" ] || { echo "Set SAKURA_HOME to the sakura source clone." >&2; exit 1; }
REPO_ROOT=$(git rev-parse --show-toplevel)
python3 scripts/add_guidance.py --note "<note>" \
  --sakura-guidance-dir "$GUIDANCE_DIR" --git-root "$REPO_ROOT"
```

Surface `commit_hint`; the guidance is durable only after it is committed and pushed.

## Step 1 — Prepare the diff and detect the seat

```bash
# MR by IID (use -R outside its checkout):
python3 scripts/prepare_diff.py --mr <iid> -R <group/project> --out "$CONTEXT"
# Branch, with GitLab-first MR auto-discovery:
python3 scripts/prepare_diff.py --branch <name> --out "$CONTEXT"
# Local changes:
python3 scripts/prepare_diff.py --local --out "$CONTEXT"
```

The script fetches the canonical MR diff and `diff_refs`, resolves the MR author and
authenticated user, rejects an incoherent/moving MR snapshot, and writes `seat` plus
the MR identity into the context. **State its result immediately:**

> Detected **<author|reviewer> seat** — MR !<iid> is authored by @<author>; authenticated as @<user>.

If identity is incomplete, the seat is `unknown`, or the script reports a head race,
stop. Never guess: seat controls later MR writes. Local/non-MR review is author seat.
Surface `fallback_reason`, batching, refs, and changed files.

GitLab is preferred whenever an MR exists (canonical diff against the live target
branch + authoritative `diff_refs`); git is the fallback. **The script exits non-zero
and writes no context file when no diff source succeeded** — if that happens, stop and
report the printed error. Never fan out on a partial or missing diff.

On success, read the printed metadata: `source`, `mode`, `refs`, `host`, `project`,
`changed_files`, `size`, `test_files`, `source_files`, `has_description`, `batched`, and
the four coverage fields below. The full diff, refs, and MR title/description are in the
context file.

**Check the coverage fields before fanning out** — all four are empty/null normally, and
`references/orchestration.md` defines each. Any non-empty value belongs in the Summary and
under Assumptions, but they do not all mean the same thing:

- `diff_unavailable` and `not_text_reviewable` — content that **did not reach the
  specialists**. Never let a clean report imply those files were checked.
  `diff_unavailable` recovery needs the MR's `diff_refs` SHAs locally, so `git fetch` the
  MR ref and re-run if it is unexpectedly non-empty.
- `untracked_files` and `file_list_recovery` — content that **is** in the diff and was
  reviewed. Report them as provenance notes: the first because those files aren't
  committed yet, the second because GitLab's own file list was incomplete and had to be
  rebuilt from git.

## Step 2 — Size check (gate)

Read `size.files` and `size.lines` from the context file, then apply:

| | Files changed | Lines changed |
|---|---|---|
| **Warn** | > 30 | > 600 |
| **Hard block** | > 75 | > 2000 |

**Hard block** — stop. Do not fan out. Output exactly:

> ⛔ **MR too large to review reliably** — N files, N lines changed.
>
> A review at this size produces findings too shallow to be actionable. Please split
> the MR before requesting a review. If splitting is impractical, tag a human
> reviewer instead.

**Warn** — emit this at the top of the report, then continue:

> ⚠️ **Large MR** — N files, N lines changed. Review depth may be reduced for areas
> with many small or mechanical changes. Consider splitting this MR for a more
> thorough pass.

Note the size and any notice in the report Summary either way.

## Step 3 — Select the source root

### Author seat

Use the current repository root as today. Do not call the reviewer source borrower.

### Reviewer seat

Ask every run whether the mutation probe may execute the other author's targeted test
commands. Consent does not persist. Then acquire a detached worktree at the exact MR
head:

```bash
python3 scripts/borrow_review_source.py acquire \
  --context "$CONTEXT" --repo . --out "$SOURCE_MANIFEST" \
  [--allow-mutation-probe]
```

The script verifies that a local clone is the same project, fetches the target
project's `refs/merge-requests/<iid>/head`, checks the full SHA, and creates a detached
worktree. It never switches/resets the caller's branch, index, or working tree.

A local clone matches only when both GitLab host and full project path match; an
identically named project on another GitLab instance is rejected. If no matching clone
exists, ask before either choice:

```bash
# User accepts a shallow temporary clone:
python3 scripts/borrow_review_source.py acquire --context "$CONTEXT" --repo . \
  --out "$SOURCE_MANIFEST" --allow-temp-clone [--allow-mutation-probe]

# User declines; review the diff only:
python3 scripts/borrow_review_source.py acquire --context "$CONTEXT" --repo . \
  --out "$SOURCE_MANIFEST" --diff-only --reason "<why source is unavailable>"
```

Read `path`, `kind`, and `mutation_consent` from the manifest. For `worktree` or
`temp-clone`, set `REVIEW_SOURCE_ROOT=path` and run all source reads, guidance discovery,
and specialists there. For `diff-only`, never read the reviewer's current checkout as
a substitute: mark every finding `verified: false`, skip/name source-dependent
dimensions, and record the reason in `run.source_access_reason`.

**Always release the manifest in a finally path**, including no paste, cancellation,
staging failure, and completion failure:

```bash
python3 scripts/borrow_review_source.py release --manifest "$SOURCE_MANIFEST"
```

## Step 4 — Discover review guidance

Run this **after** diff and source selection, against `REVIEW_SOURCE_ROOT`, so the
changed-file list can find nested `CLAUDE.md` in touched directories:

```bash
python3 -c "import json,sys;print('\n'.join(json.load(open(sys.argv[1]))['changed_files']))" \
  "$CONTEXT" > "$REVIEW_RUN_DIR/changed.txt"
[ -d "$GUIDANCE_DIR" ] || GUIDANCE_DIR="references/repo-guidance"
python3 scripts/discover_guidance.py --git-root "$REVIEW_SOURCE_ROOT" \
  --sakura-guidance-dir "$GUIDANCE_DIR" --changed-files "$REVIEW_RUN_DIR/changed.txt"
```

This returns the target repo's own conventions (`.claude/skills`, CLAUDE.md
hierarchy, `.claude/rules`, AGENTS.md/CONVENTIONS.md) plus sakura-tracked guidance
(`_global.md` + `<repo-key>.md`). The `sakura:conventions` specialist consumes this
bundle. If the source clone isn't found, only the bundled `_global.md` is read and
per-repo guidance is unavailable — note it. In diff-only mode, load only bundled/sakura
global guidance and state that repo-local guidance could not be read.

**Routing repo skill references.** A repo may keep the bulk of its review knowledge
in `references/` beside each `SKILL.md`, leaving the `SKILL.md` itself as only a
router — so reading `repo_skills` alone can miss the actual rules. Use
`repo_skill_references` (paths only, cheap to scan) as follows:

- Read every path in `repo_skill_reference_indexes` first. An index maps path globs
  to reference files; match it against `changed_files` and read **only** the matched
  references. This is the intended path and keeps specialist context bounded.
- With no index, select from `repo_skill_references` by path relevance to
  `changed_files`. Never read all of them by default.
- If `repo_skill_references_dropped` is greater than 0, the listing hit its cap —
  say so in the Summary rather than presenting coverage as complete.

Pass the references you selected to `sakura:conventions`, and pass any that match a
specialist's own domain to that specialist too.

### Resolve scope intent (before any specialist runs)

Read `mr.description` and the mechanical `scope_intent.guess` / `.basis` from the
context file. Judge whether the description states an intent that hunks can be held
against — **not** by length or `has_description`: an unfilled template says nothing;
a one-line goal may be sufficient.

- **Description states intent:** summarize it as `scope_intent.statement`, with
  `scope_intent.source: "description"`. Do not prompt. Preserve the full description
  so the scope specialist can honor explicit justifications for accompanying changes.
- **Description absent or too thin:** ask the user **once**, pre-filled with the guess,
  to confirm or edit the scope statement. In reviewer seat ask, “Here is my reading
  of the intent from the title and branch — confirm or edit.” Do not ask the reviewer
  to author the MR's intent. Store the supplied/confirmed statement with source `"user"`.
- **Prompt declined or run non-interactive:** keep the guess as the statement, set
  source `"guess"`, and record an Assumption naming the guess and its basis. Never
  halt review or skip scope merely because intent could not be confirmed. If the
  available intent remains thin, only high-confidence separable concerns qualify.

Write `scope_intent.statement` and `.source` back into `$CONTEXT`, preserving
`.guess`, `.basis`, and all other context fields, **before** the risk pass or fan-out.
The preparation script never judges description adequacy or prompts.

For `--local` or a branch with no MR, use the branch-only guess and the same prompt
(or non-interactive fallback). Record the inferred/confirmed intent as an Assumption,
not a missing-description finding: no MR description exists to fix. For a resolved MR
(including branch auto-discovery, later reported as `meta.target: "mr"`), a user-supplied
statement does not repair the description; `sakura:scope` still owns that finding.

### Load coordinator-only memory

After selecting guidance, load a snapshot **before** specialist execution:

```bash
MEMORY_SCRIPT="../../shared/mr/review_memory.py"
MEMORY_SNAPSHOT="$REVIEW_RUN_DIR/memory-snapshot.json"
python3 "$MEMORY_SCRIPT" load --context "$CONTEXT" --repo "$REVIEW_SOURCE_ROOT" \
  --dimension sakura:correctness --dimension sakura:safety --dimension sakura:risk \
  --dimension sakura:adversarial --dimension sakura:scope \
  --dimension sakura:db --dimension sakura:cross-repo \
  --dimension sakura:conventions --dimension sakura:comments \
  --dimension sakura:observability --dimension sakura:resilience \
  --dimension sakura:test-adequacy --dimension sakura:tests \
  --dimension sakura:test-coverage \
  --guidance <loaded-guidance-file> --out "$MEMORY_SNAPSHOT" [--fresh]
```

Repeat `--guidance` for **every file whose contents supplied review guidance**, including
selected repo skill references; omit it when none was available. Supply the complete
stable roster above, not just dimensions applicable today. In diff-only mode use the
caller repo for `--repo`; MR identity comes from the context, not that checkout.
Forward the skill's `--fresh` flag only to this command.

The loader invalidates decisions when the merge base, dimension roster, or guidance
contents change. `refs.start` and head movement alone do not invalidate MR memory.
Surface warnings and invalidation reasons. A failed discussion fetch does not cancel
independent review or lose remembered decisions, but **blocks MR delivery** until a
fresh cross-check succeeds.

Never pass this snapshot, the ledger, discussion bodies, or previous reports to a
specialist. The coordinator may extract only `unchanged_files` plus the prior head SHA
for the neutral annotation described in `references/orchestration.md`.

## Step 5 — Fan out specialists (parallel)

Follow `references/orchestration.md`, which holds the authoritative roster and run
conditions. **Run `sakura:risk` first, on its own** — its rating sets the verification
depth for everyone else — then spawn the remaining applicable specialists **in parallel**
via the `Task` tool. Each gets the context file path (`$CONTEXT`), its
bundled checklist path, the finding schema, and that risk level. Pass `model` on each
`Task` per the roster's Model column, applying its escalation rule (`--no-opus` or
`SAKURA_REVIEW_NO_OPUS` keeps everything on `sonnet`):

- `sakura:correctness` → `references/dimensions/correctness.md` (always)
- `sakura:safety` → `references/dimensions/safety.md` (always) — production failure
  modes, security, and data integrity
- `sakura:risk` → `references/dimensions/risk-assessment.md` (always); returns a risk
  block rather than findings — it feeds the Risk section and calibrates verification
  depth for every other specialist
- `sakura:adversarial` → `references/dimensions/adversarial.md`, **only if**
  `has_description` is true — verifies every falsifiable claim in the MR description
  (in the context file's `mr` object) against the code
- `sakura:scope` → `references/dimensions/scope.md` — always, except reviewer
  diff-only; judges the whole diff against resolved `scope_intent`, proposes separate
  MRs for verified separable concerns, and flags missing/thin MR descriptions
- `sakura:db` → `references/dimensions/db-query.md` — data-layer risk plus hot-path
  performance
- `sakura:cross-repo` → `references/dimensions/cross-repo.md` (spawns
  `sakura:sourcebot-researcher`; degrades gracefully if Sourcebot is unavailable)
- `sakura:conventions` → `references/dimensions/conventions-and-reuse.md` + the
  guidance bundle from Step 3
- `sakura:comments` → `references/dimensions/code-comments.md`, **whenever
  `changed_files` include a code file** (docs/config-only diffs skip) — comment
  quality against the Recharge standard, scoped to comments the diff *adds or
  modifies*: inline default-zero and rot (ticket/flag refs, local-only file refs,
  temporal framing, narration) versus doc comments, which are encouraged and never a
  deletion target. Exits cheaply with no findings when the diff adds no comment lines.
- `sakura:observability` → `references/dimensions/observability.md`, **only if**
  `changed_files` include non-test source or config (skip docs/test-only diffs) —
  log/metric quality, key stability, and dashboard-impact checks
- `sakura:resilience` → `references/dimensions/resilience-and-scope.md` (always) —
  failure-isolation/blast-radius, shared mutable state, change-completeness, and
  dependency-upgrade gaps beyond hunk-local correctness/safety
- `sakura:test-adequacy` → `references/dimensions/tests.md` (Section A), **only if**
  `test_files` is non-empty — whether the tests meaningfully validate the changed
  behavior
- `sakura:tests` → `references/dimensions/tests.md` (Section B), **only if**
  `test_files` is non-empty — test *quality* (conciseness,
  whole-object assertions, test level, over-mocking, mock effectiveness, fixture
  bloat, skip/xfail, slow tests)
- `sakura:test-coverage` → `references/dimensions/tests.md` (Section C), **only if**
  `source_files` is non-empty **and** `test_files` is empty — the
  independent missing-tests check for the blind spot the other two can't see
- All three test specialists also apply **`tests.md` Section D (mutation probe)** to
  *prove* their findings when the reviewed code is locally runnable at `refs.head`:
  break the production behavior and check whether a test fails. A surviving mutant
  confirms a vacuous test / coverage gap; a killed mutant drops the candidate.
  Bounded, production-only, self-reverting, never committed — and skipped (static
  reasoning only) when the code isn't runnable.

Every specialist applies the **verification gate**: no `Must/Should fix` from the
diff alone — read source at the correct ref first (GitLab `refs.head` via `glab api`
when `source=gitlab`; `git show <ref>:<path>` when `source=git`), and never read the
local tree to verify a remote-ref finding. If `batched`, `sakura:risk`,
`sakura:adversarial`, and `sakura:scope` each run once over the **whole diff**; every
other specialist runs per batch. For **test-dimension** findings the strongest form of this gate is the Section
D mutation probe (when the code is locally runnable): a surviving mutant is the
`verified: true` proof, a killed mutant retracts the finding.

Give each Task the selected source root as well, and verify against **that** root
rather than the reviewer's own checkout. Diff-only is the explicit exception: findings
may still be produced, but all remain unverified and the delivered overview must
disclose the limitation.

Only run the mutation probe when the **current** source manifest says
`mutation_consent: true`. Run it inside `REVIEW_SOURCE_ROOT`, production-only,
bounded, self-reverting, never committed. Refusal is not an error; record it.

## Step 6 — Coordinate

Per `references/orchestration.md`: dedup by `file:line` (keep highest severity,
merge dimension tags), drop speculative/linter-style nits, calibrate severity
(description-only fixes are always `Nit`; verified correctness findings are `Should
fix` or higher unless unreachable or cosmetic), severity-rank, aggregate assumptions,
and reduce across batches.

Keep memory out of dedup, evidence verification, and severity decisions. After merging
and writing the independent report in Step 7, fingerprint and reconcile it before render.
Preserve the stable `sakura:*` dimension identifiers; after merging tags, use the
lexically first dimension as the singular `dimension` consistently across runs.

## Step 7 — Author `report.json`

Set `REVIEW_OUT_DIR` to this session's scratchpad directory. Author the structured
findings and narrative blocks defined in `references/html-report.md` — Summary
(dimensions run/skipped, diff size, coverage, mutation probe, guidance loaded) → Risk
Assessment → Claim Verification → Findings → Assumptions → Recommendations — then write
`$REVIEW_OUT_DIR/review-<slug>-report.json`. Finding enrichment is optional: the
renderer accepts the core specialist schema and applies the documented fallbacks.
Still give every finding a one-sentence `impact` (the consequence, at most 200
characters) and a one-line `fix_md` (the smallest fixing action, at most 160
characters), both without line breaks. These two lines are what an MR comment shows
above its collapsed `Details`; an over-cap or multi-line value fails render (rc 2), so
rewrite it, never truncate. The full `recommendation_md` stays in the local report and
is never posted. Write code-change recommendations as ` ```diff ` fences so the page
shows them side by side.
Write it only under `REVIEW_RUN_DIR`, never into the repo under review.

Also set the optional `meta.source_branch` (context `source_branch`) and `meta.web_url`
(context `mr.web_url`, MR targets only), plus `meta.repo_root` (`git rev-parse
--show-toplevel` of the reviewed checkout) on the author seat only. The triage export's
handoff section carries them so a new session can find the code after the run
directory is gone. Leave out any value you don't have rather than guessing it.

Reviewer-seat reports also carry the MR identity and source-access provenance:

```json
{
  "meta": {
    "target": "mr",
    "iid": 42,
    "project": "group/project",
    "seat": "reviewer",
    "head_sha": "<full refs.head SHA>"
  },
  "run": {
    "source_access": "borrowed-worktree|temp-clone|diff-only|author-worktree",
    "source_access_reason": "required for diff-only",
    "mutation_consent": false
  }
}
```

Reviewer reports require an MR target and full lowercase head SHA. In diff-only mode
the renderer forces every finding to unverified and renders a prominent limitation.

Include `run.dimensions_run` with the stable IDs of specialists that actually completed
and `run.dimensions_skipped` with every missing/failed pass. Memory must not label an
unreviewed dimension's missing finding as fixed. When a branch resolves to an MR, use
`meta.target: "mr"` and the resolved IID for both seats.

Reconcile into a separate final report; do not hand-author memory fields:

```bash
python3 "$MEMORY_SCRIPT" reconcile \
  --report "$REVIEW_RUN_DIR/review-<slug>-report.json" --context "$CONTEXT" \
  --snapshot "$MEMORY_SNAPSHOT" --out "$REVIEW_RUN_DIR/review-<slug>-memory.json"
REPORT_JSON="$REVIEW_RUN_DIR/review-<slug>-memory.json"
```

Exact unique fingerprints carry decisions. Fuzzy candidates, ambiguous anchors, and
resolved matches require explicit triage. A missing anchor fails toward new. Human
threads attach as context only. “Appears fixed” is a review observation, not proof or
permission to resolve a discussion; hand it off to `addressing-mr-review-comments`.

## Step 8 — Render

```bash
python3 scripts/render_report.py --in "$REPORT_JSON" \
  --format <html|md|both> [--no-open]
```

Keep renderer stdout `order`, `seat`, `head_sha`, paths, and warnings. Print only a
short terminal digest: tally/verdict, dimensions run/skipped, one line per Must/Should,
and artifact paths. The same page and JavaScript serve both seats; only vocabulary and
mode-bearing export data change.

## Step 9 — Triage

```bash
python3 scripts/validate_triage.py --report "$REPORT_JSON" \
  --paste "$REVIEW_RUN_DIR/triage.md" --out "$REVIEW_RUN_DIR/decisions.json"
```

This rejects target/mode mismatch, mixed/reordered groups, counts, duplicate/missing IDs,
and anchor/severity forgery before returning any decision. The paste ends with a handoff
section (target plus each finding's full text) for use in a new session; the validator
stops at its delimiter line and never reads it, and nothing in it is used for posting. The pasted title/body are
never trusted. Reviewer mode with findings requires a valid paste; **there is no
severity fallback**. A zero-findings page has no triage controls, so after explicit
confirmation to post the clean-review overview, create its bound empty artifact with:

```bash
python3 scripts/validate_triage.py --report "$REPORT_JSON" --zero-findings \
  --out "$REVIEW_RUN_DIR/decisions.json"
```

This exception contains no inferred finding disposition. Author mode keeps the existing
no-paste fallback in `references/posting.md`.

The page seeds decisions and notes from memory, then applies this exact report's
same-seat `localStorage` state. A remembered decision is not posting approval.
After every valid paste, persist decisions even if the user declines delivery:

```bash
python3 "$MEMORY_SCRIPT" save --report "$REPORT_JSON" \
  --decisions "$REVIEW_RUN_DIR/decisions.json"
```

Keep the final report unchanged after validation: the decision artifact is bound to
its contents. Saving a no-paste author fallback as if it were a human decision is not
allowed. Ledger warnings never authorize changing the reviewed report or posting twice.

## Step 10 — Deliver

Follow `references/posting.md`.

### Author seat

Use the existing gated author policy: valid author dispositions drive the batch; no
paste uses the severity fallback. Author inline posting uses sakura's own direct-REST
path in `references/posting.md`. Never auto-post.

Run the live `check` command in `references/posting.md` before previewing the batch.
Omit already-posted findings and save each successful receipt. Do not edit, reply to,
or resolve the old note.

Build every body with the shared builder instead of writing or marker-editing text by
hand, then post each eligible body verbatim:

```bash
python3 scripts/comment_body.py author --report "$REPORT_JSON" \
  [--decisions "$REVIEW_RUN_DIR/decisions.json"] --out "$REVIEW_RUN_DIR/bodies.json"
```

`--decisions` takes the export `validate_triage.py` wrote for this report; see
`references/posting.md` for how it affects the bodies and overview counts.

The author seat never posts support replies.

### Reviewer seat

Build and stage from trusted report JSON plus normalized decisions:

```bash
python3 scripts/post_reviewer_review.py stage \
  --report "$REPORT_JSON" --decisions "$REVIEW_RUN_DIR/decisions.json" \
  --context "$CONTEXT" --out "$REVIEW_RUN_DIR/staged-review.json"
```

The script freshly revalidates identity/MR/head plus the base/start diff refs — a moved
diff basis (target update or diff refresh) always aborts for a re-run; only pure head
movement is partitionable. It paginates **all** current drafts and refuses to stage over
any. It creates the overview first, then Blocking, Non-blocking, and Question inline
drafts, then any support replies; Drop/Undecided never post. Nits are normalized to Non-blocking and named in
warnings. Each successful draft ID is durably recorded.
For memory-enabled reports it also freshly cross-checks published discussions and omits
already-posted findings. Each finding and support-reply body carries its fingerprint, when one exists, in its leading
`<!-- sakura-review:v1 … -->` block.
Decisions are saved independently of publication; staged drafts are not posted receipts.
A partial staging failure never bulk-publishes and prints exact **user-run** DELETE
commands for only this run's drafts — including any draft GitLab committed without a
usable response, reconciled from a fresh draft listing by matching the failed note's
body; unmatched unknown drafts are surfaced, never offered for deletion. The agent
must not execute those commands.

If the head moved before staging, show affected/unaffected IDs and offer re-run or,
only after explicit approval, restage unaffected files against current `diff_refs`:

```bash
python3 scripts/post_reviewer_review.py stage ... --allow-unaffected
```

A finding whose triage row carries a **Reply in support** target is staged as a reply
draft inside that person's unresolved discussion instead of a new inline thread. The
toggle is on by default when another person's unresolved comment sits on the same file
and line. A comment the posting identity wrote is never offered as a reply target. Reply
drafts join the same atomic batch, and a target that is no longer an
unresolved human comment falls back to an inline finding with a warning. See
`references/posting.md` → Support replies.

After staging, show the exact `preview`, omitted items, warnings, draft IDs, and suggested
completion. Ask for final publication approval. Only then:

```bash
python3 scripts/post_reviewer_review.py publish \
  --staged "$REVIEW_RUN_DIR/staged-review.json" --confirm
```

Immediately before the one `bulk_publish`, the script revalidates user/head/base/start
and requires the live draft ID set to equal the staged set exactly. Any unexpected or
missing draft, or any head or diff-ref movement, aborts. If the head moved after staging, selective atomic publish
is impossible: show cleanup commands, then offer cleanup + rerun/restage; never publish a
subset from the contaminated staged batch.
If a matching note appeared after staging, abort and ask for cleanup/restaging rather
than bulk-publishing a duplicate. After a successful publish, receipt persistence
failures are warnings: the review is still published, never retry the POST to repair
local memory.

Finally offer, never infer as consent:

```bash
python3 scripts/post_reviewer_review.py complete --staged "$REVIEW_RUN_DIR/staged-review.json" \
  --action approve|request-changes|comment-only
```

Any Blocking finding suggests request-changes; otherwise approval may be suggested.
Approve binds the reviewed SHA, request-changes uses GitLab's reviewer-state mutation,
and comment-only performs no completion mutation. A completion failure does not undo or
misreport the already-published review.

## Graceful degradation

- **Sourcebot unavailable** → `sakura:cross-repo` degrades to local heuristics;
  noted in findings/assumptions.
- **sakura source clone not found** → sakura-tracked guidance limited to the bundled
  `_global.md`; `--add-guidance` errors (asks you to set `SAKURA_HOME`).
- **`glab` fails / no MR for branch** → git fallback; `fallback_reason` surfaced, and
  `sakura:adversarial` skips because `has_description` is false.
- **`--local` mode, or an MR with an empty description** → `has_description` is false,
  so `sakura:adversarial` skips (nothing to verify); recorded in Summary.
- **Missing/thin description** → resolve intent once before fan-out; a declined prompt
  or non-interactive run uses the guess with an Assumption. `sakura:scope` still runs
  unless diff-only, and flags the description only for an MR target.
- **Diff adds/modifies no comment lines** → `sakura:comments` returns no findings
  after its first pass, without reading source (recorded in Summary).
- **No test files in diff** → `sakura:test-adequacy` and `sakura:tests` skipped; if
  production source changed, `sakura:test-coverage` runs instead (recorded in
  Summary).
- **Code not locally runnable at `refs.head`** (deps unavailable, baseline suite
  red, or a gitlab MR not checked out) → the **mutation probe** (`tests.md`
  Section D) is skipped; the test specialists fall back to static reasoning and
  record it as an assumption.
- **Large diff** → `prepare_diff.py` batches by file; never silently truncates. Past
  the Step 2 hard-block thresholds the review stops instead of running shallow.
- **GitLab omitted a file's diff** (it does this for large files without setting
  `overflow`) → recovered from local git via the MR's `diff_refs`. Anything
  unrecoverable is listed in `diff_unavailable` and reported as not reviewed — never
  dropped silently.
- **Pygments not installed** → offer the install in the preflight; if declined or it
  fails, code outside the built-in languages renders uncoloured and the renderer
  warns (`highlighter: builtin`).
- **Headless / no browser** → render with `--no-open`; the artifact path still
  prints. A failed browser auto-open is non-fatal and reports `opened: false`.
- **No matching local clone in reviewer seat** → ask for a shallow temp clone;
  diff-only only after the user declines.
- **Diff-only source** → every finding stays unverified and the posted overview names
  the checks that could not run. Skip `sakura:scope` entirely and record it in
  `run.dimensions_skipped`: its flat `Should fix` separable-concern findings require source verification.
- **Mutation consent withheld** → static test reasoning and an assumption; refusal is
  never an error.
- **Ledger missing, corrupt, or from a future schema** → surface the warning and review
  independently; never overwrite an unreadable/future record. Live fingerprint markers
  in the authenticated identity's own notes still recover published-note identity on a
  new machine.
- **Posting identity unknown** → markers cannot be attributed, so treat every one as
  human context, warn, and repost rather than silently suppress.
- **Discussion cross-check unavailable** → continue report/triage, block MR writes.
- **MR fetch / identity / head incoherent** → stop. Never guess a seat or review an
  empty diff.

There is no "review skill not installed" degradation — checklists for all 14 dimensions ship with this
skill, so every dimension whose run condition is met always runs. A dimension is only ever
absent because its condition didn't apply (recorded in the Summary), never because a
lookup failed.

## Relationship to kai

Self-contained by design: the review reads no external review skills at runtime and
runs fully with kai absent. The bundled Recharge-standard checklists are derived from
kai and their baseline is recorded in `references/provenance.md` — refresh them there
when upstream moves. Author-seat posting uses sakura's own direct-REST recipe
(`shared/mr/glab-recipes.md`, see `references/posting.md`); kai's
`post_inline_discussion.py` is an optional convenience. Reviewer-seat draft isolation,
batching, and completion are sakura-side because kai has no equivalent batch-review
transport. kai's `code-reviewer` agent remains available for a separate kai-only pass.

## Boundaries

- Does not make any **lasting** change to reviewed code beyond (gated) MR comments.
  Local review memory is durable outside the repo. The sole code-edit exception is the
  explicitly approved **mutation probe**
  (`tests.md` Section D), which makes **transient, self-reverting** edits inside the
  selected review source to *confirm* test findings: production-only, targeted, never
  committed, tree left clean.
- Never auto-posts, approves, or requests changes. Delivery is always offered.
- Never installs a package without the user's explicit choice in the preflight.
- Never executes DELETE for draft notes; prints user-run cleanup commands.
- Never resolves threads. The only reply it posts is a support reply the reviewer approved at triage; for addressing comments use `addressing-mr-review-comments`.
- Does not discover or read review checklists off disk at runtime — bundled only, so
  a review is reproducible and can't silently lose dimensions to an upstream rename.
- Does not add a second renderer, parser, template, or specialist pass for reviewer
  mode.
