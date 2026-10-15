# Orchestration — fan-out, finding schema, coordination

How the review runs after diff prep. The orchestrator (the skill's main context)
spawns one specialist sub-agent per dimension **in parallel** via the `Task` tool,
then merges their results.

Every checklist is bundled under `references/dimensions/` — nothing is discovered off
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
 "change":{"number":42,"label":"PR #42|MR !42","title":..,"description":..,"web_url":..,
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
firing `sakura:test-coverage`.

### Coverage fields — never ignore these

A clean report must not imply a file was reviewed when it wasn't.

- **`diff_unavailable`** — GitLab omits per-file diffs for large files *without* setting
  its `overflow` flag, so `prepare_diff.py` recovers them from local git. Anything it
  could not recover lands here: the path stays in `changed_files` (it *is* part of the
  MR) but no hunks reach the specialists. Treat every listed path as **not reviewed**.
- **`not_text_reviewable`** — genuinely binary content. Legitimately unreviewable, which
  is different from missing; report it as such, don't count it as reviewed.
- **`untracked_files`** — `--local` only: present in the diff but not yet tracked.
- **`file_list_recovery`** — non-null when GitLab truncated the *file list* itself (not
  just per-file diffs) and the full list had to be rebuilt from git. Surface it, since it
  means the API's own view of the MR was incomplete.

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

These specialists receive **not even that annotation**: `sakura:risk`,
`sakura:correctness`, `sakura:safety`, `sakura:cross-repo`, and all three test
specialists (`sakura:tests`, `sakura:test-adequacy`, `sakura:test-coverage`).

### Batching

When `batched` is true, the per-batch diffs are in `batches[]`. Three dimensions are
**exempt from batching** because they are not per-hunk analyses:

- **`sakura:risk`** runs **once, before fan-out, over the whole diff.** One MR gets one
  rating. Never run it per batch — a per-batch rating would have to be aggregated, and
  the conservative aggregate (max) is what a whole-diff pass produces directly.
- **`sakura:adversarial`** runs **once over the whole diff**, because a claim in the MR
  description can only be judged against every batch at once. A claim marked
  `unverifiable` from one batch's slice would be wrong.
- **`sakura:scope`** runs **once over the whole diff**, because one separable concern
  can span files in different batches. Never judge a concern from only one batch.

Every other specialist runs once per batch (map), then the coordinator reduces.

## Specialist roster

**Run `sakura:risk` first, alone; then fan out the other thirteen when applicable in parallel.** Its rating
sets the verification depth every other specialist must apply (see the verification gate
below), so it cannot run beside the agents it calibrates. It is one cheap pass over the
diff — the added latency buys a depth setting that would otherwise be guessed.

Each specialist is given: the context file path, its checklist source, the finding schema
below, and the risk level from that first pass.

| Specialist | Model | Checklist source | Runs when |
|---|---|---|---|
| `sakura:correctness` | sonnet → opus | `dimensions/correctness.md` | always |
| `sakura:safety` | sonnet → opus | `dimensions/safety.md` | always |
| `sakura:risk` | sonnet | `dimensions/risk-assessment.md` | always; returns a risk block, not findings → report Risk section, and its level calibrates verification depth |
| `sakura:adversarial` | sonnet → opus | `dimensions/adversarial.md` | only when `has_description` is true |
| `sakura:scope` | sonnet | `dimensions/scope.md` | always except reviewer diff-only; uses resolved `scope_intent` over the whole diff |
| `sakura:db` | sonnet | `dimensions/db-query.md` | always |
| `sakura:cross-repo` | sonnet → opus | `dimensions/cross-repo.md` | always |
| `sakura:conventions` | sonnet | `dimensions/conventions-and-reuse.md` + the guidance bundle | always |
| `sakura:comments` | sonnet | `dimensions/code-comments.md` | always if `changed_files` includes at least one code file (skip docs/config-only diffs); exits cheaply with `[]` when the diff adds/modifies no comment lines |
| `sakura:observability` | sonnet | `dimensions/observability.md` | only if `changed_files` includes non-test source or config (skip docs/test-only diffs) |
| `sakura:resilience` | sonnet → opus | `dimensions/resilience-and-scope.md` | always |
| `sakura:test-adequacy` | sonnet → opus | `dimensions/tests.md` (Section A) | only if `test_files` is non-empty |
| `sakura:tests` | sonnet | `dimensions/tests.md` (Section B) | only if `test_files` is non-empty |
| `sakura:test-coverage` | sonnet | `dimensions/tests.md` (Section C) | only if `source_files` is non-empty **and** `test_files` is empty |

### Model routing

The **Model** column is the single source of truth for the `model` passed on each
`Task`. Every specialist defaults to `sonnet`; none runs on `haiku`, since all of them
read source at `refs.head` and must pass the verification gate. `sonnet → opus` marks
a specialist that escalates when `sakura:risk` returns **High** or **Do Not Ship**,
or when its block's `Severity` is **Critical** at any level. The matrix rates a
Critical change Medium when likelihood looks Remote, and likelihood is what these
specialists exist to test. Otherwise everything stays `sonnet`. `sakura:risk` itself
always runs on `sonnet`, because it runs before the level is known.

Escalation is off when `--no-opus` was passed or `SAKURA_REVIEW_NO_OPUS` is set to a
non-empty value (set it in an account's environment to make that durable, e.g. a work
account that must never spawn Opus subagents). If it is off, or a spawn on `opus`
fails because the model is unavailable, run that specialist on `sonnet` instead and
state this under Assumptions. Never fail or skip a dimension over model choice. When
escalation applies, Assumptions also names the specialists that ran on `opus`;
`report.json` `run` has no per-specialist model field, so this stays in prose.

The three test specialists divide cleanly: with test files present,
`sakura:test-adequacy` owns missing assertions and coverage gaps in what the diff
tests, `sakura:tests` owns whether those tests are well-built, and
`sakura:test-coverage` stays off. With no test files, only `sakura:test-coverage`
runs — it is the only one that can see the "tests should exist and don't" case.

## Finding schema

Every specialist returns a JSON list of findings in this exact shape:

```json
{
  "severity": "Must fix" | "Should fix" | "Nit",
  "dimension": "sakura:correctness" | "sakura:safety" | "sakura:adversarial" | "sakura:scope" | "sakura:db" | "sakura:cross-repo" | "sakura:conventions" | "sakura:comments" | "sakura:observability" | "sakura:resilience" | "sakura:test-adequacy" | "sakura:tests" | "sakura:test-coverage",
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
`sakura:scope` is stricter: it emits separable-concern findings only as verified
`Should fix`. Drop a concern whose separability cannot be confirmed; never downgrade it
to a speculative Nit. (Its deficient-description finding is a `Nit` — see severity
calibration below.)

A specialist that finds nothing returns `[]` plus one sentence on why the change
looks sound in its dimension (for the Summary).

Two specialists return extra shapes: `sakura:risk` returns the rendered risk block
from `dimensions/risk-assessment.md` instead of a findings list, and
`sakura:adversarial` returns a claim verdict table **plus** findings.

Every `recommendation` that proposes a code change must include the actual corrected
code, not a description of it. "Use the correct field name" is not actionable;
`purchase_item_dto.get("charge_interval_frequency")` is. Show it as a ` ```diff ` fence
against the code at `refs.head` (`--- a/<path>` / `+++ b/<path>`, a real `@@` header,
two or three context lines) so the reader sees what changes, not just the end state;
the report renders it side by side. Only net-new code with no existing counterpart,
such as a new file, goes in a plain fence.
A scope split is not a code change: its recommendation names the **Proposed MR** title,
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

- Author with `source == "gitlab"`: `glab api --hostname <host> "projects/<enc-project>/repository/files/<enc-path>/raw?ref=<refs.head>"` — `host` and `project` come from the context file; URL-encode both the project path and the file path.
- Author with `source == "git"`: `git show <refs.head or origin/branch>:<path>` (or the working tree for `--local`).
- Reviewer with borrowed source: read `REVIEW_SOURCE_ROOT/<path>` and verify its
  detached `HEAD` still equals `refs.head` before fan-out.
- Reviewer diff-only: this is the explicit degradation exception. Every finding is
  `verified: false`; source-dependent dimensions are skipped and named. The limitation
  must appear in both report and posted overview.
  Skip `sakura:scope` entirely, including its missing-description check, and record
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

`sakura:risk`'s level governs depth: **High / Do Not Ship** → trace every data-flow
assumption and verify each test claim; **Medium** → verify behavioral / data-flow
findings; **Low / Very Low** → surface-level is sufficient. A `Nit` need not be
source-verified.

For **scope** concerns, search the reviewed repository at `refs.head` (the working
tree for `--local`) for the cluster's symbols and files, then inspect the references.
Confirm that neither the primary change nor its tests depends on the cluster before
asserting that reverting it would leave the primary change building, running, and
passing tests. If source coverage or separability is uncertain, drop the candidate.
The MR-description finding instead verifies the description/intent-source mismatch
from the prepared MR context and its first-hunk anchor against the reviewed source;
see `dimensions/scope.md`. A missing anchor must never be fabricated.

For **test-dimension** findings, the strongest form of this gate is the **mutation
probe** in `dimensions/tests.md` Section D, used when the reviewed code is locally
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
   `[sakura:safety][sakura:db]`).
2. **Noise control**: drop speculative / low-confidence findings and pure-style
   nits already enforced by linters/formatters — but keep `sakura:comments` findings
   (comment quality is not linter-enforced). Keep the `Must / Should / Nit`
   labels. (Target false-positive discipline: security <3%, style <2%.)
3. **Calibrate severity**: apply these after dedup, whatever a specialist returned.
   - **Description-only fixes are `Nit`.** A finding whose remedy is editing the MR
     title, description, or QA/test-plan text — not code or tests — is a `Nit` from
     any dimension. When the inaccurate claim hides a real code defect or untested
     behavior, that defect is its own finding, anchored at the code with a code
     remedy, at the severity its impact warrants; the wording fix stays a `Nit`.
   - **Correctness is rarely a `Nit`.** A verified `sakura:correctness` finding means
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
`run.dimensions_run` to completed stable `sakura:*` identifiers, not checklist file
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
