# quirk:full-code-review deep mode — tech spec

**Status:** Implementation verified and reviewed. Recall acceptance remains blocked on Sonnet authentication.
**Logic spec:** [logic.md](logic.md). Behavior and acceptance remain owned there.

Reader: implementers and reviewers deciding whether the deep-mode implementation meets the approved behavior.

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

The coordinator is the skill, not a new model-dispatch service. `skills/full-code-review/SKILL.md` routes `--deep [minutes]` to [deep.md](../../../../skills/full-code-review/references/deep.md). Four Python 3.9+ standard-library helpers supply its deterministic boundaries:

| File under `skills/full-code-review/scripts/` | Responsibility |
|---|---|
| `deep_sandbox.py` | Trust eligibility, independent temporary source copies, isolated execution and cleanup |
| `build_area_map.py` | Import/reference coupling, size-bounded areas and verification questions |
| `merge_deep_findings.py` | Checker gating, duplicate consolidation and incomplete coverage |
| `score_deep_report.py` | Target-bound recall and independently sampled false-positive measurement |

The three underscore-prefixed prompts in `references/lenses/` are not registered standard lenses: `_area-finder.md`, `_contract.md`, `_checker.md`. Standard lens discovery and policy remain unchanged. Finders use Sonnet; checkers use Sonnet with existing risk-based escalation.

## Code references

Back-links: [Data flow](logic.md#data-flow), [Decisions Locked](logic.md#decisions-locked).

Paths are relative to the repository root. Symbols, rather than pre-implementation line numbers, identify the integration points:

- `skills/full-code-review/scripts/deep_sandbox.py`: `evaluate_trust`, `probe_capabilities`, `acquire_copy`, `exec_in_copy`, `release_copy`, `main`.
- `skills/full-code-review/scripts/build_area_map.py`: `build_coupling_graph`, `partition_areas`, `build_area_map`, `main`.
- `skills/full-code-review/scripts/merge_deep_findings.py`: `merge_deep_run`, `main`.
- `skills/full-code-review/scripts/score_deep_report.py`: `match_defect`, `score_report`, `main`.
- `skills/full-code-review/scripts/render_report.py`: `_prepare_report`, `_validate_contract_run`, `_finding_card`, `_checked_dropped_section`, `_content`, `_render_md_prepared`, `handoff_payload`.
- `skills/full-code-review/scripts/comment_body.py`: `_author_bodies`.
- `skills/full-code-review/scripts/post_author_comments.py`: `post`.
- `skills/full-code-review/scripts/post_reviewer_review.py`: `_plan`, called by `stage`.

## Contracts & interfaces

Back-links: [Behavior & scenarios](logic.md#behavior--scenarios), [Decisions Locked](logic.md#decisions-locked).

### Execution uses independent git metadata

`evaluate_trust(context, source_access)` returns eligibility and whether consent may be requested, never consent itself. Author-seat execution is eligible; reviewer execution requires a trusted non-fork author. Diff-only execution is refused.

`acquire_copy(source_root, head_sha, out_manifest, label)` requires the expected full SHA and produces a worktree snapshot with independent git metadata. Acquisition does not load caller git configuration, hooks, fsmonitor, or filters. APFS clonefile is used for source data when available; ordinary copying is the fallback. Linked worktrees are not registered in the user's repository.

The copy preserves local source changes and reports them in `source_state`; it does not falsely label a dirty worktree snapshot as pristine committed content. Each finder gets its own copy, and each claim gets a fresh checker context and copy. Copies are released immediately after the owning agent exits and again through a coordinator finally path.

`exec_in_copy(manifest_path, command, timeout, cwd_rel)` runs argv under an environment allowlist, private HOME/XDG/tmp directories, disabled git hooks/configuration, and forge-command blocking. It returns command exit/output, timeout and environment-unavailable status rather than interpreting a nonzero command as proof of a defect. Timeout termination covers the process group. Cleanup validates a private acquisition record, not just path prefixes.

macOS uses Seatbelt and Linux uses Bubblewrap when usable. The standalone temporary worktree fallback has environment isolation, not OS-enforced filesystem isolation. OS credential protection covers conventional and explicitly configured credential paths; it is not universal secret discovery. Detached descendants are not guaranteed to remain in a process group without PID-namespace enforcement. The report must retain these limits rather than implying an untrusted-code sandbox.

### Areas account for the entire reviewed source

`build_area_map(context, source_root, risk, max_lines=1800, max_files=8)` accepts the policy-filtered context and optional source/risk data. Every changed path appears exactly once. Imports, path mentions, shared boundary markers and test pairing inform coupling; the coordinator refines the questions from the diff and risk result.

Full source lines count toward size, including embedded styles. Oversized files occupy their own area. A boundary split by the size limit remains the whole-change contract lens's responsibility. Missing source falls back to the available diff, never an unrelated checkout. Invalid paths/JSON are errors, not silent exclusions.

### Only checked significant claims enter findings

`merge_deep_run(lens_findings, deep_candidates, checker_verdicts, area_map, trust_info, budget_info)` returns findings, deep-run metadata, coverage notes, assumptions and any incomplete-verdict override.

- Every deep candidate and every standard Must/Should finding requires a checker verdict. Explicit `budget_info.checker_failures` withholds failed checks and marks the report incomplete; an unexplained missing verdict is an error.
- Candidate IDs must be unique across all inputs. Unknown or duplicate checker IDs are errors.
- Confirmed/plausible findings survive; refuted claims go only to `checked_and_dropped` with reasons. Plausible findings require `what_would_confirm` and are never postable.
- Reproduced evidence requires the checker's command and observed output. Reading code never becomes reproduced evidence.
- The checker may recalibrate severity. Duplicate consolidation retains the strongest surviving severity and evidence, merging dimensions. Explicit root-cause keys permit cross-anchor duplicates; nearby lines or shared title words do not establish equivalence.
- Overlong title/impact/fix text must be rewritten, not silently truncated.
- Pending/unreached areas, declared checker failures and exceeded budgets produce incomplete coverage. No unchecked claims appear as findings.

### Scoring requires evidence, not optimistic defaults

`score_report(report, answer_key, spot_check=None, budget_minutes=60)` reports recall even when evaluation proof is absent. A passing score additionally requires matching project/number/revision, enabled complete deep coverage, measured elapsed time within budget, and a nonempty external spot-check sample.

Scoring reuses the renderer's severity ranking and canonical `F1..Fn` IDs, not finder IDs. It accepts omitted authored IDs and integer line values; duplicate authored IDs are invalid. A finding refuted by the external spot check cannot count toward recall. Plausible claims do not count as confirmed defects.

The refuted share uses actually checked shown findings as its denominator. Missing judgments produce an unknown share, not zero. Partial sampling is permitted and reports checked count, coverage and unchecked IDs. Missing/invalid evidence cannot be a passing acceptance run. CLI exits are 0 for passing, 1 for unmet acceptance, and 2 for invalid input. Inputs are not mutated.

## Data models / schemas

Back-links: [Data flow](logic.md#data-flow), [Success criteria](logic.md#success-criteria).

The maintained report schema lives in [html-report.md](../../../../skills/full-code-review/references/html-report.md); finder/checker output shapes live in their corresponding prompts. The coordinator procedure and input-file names live in [deep.md](../../../../skills/full-code-review/references/deep.md).

`run.deep` carries budget/timing, trust/consent, execution/isolation details, area status, unreached areas, checker failures and refutations. Findings add `verification_status`, `repro`, `what_would_confirm` and optional root-cause `dedup_key`. The existing report schema version remains 1 because these fields are additive.

Copy manifests are private schema-2 acquisition records with lease identity, independent copy/environment paths, source SHA/state, copy/snapshot/isolation kinds, protected credential/executable paths and release state. They are neither policy nor persistent consent.

The pinned answer key is `tests/fixtures/full-code-review/answer-keys/pr50-3605fd8.json`, bound to `3605fd8777b60646bcad11aba08f83c2c858e6b9`. Its defect membership and per-candidate dispositions are authoritative in that fixture, not duplicated as a count here.

## DO-NOT-CHANGE fences

Back-link: [Scope & non-goals](logic.md#scope--non-goals).

- Preserve the 14 standard lens checklists and their discovery/policy behavior; deep mode is opt-in and supplies no new policy key.
- Preserve size-gate behavior; `--deep` is not a size override.
- Preserve the forge adapters and triage grammar. Refutations never enter triage; plausible findings are blocked at body construction and both posting paths.
- Preserve renderer escaping, highlighting and the five numbered Markdown sections.
- Keep the skill entrypoint within its existing line budget; procedural detail belongs in its reference.

## Always / Ask / Never

Back-link: [Decisions Locked](logic.md#decisions-locked).

Always bind source reads to the reviewed revision, report coverage honestly, keep memory away from independent discovery/checking, and record actual model routing. Ask once per eligible run before executing reviewed code; refusal is read-only review, not an error.

Never run deep repros in the caller's checkout, seed finders with the answer key, infer a completed area from silence, post plausible findings, or describe missing runtime evidence as a successful evaluation.

## Cross-cutting

Back-links: [Data flow](logic.md#data-flow), [Decisions Locked](logic.md#decisions-locked).

The run clock starts at invocation and includes preparation. At 80% no new finders start. Remaining commands and checker dispatches receive the remaining deadline. Failed or unfinished checks are withheld and reported; raw candidates are never substituted when time expires.

Deep fields are optional for standard reports. The renderer forces pending/unreached areas or checker failures to incomplete and shows a persistent deep incomplete banner above the tabs' content. Both author and reviewer posting omit plausible findings even when triaged to post.

## Testing strategy

Back-links: [Behavior & scenarios](logic.md#behavior--scenarios), [Success criteria](logic.md#success-criteria).

The `tests/full_code_review/` suites cover sandbox trust/lifecycle, private cleanup, credential/config isolation, process-group timeout, complete area accounting, checker gating and failure paths, lossless text limits, renderer/triage/posting behavior, canonical scorer IDs, target binding, and missing/partial sampling evidence. Preserve Python 3.9 and current-Python compatibility.

A synthetic CLI smoke must acquire/execute/release a copy, observe an actual wrong result, build coupled areas, merge confirmed/plausible/refuted claims, render both formats, validate an actual browser triage export, and prove a plausible Will-fix finding remains non-postable. This is protocol evidence, not measured defect recall.

Acceptance still requires two fresh Sonnet deep runs of pinned PR #50 within 60 minutes, every confirmed answer-key defect caught, and no more than 20% refutations on independent spot checks. Historical reports, seeded prompts and literal elapsed-time estimates cannot satisfy this gate. The local Sonnet runtime probe currently fails Anthropic OAuth refresh (`invalid_grant`); acceptance remains blocked until authentication is repaired.

## Non-goals

Back-link: [Scope & non-goals](logic.md#scope--non-goals).

No automatic deep enablement, cleanup angles, relaxed size gate, untrusted reviewer execution, standard-lens execution in deep mode, or changed forge publishing protocol.
