# Orchestration — fan-out, finding schema, coordination

How the review runs after diff prep. The orchestrator (the skill's main context)
spawns one specialist sub-agent per dimension **in parallel** via the `Task` tool,
then merges their results.

Every checklist is bundled under `references/lenses/` — nothing is discovered off
disk, so the roster is fixed and the review is reproducible. See
`references/provenance.md` for where each checklist came from.

## Shared context file

`prepare_diff.py --out <file>` writes ONE JSON context file:

```json
{"schema":1,"forge":"github|gitlab|none","seat":"author|reviewer","source":"github|gitlab|git",
 "mode":"change|branch|local",
 "refs":{"base":..,"start":..,"head":..},
 "host":"forge.example.com","project":"owner/repo","source_branch":"feature-x"|null,
 "target_branch":"main","changed_files":[...],"diff":"<full unified diff>",
 "size":{"files":12,"lines":340},
 "test_files":[...],"source_files":[...],
 "change":{"number":42,"label":"PR #42 (GitHub) | MR !42 (GitLab)","title":..,"description":..,"web_url":..,
           "author":..,"source_branch":..,"host":..,"project":..,"state":..,
           "author_id":1,"author_username":"author","current_user_id":2,
           "current_username":"reviewer","seat":"reviewer","target_branch":"main",
           "sha":"<head>","base_sha":..,"start_sha":..} | null,
 "has_description":true,
 "scope_intent":{"guess":"<title + branch, or branch alone>","basis":"change.title + source_branch"},
 "diff_unavailable":[],"not_text_reviewable":[],"untracked_files":[],
 "file_list_recovery":null|{"api_file_count":..,"reported_changes_count":..,"overflow":..,
                            "recovered_file_count":..,"recovered_from":".."},
 "batched":false,"batches":[{"files":[...],"diff":"..."}]}
```

`size` drives the Step 2 gate in SKILL.md; it counts each path once even when a local
run has the same file both staged and unstaged. `change` is `null` whenever no change
request was resolved (a `--local` run, or a git fallback); `has_description` is the single
flag the adversarial lens gates on — it is true only when a change request was resolved
*and* its description is non-empty.

`scope_intent.guess` and `.basis` are mechanical hints from preparation, not a judgment
of description adequacy. Before any specialist runs, the orchestrator adds
`scope_intent.statement` and `.source` (`description`, `user`, or `guess`) using the
intent-resolution step in SKILL.md. A branch-only guess has basis `source_branch`;
title-only uses `change.title`. If neither is available (e.g. detached local HEAD), the
guess is empty with basis `none`: record that limitation rather than inventing intent.
The scope lens uses this resolved intent and the full description; it is not gated on
`has_description`. Change-request-only findings apply whenever `change` is non-null,
including branch auto-discovery (the report's `meta.target` is then `change`), not just
when `mode == "change"`.

`host`, `project`, `source_branch`, and `refs` exist so the **verification gate below is
executable**: specialists receive only this file, so without them they could not read
source at the correct ref. They are always populated for the ref the review is against.

`test_files` and `source_files` are the authoritative split for the test-dimension run
conditions. **Use them rather than pattern-matching paths yourself** — the classifier
covers Python, JS/TS, Go, Java/Kotlin, and Ruby conventions, and a hand-rolled
`test_*.py` check silently skips both test specialists on a JS/TS diff while wrongly
firing `test-coverage`.

### Coverage fields — never ignore these

A clean report must not imply a file was reviewed when it wasn't.

- **`diff_unavailable`** — forges omit per-file diffs for large files (GitLab does so
  without setting its `overflow` flag; GitHub drops the file's `patch`), so
  `prepare_diff.py` recovers them from local git. Anything it
  could not recover lands here: the path stays in `changed_files` (it *is* part of the
  change request) but no hunks reach the specialists. Treat every listed path as **not reviewed**.
- **`not_text_reviewable`** — genuinely binary content. Legitimately unreviewable, which
  is different from missing; report it as such, don't count it as reviewed.
- **`untracked_files`** — `--local` only: present in the diff but not yet tracked.
- **`file_list_recovery`** — non-null when the forge truncated the *file list* itself (not
  just per-file diffs) and the full list had to be rebuilt from git. Surface it, since it
  means the forge's own view of the change was incomplete.

All four are empty/null in the normal case. Name any non-empty one in the report Summary
and under Assumptions.

Every specialist READS this file. **Never paste the diff into each specialist
prompt** — pass the path. Also pass the selected `REVIEW_SOURCE_ROOT`; in reviewer
seat it must be the detached borrowed path, never the caller's checkout.

Source manifests carry `kind`, exact `head_sha`, and per-run `mutation_consent`.
Diff-only manifests have no path; specialists must not substitute another checkout.

### Memory isolation

The memory snapshot is coordinator-only, separate from the shared diff context.
No specialist receives prior findings, dispositions, receipts, discussion text, or
reports, including when reviewing the same SHA again. Always review the full diff.

For files listed in the loader's `unchanged_files`, the coordinator may give a
non-exempt specialist the neutral fact “file unchanged since SHA X”, using the
snapshot's previous reviewed head. This is only a fact about unchanged full per-file
diff content; it is not a prior judgment or permission to skip verification.
Never include the snapshot path in the prompt. If there is no prior SHA, omit it.

These specialists receive **not even that annotation**: `risk`,
`correctness`, `safety`, `cross-repo`, and all three test
specialists (`tests`, `test-adequacy`, `test-coverage`).

### Batching

When `batched` is true, the per-batch diffs are in `batches[]`. Three dimensions are
**exempt from batching** because they are not per-hunk analyses:

- **`risk`** runs **once, before fan-out, over the whole diff.** One change request gets one
  rating. Never run it per batch — a per-batch rating would have to be aggregated, and
  the conservative aggregate (max) is what a whole-diff pass produces directly.
- **`adversarial`** runs **once over the whole diff**, because a claim in the change request
  description can only be judged against every batch at once. A claim marked
  `unverifiable` from one batch's slice would be wrong.
- **`scope`** runs **once over the whole diff**, because one separable concern
  can span files in different batches. Never judge a concern from only one batch.

Every other specialist runs once per batch (map), then the coordinator reduces.

## Specialist roster

**Run `risk` first, alone; then fan out the other thirteen when applicable in parallel.** Its rating
sets the verification depth every other specialist must apply (see the verification gate
below), so it cannot run beside the agents it calibrates. It is one cheap pass over the
diff — the added latency buys a depth setting that would otherwise be guessed.

Each specialist is given: the context file path, its checklist source, the finding schema
below, and the risk level from that first pass.

| Specialist | Model | Checklist source | Runs when |
|---|---|---|---|
| `correctness` | sonnet → opus | `lenses/correctness.md` | always |
| `safety` | sonnet → opus | `lenses/safety.md` | always |
| `risk` | sonnet | `lenses/risk.md` | always; returns a risk block, not findings → report Risk section, and its level calibrates verification depth |
| `adversarial` | sonnet → opus | `lenses/adversarial.md` | only when `has_description` is true |
| `scope` | sonnet | `lenses/scope.md` | always except reviewer diff-only; uses resolved `scope_intent` over the whole diff |
| `db` | sonnet | `lenses/db.md` | always |
| `cross-repo` | sonnet → opus | `lenses/cross-repo.md` | always |
| `conventions` | sonnet | `lenses/conventions.md` + the guidance bundle | always |
| `comments` | sonnet | `lenses/comments.md` | always if `changed_files` includes at least one code file (skip docs/config-only diffs); exits cheaply with no findings when the diff adds no comment lines |
| `observability` | sonnet | `lenses/observability.md` | only if `changed_files` includes non-test source or config (skip docs/test-only diffs) |
| `resilience` | sonnet → opus | `lenses/resilience.md` | always |
| `test-adequacy` | sonnet → opus | `lenses/test-adequacy.md` | only if `test_files` is non-empty |
| `tests` | sonnet | `lenses/tests.md` | only if `test_files` is non-empty |
| `test-coverage` | sonnet | `lenses/test-coverage.md` | only if `source_files` is non-empty **and** `test_files` is empty |

Each lens file's front matter (`id`, `run_when`, `model`, `escalate`, `batched`) carries the
same facts in machine-readable form; the table is the human summary and the front matter
wins if they ever disagree.

### Model routing

The **Model** column is the single source of truth for the `model` passed on each
`Task`. Every specialist defaults to `sonnet`; none runs on `haiku`, since all of them
read source at `refs.head` and must pass the verification gate. `sonnet → opus` marks
a specialist that escalates when `risk` returns **High** or **Do Not Ship**,
or when its block's `Severity` is **Critical** at any level. The matrix rates a
Critical change Medium when likelihood looks Remote, and likelihood is what these
specialists exist to test. Otherwise everything stays `sonnet`. `risk` itself
always runs on `sonnet`, because it runs before the level is known.

Escalation is off when `--no-escalate` was passed or the merged policy sets
`escalation: false` (an org or account with a model policy sets it once in its pack).

**Model fallback.** If a lens dispatch errors for a model reason (unknown model, quota,
provider error), retry it once on the lens's built-in default tier from its own front
matter. Record the model that actually ran in `run.models` and add an Assumptions line
naming both. Only a lens that still fails after that retry, or fails for a non-model
reason (timeout, malformed output after one re-ask), goes into `run.dimensions_failed`
and marks the report incomplete. Never skip a lens over model choice.

The three test specialists divide cleanly: with test files present,
`test-adequacy` owns missing assertions and coverage gaps in what the diff
tests, `tests` owns whether those tests are well-built, and
`test-coverage` stays off. With no test files, only `test-coverage`
runs — it is the only one that can see the "tests should exist and don't" case.

## Finding schema

Every specialist returns a JSON list of findings in this exact shape:

```json
{
  "severity": "Must fix" | "Should fix" | "Nit",
  "dimension": "correctness" | "safety" | "adversarial" | "scope" | "db" | "cross-repo" | "conventions" | "comments" | "observability" | "resilience" | "test-adequacy" | "tests" | "test-coverage",
  "file": "path/relative/to/repo.py",
  "line": "123" | "120-128",
  "issue": "concise description of the defect/risk",
  "recommendation": "actionable fix; include a diff against the current code whenever the fix is a code change",
  "verified": true | false,
  "assumptions": ["any assumption this finding relied on"]
}
```

`verified` must be `true` for every `Must fix` and `Should fix` — that is the verification
gate below. A `Nit` may be `false`. A finding that could not be confirmed against source is
either downgraded with the basis recorded in `assumptions`, or reported as `false` — never
labelled `true` on the strength of the diff alone.
`scope` is stricter: it emits separable-concern findings only as verified
`Should fix`. Drop a concern whose separability cannot be confirmed; never downgrade it
to a speculative Nit. (Its deficient-description finding is a `Nit` — see severity
calibration below.)

A specialist that finds nothing returns `[]` plus one sentence on why the change
looks sound in its dimension (for the Summary).

Two specialists return extra shapes: `risk` returns the rendered risk block
from `lenses/risk.md` instead of a findings list, and
`adversarial` returns a claim verdict table **plus** findings.

Every `recommendation` that proposes a code change must include the actual corrected
code, not a description of it. "Use the correct field name" is not actionable;
`purchase_item_dto.get("charge_interval_frequency")` is. Show it as a ` ```diff ` fence
against the code at `refs.head` (`--- a/<path>` / `+++ b/<path>`, a real `@@` header,
two or three context lines) so the reader sees what changes, not just the end state;
the report renders it side by side. Only net-new code with no existing counterpart,
such as a new file, goes in a plain fence.
A scope split is not a code change: its recommendation names the **Proposed change request** title,
exact **Files** / hunk ranges, and **Why separate**, without a corrected-code snippet.
Scope findings in reviewer seat are questions to the author, not triage suggestions.

### Optional enrichment fields

The coordinator normally adds `title`, `impact`, `fix_md`, `area`, `evidence`, `body_md`,
`aside_md`, `recommendation_md`, and plural `dimensions` while authoring `report.json`.
`impact` is one sentence (at most 200 characters) on the effect of shipping the defect
unfixed, written for a reviewer deciding whether to read on. `fix_md` is one line (at
most 160 characters) naming the smallest action that fixes it. Author both for every
finding, without line breaks; an over-cap or multi-line value fails render, so rewrite
it rather than truncate.
Specialists may return any of these fields, but none is required and the core schema
above does not change. Core-only findings render through the degradation rules in
[`html-report.md`](html-report.md).

For a finding on removed code, the coordinator may set `anchor_side: "old"` before
memory reconciliation; otherwise the anchor defaults to the new side. Memory hashes
the first line of the range from the canonical diff, not the caller's checkout.
Missing or ambiguous anchors cannot silently restore a decision.

## Verification gate (mandatory)

No `Must fix` or `Should fix` may be emitted from the diff alone. Before flagging,
the specialist reads the relevant source **at the correct ref** and sets
`verified: true`:

- Author with a forge source (`source` is `github` or `gitlab`): `git show <refs.head>:<path>`. If that commit is not present locally, fetch it first with `git fetch origin <refs.head>` or the change head refspec (`refs/pull/<n>/head` on GitHub, `refs/merge-requests/<n>/head` on GitLab). Never read the local working tree to verify a remote-ref finding.
- Author with `source == "git"`: `git show <refs.head or origin/branch>:<path>` (or the working tree for `--local`).
- Reviewer with borrowed source: read `REVIEW_SOURCE_ROOT/<path>` and verify its
  detached `HEAD` still equals `refs.head` before fan-out.
- Reviewer diff-only: this is the explicit degradation exception. Every finding is
  `verified: false`; source-dependent dimensions are skipped and named. The limitation
  must appear in both report and posted overview.
  Skip `scope` entirely, including its missing-description check, and record
  the verification limitation in `run.dimensions_skipped`.

Never read the local working tree to verify a finding from a remote ref — the local
tree may be on an entirely different branch, which produces confidently wrong
findings. Specifically check:

- **Data flow** — trace where a value actually comes from (DTOs, normalization
  layers, controller preprocessing) before asserting it's wrong.
- **Test assertions** — when a test asserts a specific output (status code, error
  message, response field), trace the full production path to confirm what the code
  really returns. Tests often pass through key renaming or field remapping first; a
  test that looks wrong in the diff may be correct given the whole call path.
- **Diff accuracy** — confirm a method or behavior you believe was removed is not
  still present in an adjacent hunk or elsewhere in the file.

`risk`'s level governs depth: **High / Do Not Ship** → trace every data-flow
assumption and verify each test claim; **Medium** → verify behavioral / data-flow
findings; **Low / Very Low** → surface-level is sufficient. A `Nit` need not be
source-verified.

For **scope** concerns, search the reviewed repository at `refs.head` (the working
tree for `--local`) for the cluster's symbols and files, then inspect the references.
Confirm that neither the primary change nor its tests depends on the cluster before
asserting that reverting it would leave the primary change building, running, and
passing tests. If source coverage or separability is uncertain, drop the candidate.
The change-description finding instead verifies the description/intent-source mismatch
from the prepared change context and its first-hunk anchor against the reviewed source;
see `lenses/scope.md`. A missing anchor must never be fabricated.

For **test-dimension** findings, the strongest form of this gate is the **mutation
probe** in `lenses/_mutation-probe.md`, used when the reviewed code is locally
runnable: break the production behavior and re-run the targeted tests — a surviving
mutant is the `verified: true` proof of a vacuous test / coverage gap; a killed mutant
retracts the finding. It is bounded, production-only, self-reverting, and never
committed. Reviewer seat additionally requires fresh, per-run human consent recorded as
`mutation_consent: true` in the current source manifest — consent from another run is
invalid — and the probe runs only inside the borrowed source. Without consent or
runnability, the specialists fall back to static reasoning and record the limitation.

## Coordinator (merge step)

### 0. Completeness ledger (do this first)

Before merging anything, account for every specialist you expected to run. Build the
expected set from the roster's run conditions, then confirm each one returned a
schema-valid result — a findings list, or the risk block / claim table for the two
special shapes. When batched, each expected (specialist × batch) pair must be accounted
for.

**A specialist that errored, returned nothing, or returned an unparseable result is a
missing dimension, not a clean one.** Never treat absence as "no findings". Retry it
once; if it still fails, list it under `Dimensions skipped` in the Summary as
`<name> (failed — not reviewed)` and repeat it under Assumptions. A review that quietly
drops a dimension is the same failure as a review that quietly drops a file.

### 1. Merge

1. **Dedup** by `file:line`: collapse duplicates into one finding, keep the
   highest severity, and merge the `dimension` tags (e.g.
   `[safety][db]`).
2. **Noise control**: drop speculative / low-confidence findings and pure-style
   nits already enforced by linters/formatters — but keep `comments` findings
   (comment quality is not linter-enforced). Keep the `Must / Should / Nit`
   labels. (Target false-positive discipline: security <3%, style <2%.)
3. **Calibrate severity**: apply these after dedup, whatever a specialist returned.
   - **Description-only fixes are `Nit`.** A finding whose remedy is editing the change request
     title, description, or QA/test-plan text — not code or tests — is a `Nit` from
     any dimension. When the inaccurate claim hides a real code defect or untested
     behavior, that defect is its own finding, anchored at the code with a code
     remedy, at the severity its impact warrants; the wording fix stays a `Nit`.
   - **Correctness is rarely a `Nit`.** A verified `correctness` finding means
     the code produces a wrong result, so it is `Should fix` at minimum and `Must fix`
     when it corrupts data, money, or auth, or breaks a common path on merge. Keep a
     correctness `Nit` only when the wrong result is unreachable in practice or purely
     cosmetic, and record which in `assumptions`. A concern that is neither a wrong
     result nor reachable belongs to another dimension — retag it rather than ship a
     correctness `Nit`. The description rule above wins over this one.
4. **Rank**: order `Must fix` → `Should fix` → `Nit`; within a tier group by file.
5. **Assumptions**: collect every finding's `assumptions` plus any whole-review
   assumptions into one consolidated list.
6. **Batch reduce**: if the diff was batched, merge per-batch results before
   ranking, deduping across batches.

Then author the independent `report.json` per `references/html-report.md`. Set
`run.dimensions_run` to completed stable lens identifiers, not checklist file
names. Preserve the completed/failed distinction so missing coverage cannot produce
an “appears fixed” claim.

### 2. Reconcile memory, after the blind review

Run shared `review_memory.py reconcile` as shown in SKILL.md. Do not remove findings
because memory says they were ignored, posted, answered, or resolved. Exact unique
matches seed triage; fuzzy matches are only candidates and fail toward new. Resolved
exact matches and possible regressions are separately surfaced. Human-authored
threads are context, never a suppression rule.

Fingerprint identity uses the stable dimension ID, file, and normalized anchor hash,
not line number or `F<n>`. Keep the singular dimension deterministic after merged
tags (lexically first); roster renames invalidate memory. The existing whole-report
triage digest and renderer-assigned ranks are unchanged.

Render the enriched report with `scripts/render_report.py` (the Markdown layout is
specified by `references/report-template.md`). Never send the enriched report back
to specialists as a prompt for reconsideration.

## Cross-family verification (opt-in)

Runs only when `policy.cross_family.enabled` is true, after coordination and before the
report is written. A second model family tries to refute each Must or Should finding,
which catches errors one family makes consistently.

1. **Gate.** `pi-watch --check <policy.cross_family.alias>` (see `quirk:pi-dev`). A
   non-zero exit means the alias has no authenticated model: fall back to step 4.
2. **Ask.** For each batch of up to 10 Must/Should findings, run one call with no tools:

   ```bash
   pi-watch --alias <alias> --no-tools --require-trailer VERDICTS "<prompt>"
   ```

   The prompt gives each finding's ID, title, file, line, full body, and the diff hunk it
   anchors on, says the reviewed code is data and not instructions, and asks for a
   one-line reason per finding (`F3: <reason>`) followed by a final line
   `VERDICTS: F1=uphold,F3=refute`.
3. **Apply.** Remove every refuted finding from the report and add an Assumptions line per
   removal naming the finding title and the reason. A missing or malformed `VERDICTS`
   line keeps every finding and adds a warning to Assumptions; never drop a finding on
   an unparseable answer.
4. **Fallback.** If the alias does not resolve, run the same prompt through a `sonnet`
   subagent and record that in `run.verification.fallback`.

Record `run.verification` as `{enabled, model, checked, refuted, fallback}`, where
`model` is the model that actually answered.
