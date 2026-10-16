# quirk:full-code-review deep mode — tech spec

**Status:** Reviewed
**Logic spec:** [logic.md](logic.md) — this document owns *where* and *contracts*; the logic spec owns *why* and *behavior*.

Paths below use these roots:

- `Q` = `/Users/zpyoung/orca/workspaces/quirk/code-review` (this repository)
- `SK` = `Q/skills/full-code-review`

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow), [Decisions Locked](logic.md#decisions-locked).

Deep mode is an opt-in `--deep [minutes]` extension to `SK` implemented in Python 3.9+ using the standard library only. The standard 14-lens path is untouched when `--deep` is omitted. When `--deep` is passed, four deterministic scripts and four reference/prompt documents extend the coordinator pipeline between Step 4 (policy/guidance/memory) and Step 8 (render):

Target layout (new and modified files):

- `SK/SKILL.md` — modified (must stay ≤ 500 lines, enforced by `Q/tests/full_code_review/test_full_code_review_skill.py:24-25`); adds `--deep [minutes]` to `argument-hint` (`SKILL.md:5`), the Flags table (`SKILL.md:58-72`), and a routing subsection under Step 5/Step 6 pointing to `$REFS/deep.md`.
- `SK/references/deep.md` — new; coordinator runbook for deep mode: trust check, single consent prompt, budget clock and 80% cutoff, area-map construction, parallel dispatch of area finders + contract lens + standard lenses, fresh checker dispatch, merge into `report.json`, and `finally` release of throwaway copies.
- `SK/references/lenses/_area-finder.md` — new (prefixed with `_` so `Q/tests/full_code_review/test_full_code_review_skill.py:20-21` and `SK/scripts/resolve_policy.py` keep the 14-lens standard roster unchanged); prompt and output contract for per-area defect finders (`model: sonnet`, `escalate: false`, one dispatch per area).
- `SK/references/lenses/_contract.md` — new (prefixed with `_`); prompt and output contract for the cross-file producer/consumer and doc-to-script contract lens (`model: sonnet`, `escalate: false`, runs once over the whole change).
- `SK/references/lenses/_checker.md` — new (prefixed with `_`); prompt and output contract for fresh candidate verification and repro re-execution (`model: sonnet`, `escalate: true` — escalates to `opus` when `risk.level` is `High` or `Do Not Ship` or when risk `Severity` is `Critical`, unless `policy.escalation` is `false` or `--no-escalate` was passed, matching `SK/references/orchestration.md:169-188`).
- `SK/references/html-report.md`, `SK/references/report-template.md`, `SK/references/posting.md`, `SK/references/degradation.md` — modified; document `run.deep`, finding `verification_status` / `repro` / `what_would_confirm`, the collapsed "Checked and dropped" section, and the posting block on `plausible` findings.
- `SK/scripts/deep_sandbox.py` — new; trust-rule evaluation, OS sandbox detection (`sandbox-exec` on macOS, `bwrap` on Linux, worktree fallback), disk-safe throwaway copy creation (`cp -cR` APFS clonefile on macOS, detached `git worktree` with hooks disabled as fallback), isolated environment (`HOME`, `XDG_*`, `TMPDIR`, stub `gh`/`glab` in `PATH`, stripped forge tokens), bounded command execution, and cleanup.
- `SK/scripts/build_area_map.py` — new; parses `context.json` and `$REVIEW_SOURCE_ROOT` to build a producer/consumer file-coupling graph, partitions changed files into size-bounded areas, attaches baseline and risk-derived questions, and writes `area-map.json`.
- `SK/scripts/merge_deep_findings.py` — new; merges checked deep candidates and checked standard-lens findings with unchecked Nit lens findings, deduplicates by file/line or coupled root cause, attaches `evidence` (`"reproduced"` or `"read from code"`), `repro`, `verification_status` (`"confirmed"` or `"plausible"`), `what_would_confirm`, and populates `run.deep.checked_and_dropped`, `run.deep.areas`, `run.incomplete`, and `run.coverage`.
- `SK/scripts/score_deep_report.py` — new; evaluates a deep-mode `report.json` against an answer-key JSON fixture and optional spot-check verdicts, reporting caught/missed defects, recall, refuted share, and pass/fail against the logic spec's bar.
- `SK/scripts/render_report.py` and `SK/assets/report.html` — modified; validate and render `run.deep` (area map and collapsed "Checked and dropped" list), finding `verification_status` (`"confirmed"` | `"plausible"`), `repro` (`command`, `output`), and `what_would_confirm` in both HTML and Markdown outputs.
- `SK/scripts/comment_body.py`, `SK/scripts/post_author_comments.py`, `SK/scripts/post_reviewer_review.py` — modified; block `plausible` findings (`verification_status == "plausible"`) from ever being marked `post: true`, staged, or posted, even when triaged as `Will fix` (`fix`) or `Blocking` (`fix`).
- `Q/tests/fixtures/full-code-review/answer-keys/pr50-3605fd8.json` — new; verified answer-key fixture for PR #50 at commit `3605fd8`.

Runtime data flow in deep mode:

1. Steps 1–4 run via `prepare_diff.py`, `borrow_review_source.py` (reviewer seat), `resolve_policy.py`, `discover_guidance.py`, and `review_memory.py load` as today.
2. `deep_sandbox.py check-trust --context "$CONTEXT"` evaluates the execution trust rule. When trusted (author seat, or reviewer seat with `change.is_fork is False` and `change.author_trusted is True`, and not `diff-only`), the coordinator asks one consent prompt naming the target, `refs.head`, throwaway copy path, network allowed, `gh`/`glab` disabled, and budget in minutes.
3. `risk` lens runs first.
4. `build_area_map.py` partitions `context["changed_files"]` into size-bounded areas keeping producer/consumer files together and writes `$REVIEW_RUN_DIR/area-map.json`.
5. Within the `--deep <minutes>` budget (default 60), standard lenses, one area finder per area (on `sonnet`, up to the 80% budget cutoff), and the contract lens (once over the whole change, on `sonnet`) run in parallel. Finders with execution consent run repro commands exclusively via `deep_sandbox.py exec`.
6. Every candidate from area finders and the contract lens, plus every `Must fix` and `Should fix` finding from the standard lenses, is dispatched to a fresh checker (`_checker.md`, on `sonnet` or escalated to `opus` per `SK/references/orchestration.md:169-188` when risk is `High` / `Do Not Ship` / `Critical` and escalation is enabled) which reads the claim and the code at `refs.head` and reruns any repro in its own fresh throwaway copy.
7. `merge_deep_findings.py` combines checker verdicts and standard-lens findings into `report.json` fields (`findings`, `run.deep`, `run.coverage`, `run.incomplete`, `meta.verdict`), followed by `review_memory.py reconcile`, `render_report.py`, `validate_triage.py`, and posting scripts.

## Code references

Back-links: [Data flow](logic.md#data-flow), [Behavior & scenarios](logic.md#behavior--scenarios), [Decisions Locked](logic.md#decisions-locked).

### Existing files and symbols to modify

- `SK/SKILL.md`
  - Line 5 (`argument-hint`): add `[--deep [minutes]]`.
  - Lines 58–72 (`### Flags` table): add row for `--deep [minutes]`.
  - Lines 306–353 (`## Step 5` and `## Step 6`): add concise conditional routing to `$REFS/deep.md` when `--deep` is passed, keeping total line count ≤ 500 (`Q/tests/full_code_review/test_full_code_review_skill.py:24-25`).
- `SK/scripts/borrow_review_source.py`
  - `probe_refusal(context)` (`borrow_review_source.py:147-158`): reused by `deep_sandbox.py` for reviewer-seat trust evaluation (`change.is_fork is False` and `change.author_trusted is True`).
- `SK/scripts/render_report.py`
  - `_RUN_FIELDS` (`render_report.py:25-28`): add `"deep"`.
  - `_FINDING_FIELDS` (`render_report.py:51`): add `"verification_status"`, `"repro"`, `"what_would_confirm"`.
  - `_HANDOFF_FINDING` (`render_report.py:1260-1261`): add `"verification_status"`, `"repro"`, `"what_would_confirm"`.
  - `_validate_contract_run(run, meta, warnings)` (`render_report.py:363-386`): validate `run["deep"]` when present; if `run["deep"].get("unreached_areas")` is non-empty, enforce `run["incomplete"] = True` and `meta["verdict"] = "Incomplete review"`.
  - `_prepare_report(report)` (`render_report.py:388-549`): validate finding `verification_status` in `("confirmed", "plausible")`, validate `repro` (`{"command": str, "output": str}` required when `evidence == "reproduced"` in a deep report), and require non-empty `what_would_confirm` when `verification_status == "plausible"`.
  - `_what_was_run(report)` (`render_report.py:669-723`): render `run.deep.areas` (area ID, files, questions, status/degraded reason) and deep budget/sandbox summary.
  - `_finding_card(finding, seat="author")` (`render_report.py:961-1004`): render a `"plausible"` warning token and **What would confirm this** callout when `verification_status == "plausible"`, and render a **Reproduction** block (`repro.command` and `repro.output`) when `repro` is present.
  - `_findings_section(report)` (`render_report.py:1147-1185`): append a collapsed `<details class="checked-dropped"><summary>Checked and dropped (N)</summary>...</details>` block when `run.deep.checked_and_dropped` is non-empty.
  - `_render_md_prepared(report)` (`render_report.py:1327-1432`): render the area map in `## 1. Summary`, render `**Evidence:**`, `**Status:** Plausible — what would confirm: ...`, and `**Reproduction:**` on each finding in `## 3. Findings`, and append a collapsed `<details><summary>Checked and dropped (N)</summary>...</details>` block at the end of `## 3. Findings` (preserving the 5-section heading invariant tested in `Q/tests/full_code_review/test_full_code_review_skill.py:69-75`).
- `SK/scripts/comment_body.py`
  - `_author_bodies(raw, decisions=None)` (`comment_body.py:668-725`): check `finding.get("verification_status") == "plausible"` before `_POSTED_SLOTS`; if plausible, keep `post: False` and append to `omitted` with `reason: "plausible finding (never posted)"`.
- `SK/scripts/post_author_comments.py`
  - `post(report, context, bodies, ids, out, overview=False, forge=None)` (`post_author_comments.py:52-105`, CLI entry `main(argv=None)` at line 108): if a finding in `report["findings"]` has `verification_status == "plausible"`, skip it with a warning even if its ID was passed in `--ids`.
- `SK/scripts/post_reviewer_review.py`
  - `_plan(prepared, by_id, context, refs, forge, changed_paths=None)` (`post_reviewer_review.py:249-338`, called by `stage(args)` at `post_reviewer_review.py:393-488`): in the per-finding loop (`lines 260-330`), if `finding.get("verification_status") == "plausible"`, append to `omitted` with `reason: "plausible finding (never posted)"` and `continue` before staging any draft or counting it toward blocking findings.

### New files to create

- `SK/scripts/deep_sandbox.py`
- `SK/scripts/build_area_map.py`
- `SK/scripts/merge_deep_findings.py`
- `SK/scripts/score_deep_report.py`
- `SK/references/deep.md`
- `SK/references/lenses/_area-finder.md`
- `SK/references/lenses/_contract.md`
- `SK/references/lenses/_checker.md`
- `Q/tests/fixtures/full-code-review/answer-keys/pr50-3605fd8.json`
- `Q/tests/full_code_review/test_deep_sandbox.py`
- `Q/tests/full_code_review/test_build_area_map.py`
- `Q/tests/full_code_review/test_merge_deep_findings.py`
- `Q/tests/full_code_review/test_score_deep_report.py`

## Contracts & interfaces

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow), [Behavior & scenarios](logic.md#behavior--scenarios), [Decisions Locked](logic.md#decisions-locked), [Deferred Ideas](logic.md#deferred-ideas).

### 1. `deep_sandbox.py` — trust evaluation, throwaway copies, and OS sandboxing

 Resolves the two `[tech-spec]` items in [Deferred Ideas](logic.md#deferred-ideas):
- **OS sandbox detection:** On macOS (`sys.platform == "darwin"`), probes `/usr/bin/sandbox-exec` by executing `/usr/bin/sandbox-exec -p '(version 1)(allow default)' /usr/bin/true`. On Linux (`sys.platform.startswith("linux")`), probes `bwrap` (`shutil.which("bwrap")`) via `bwrap --ro-bind / / --dev /dev --proc /proc /bin/true`. If the OS probe succeeds, `sandbox_kind` is `"sandbox-exec"` or `"bwrap"`; otherwise `sandbox_kind` is `"worktree"` (temporary copy with environment/hook/PATH isolation).
- **Disk-safe throwaway copies:** On macOS/APFS, `acquire` clones `$REVIEW_SOURCE_ROOT` into a canonical (`os.path.realpath`) temporary directory via `cp -cR` (APFS `clonefile(2)` copy-on-write, which shares data blocks and copies 11,000+ files in <100 ms with near-zero disk overhead), then removes `.git/hooks` and writes `.git/config` with `core.hooksPath = /dev/null` and `core.fsmonitor = false`. When `cp -cR` is unsupported or fails (cross-device or Linux non-CoW filesystem), `acquire` falls back to `git -C <source_root> -c core.hooksPath=/dev/null -c core.fsmonitor=false worktree add --detach <copy_dir> <head_sha>`. Each finder/checker copy is released immediately when that agent finishes so concurrent worktrees never exceed the parallel dispatch width.

`CONTRACT:`
```python
def evaluate_trust(context: dict, source_access: str = "author-worktree") -> dict: ...
def probe_capabilities(source_root: str) -> dict: ...
def acquire_copy(source_root: str, head_sha: str, out_manifest: str, label: str = "finder") -> dict: ...
def exec_in_copy(manifest_path: str, command: list[str], timeout: int = 120, cwd_rel: str = ".") -> dict: ...
def release_copy(manifest_path: str) -> dict: ...
```

`COMMAND:`
```bash
python3 "$SCRIPTS/deep_sandbox.py" check-trust --context "$CONTEXT" [--source-access <kind>]
python3 "$SCRIPTS/deep_sandbox.py" acquire --source-root "$REVIEW_SOURCE_ROOT" --head-sha "$HEAD_SHA" --label <id> --out "$REVIEW_RUN_DIR/copy-<id>.json"
python3 "$SCRIPTS/deep_sandbox.py" exec --manifest "$REVIEW_RUN_DIR/copy-<id>.json" [--timeout 120] [--cwd <rel>] -- <command...>
python3 "$SCRIPTS/deep_sandbox.py" release --manifest "$REVIEW_RUN_DIR/copy-<id>.json"
```

- **Preconditions:**
  - `check-trust`: `context` is a valid `prepare_diff.py` context dict.
  - `acquire`: `source_root` is an existing directory whose `git rev-parse HEAD` equals `head_sha` (40-char hex).
  - `exec`: `manifest_path` was written by `acquire` and not yet released; `command` is a non-empty argv list.
- **Postconditions:**
  - `check-trust` returns `{"allowed": bool, "prompt_required": bool, "reason": str | None}`. `allowed` is `True` iff `source_access != "diff-only"` and (`seat == "author"` or (`seat == "reviewer"` and `change.is_fork is False` and `change.author_trusted is True`)). When `allowed` is `False`, `prompt_required` is `False` and `reason` states why (e.g. `"the change comes from a fork"`, `"the change author is not a trusted member of the repository"`, or `"diff-only source access"`).
  - `acquire` creates an isolated `copy_dir` and `env_dir` (both resolved with `os.path.realpath` so macOS Seatbelt subpaths never fail on `/tmp` $\to$ `/private/tmp` symlinks), writes stub `gh` and `glab` executables in `<env_dir>/bin` that exit 127 with a diagnostic on stderr, and writes the manifest JSON.
  - `exec` runs `command` with `cwd = <copy_dir>/<cwd_rel>`, `HOME=<env_dir>/home`, `XDG_CONFIG_HOME=<env_dir>/xdg_config`, `XDG_STATE_HOME=<env_dir>/xdg_state`, `XDG_CACHE_HOME=<env_dir>/xdg_cache`, `TMPDIR=<env_dir>/tmp`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, `<env_dir>/bin` prepended to `PATH`, and credential variables (`GH_TOKEN`, `GITHUB_TOKEN`, `GLAB_TOKEN`, `GITLAB_TOKEN`, `SSH_AUTH_SOCK`, `GIT_ASKPASS`) stripped. Under `sandbox-exec`, file writes outside `<copy_dir>` and `<env_dir>` are kernel-denied while network is allowed (`(allow network*)`). Returns `{"exit_code": int, "stdout": str, "stderr": str, "timed_out": bool, "sandbox_kind": str, "environment_unavailable": bool, "unavailable_reason": str | None}` and exits 0 (the payload carries the command's `exit_code`).
  - `release` removes `copy_dir` and `env_dir`. If `copy_kind == "git-worktree"`, it runs `git -C <source_root> worktree remove --force <copy_dir>` (never a repo-wide `git worktree prune`).
- **Invariants:**
  - `source_root` is never mutated by `acquire`, `exec`, or `release`.
  - No git hook in `source_root` or user global git config ever runs during `acquire` or `exec`.
- **Errors:**
  - Invalid arguments, `head_sha` mismatch, or missing manifest exits 2 with `{"error": "<message>"}` on stdout.

### 2. `build_area_map.py` — size-bounded coupled area partitioning

Back-links: [Data flow](logic.md#data-flow), [Key decisions & rationale](logic.md#key-decisions--rationale), [Glossary](logic.md#glossary).

`CONTRACT:`
```python
def build_coupling_graph(changed_files: list[str], source_root: str | None, diff_text: str) -> dict[str, set[str]]: ...
def partition_areas(changed_files: list[str], coupling: dict[str, set[str]], file_lines: dict[str, int], max_lines: int = 1800, max_files: int = 8) -> list[dict]: ...
def build_area_map(context: dict, source_root: str | None = None, risk: dict | None = None, max_lines: int = 1800, max_files: int = 8) -> dict: ...
```

`COMMAND:`
```bash
python3 "$SCRIPTS/build_area_map.py" --context "$CONTEXT" [--source-root "$REVIEW_SOURCE_ROOT"] [--risk "$REVIEW_RUN_DIR/risk.json"] [--max-lines 1800] [--max-files 8] --out "$REVIEW_RUN_DIR/area-map.json"
```

- **Preconditions:** `context` has `changed_files` (list of repo-relative paths) and `diff` (unified diff string).
- **Postconditions:**
  - Detects producer/consumer edges across `changed_files` from:
    1. Python imports (`import <mod>`, `from <mod> import ...`) resolved against sibling/repo modules.
    2. Script/reference/asset path mentions (e.g., `SKILL.md` or `references/*.md` naming `scripts/<name>.py` or `assets/<name>`, `render_report.py` naming `assets/report.html` and `validate_triage.py`).
    3. Test-to-subject pairing (`test_<stem>.py` $\leftrightarrow$ `<stem>.py`).
  - Groups connected files greedily along coupling edges into areas `A1..An` bounded by `max_lines` (default 1800 changed+enclosing lines) and `max_files` (default 8 files); a single file exceeding `max_lines` forms a single-file area.
  - Generates 2–5 concrete verification questions per area derived from the coupled boundaries, file roles, and optional `risk` output.
  - Writes `area-map.json` with `schema_version: 1` and `areas: [...]`.
- **Invariants:** Every path in `context["changed_files"]` appears in the `files` list of exactly one area in `areas`, in deterministic order.
- **Errors:** Exits 2 with `{"error": "<message>"}` on unreadable input or invalid JSON.

### 3. `merge_deep_findings.py` — budget accounting, checker gating, dedup, and report assembly

Back-links: [Data flow](logic.md#data-flow), [Key decisions & rationale](logic.md#key-decisions--rationale), [Behavior & scenarios](logic.md#behavior--scenarios), [Decisions Locked](logic.md#decisions-locked).

`CONTRACT:`
```python
def merge_deep_run(
    lens_findings: list[dict],
    deep_candidates: list[dict],
    checker_verdicts: list[dict],
    area_map: dict,
    trust_info: dict,
    budget_info: dict,
) -> dict: ...
```

`COMMAND:`
```bash
python3 "$SCRIPTS/merge_deep_findings.py" \
  --lens-findings "$REVIEW_RUN_DIR/lens-findings.json" \
  --deep-candidates "$REVIEW_RUN_DIR/deep-candidates.json" \
  --checker-verdicts "$REVIEW_RUN_DIR/checker-verdicts.json" \
  --area-map "$REVIEW_RUN_DIR/area-map.json" \
  --trust "$REVIEW_RUN_DIR/deep-trust.json" \
  --budget "$REVIEW_RUN_DIR/deep-budget.json" \
  --out "$REVIEW_RUN_DIR/deep-merged.json"
```

- **Preconditions:**
  - Every `deep_candidates` item and every `Must fix` / `Should fix` item in `lens_findings` has a corresponding verdict in `checker_verdicts` (matched by `id`). Unchecked candidates are never admitted to `findings`.
- **Postconditions:**
  - **Refuted candidates (`verdict == "refuted"`):** excluded from `findings` and placed in `deep.checked_and_dropped` with `file`, `line`, `title`, `area`, and the checker's `reason`.
  - **Confirmed and plausible candidates (`verdict in ("confirmed", "plausible")`):** included in `findings` with:
    - `verification_status`: `"confirmed"` or `"plausible"`
    - `verified`: `True` when `verdict == "confirmed"`, `False` when `verdict == "plausible"`
    - `evidence`: `"reproduced"` (when checker confirmed/reran a reproduction and supplied `repro_command` and `repro_output`) or `"read from code"`
    - `repro`: `{"command": str, "output": str}` when `evidence == "reproduced"`, omitted otherwise
    - `what_would_confirm`: non-empty string when `verification_status == "plausible"`
  - **Standard-lens `Nit` findings:** preserved with `evidence: "read from code"` and `verification_status: "confirmed"` unless a checker explicitly refuted them or a confirmed/plausible deep finding deduplicates at the same `file:line`.
  - **Deduplication:** findings at the same `file:line` (or sharing the same `dedup_key` / overlapping line range on the same defect) merge: keep the highest severity, prefer `"confirmed"` over `"plausible"`, prefer `"reproduced"` over `"read from code"`, and union `dimensions`.
  - **Coverage & budget:**
    - If `trust_info["execution_enabled"]` is `False`, appends the execution-off reason to `coverage_notes` (e.g., `"⚠ Deep repros disabled: the change author is not a trusted member of the repository"`).
    - If any area recorded `status == "read_only_degraded"`, appends `"⚠ Area <id> ran read-only: <degraded_reason>"` to `coverage_notes`.
    - If any area has `status == "unreached"`, sets `incomplete: True`, `verdict_override: "Incomplete review"`, lists the unreached area IDs in `deep.unreached_areas`, and appends `"⚠ Incomplete deep review: budget expired before reaching <areas>"` to `coverage_notes`.
- **Invariants:** No unchecked deep candidate or unchecked Must/Should lens finding ever appears in `findings`. There is no cap on the number of confirmed/plausible findings returned.
- **Errors:** Exits 2 with `{"error": "<message>"}` if any deep candidate or Must/Should lens finding lacks a checker verdict or if a `"reproduced"` verdict omits `repro_command` / `repro_output` or a `"plausible"` verdict omits `what_would_confirm`.

### 4. `score_deep_report.py` — answer-key recall and precision evaluator

Back-links: [Behavior & scenarios](logic.md#behavior--scenarios) (Scenario 9), [Success criteria](logic.md#success-criteria), [Decisions Locked](logic.md#decisions-locked).

`CONTRACT:`
```python
def match_defect(defect: dict, findings: list[dict]) -> dict | None: ...
def score_report(report: dict, answer_key: dict, spot_check: dict | None = None, budget_minutes: float = 60.0) -> dict: ...
```

`COMMAND:`
```bash
python3 "$SCRIPTS/score_deep_report.py" \
  --report "$REPORT_JSON" \
  --answer-key "$Q/tests/fixtures/full-code-review/answer-keys/pr50-3605fd8.json" \
  [--spot-check "$SPOT_CHECK_JSON"] \
  [--out "$SCORE_JSON"]
```

- **Preconditions:** `report` is a valid `report.json` dict; `answer_key` conforms to the answer-key schema below.
- **Postconditions:**
  - Evaluates each answer-key defect against `report["findings"]`. A defect is caught when a finding matches at least one of the defect's `anchors` (`file` equals anchor `file`, finding line range overlaps `[line_min, line_max]`, and if `keywords` are specified on the defect, at least one keyword matches case-insensitively in `title`, `issue`, `body_md`, or `recommendation_md`).
  - Computes `caught` (list of `{defect_id, title, finding_id, file, line}`), `missed` (list of `{defect_id, title, anchors}`), `recall` (`len(caught) / len(answer_key["defects"])`), and `refuted_share`:
    - When `--spot-check` is supplied (mapping finding IDs or `file:line` to `"confirmed" | "plausible" | "refuted"`), `refuted_share = refuted_count / max(1, len(report["findings"]))`.
    - Otherwise `refuted_share` is `0.0` (or computed from any finding marked refuted in spot-check metadata).
  - Sets `passed = (recall == 1.0 and refuted_share <= 0.20 and within_budget)`.
  - Prints the JSON score report to stdout (and writes `--out` if given). Exits 0 when `passed` is `True`, exits 1 when `passed` is `False`, exits 2 on invalid input.

- **Invariants:** Does not mutate `report`, `answer_key`, or `spot_check` inputs; deterministic for identical inputs.
- **Errors:** Exits 1 when `passed` is `False`; exits 2 with `{"error": "<message>"}` on stdout when any input file is missing, unreadable, or violates the report/answer-key schema.
## Data models / schemas

Back-links: [Data flow](logic.md#data-flow), [Behavior & scenarios](logic.md#behavior--scenarios), [Success criteria](logic.md#success-criteria), [Decisions Locked](logic.md#decisions-locked).

### Area map (`area-map.json` and `report.json` → `run.deep.areas`)

`SCHEMA:`
```json
{
  "schema_version": 1,
  "areas": [
    {
      "id": "A1",
      "title": "prepare_diff.py + forge/__init__.py",
      "files": [
        "skills/full-code-review/scripts/prepare_diff.py",
        "skills/full-code-review/scripts/forge/__init__.py"
      ],
      "test_files": [
        "tests/full_code_review/test_prepare_diff.py"
      ],
      "coupled_edges": [
        ["skills/full-code-review/scripts/prepare_diff.py", "skills/full-code-review/scripts/forge/__init__.py"]
      ],
      "lines": 1388,
      "questions": [
        "Do producer and consumer agree on git C-quoted paths in diff headers?"
      ],
      "status": "completed",
      "degraded_reason": null
    }
  ]
}
```

Allowed `status` values: `"pending"`, `"completed"`, `"read_only_degraded"`, `"unreached"`.

### Finder / Contract lens candidate output

`SCHEMA:`
```json
{
  "area": "A1",
  "execution_degraded_reason": null,
  "candidates": [
    {
      "id": "A1.1",
      "area": "A1",
      "dimension": "correctness",
      "file": "skills/full-code-review/assets/report.html",
      "line": "1922",
      "summary": "Triage export defangs the anchor path (< to &lt;) while validate_triage compares raw file:line",
      "failure_scenario": "A file path containing '<' exports as '&lt;' in the triage paste and fails validate_triage.py anchor comparison.",
      "reproduced": true,
      "repro_command": "python3 -c '...'",
      "repro_output": "ValueError: F1 anchor mismatch",
      "confidence": "high"
    }
  ]
}
```

### Checker verdict output

`SCHEMA:`
```json
{
  "id": "A1.1",
  "verdict": "confirmed",
  "severity": "Should fix",
  "evidence_tag": "reproduced",
  "repro_command": "python3 -c '...'",
  "repro_output": "ValueError: F1 anchor mismatch",
  "what_would_confirm": null,
  "reason": "Reran repro in fresh copy; report.html:1922 calls defang() on card.dataset.file while validate_triage.py:133 compares raw file:line.",
  "refined_file": "skills/full-code-review/assets/report.html",
  "refined_line": "1922",
  "refined_title": "Triage paste fails for a file whose name contains <",
  "refined_impact": "Any finding on a file path containing '<' makes the exported triage paste fail validation.",
  "refined_fix_md": "Leave the backticked anchor path raw in report.html export or decode '&lt;' in validate_triage.py.",
  "refined_issue": "report.html:1922 passes card.dataset.file through defang(), turning '<' into '&lt;', whereas validate_triage.py:133 compares against raw trusted['file'].",
  "refined_recommendation": "```diff\n--- a/skills/full-code-review/assets/report.html\n+++ b/skills/full-code-review/assets/report.html\n@@ -1920,3 +1920,3 @@\n-  lines.push(\"  `\" + defang(card.dataset.file) + \"` · \" + sev);\n+  lines.push(\"  `\" + card.dataset.file + \"` · \" + sev);\n```"
}
```

### `report.json` extensions (`run.deep` and finding fields)

`SCHEMA:`
```json
{
  "run": {
    "deep": {
      "enabled": true,
      "budget_minutes": 60,
      "elapsed_minutes": 28.4,
      "cutoff_reached": false,
      "execution_allowed": true,
      "execution_consent": true,
      "execution_disabled_reason": null,
      "sandbox_kind": "sandbox-exec",
      "copy_kind": "clonefile",
      "areas": [],
      "unreached_areas": [],
      "checked_and_dropped": [
        {
          "id": "A6.1",
          "area": "A6",
          "file": "skills/full-code-review/scripts/resolve_policy.py",
          "line": "322",
          "title": "Nested REVIEW.md files merge repo-wide",
          "reason": "Documented behavior in resolve_policy.py:5-6 and references/policy.md:16."
        }
      ]
    }
  },
  "findings": [
    {
      "severity": "Should fix",
      "dimension": "correctness",
      "dimensions": ["correctness"],
      "file": "skills/full-code-review/assets/report.html",
      "line": "1922",
      "title": "Triage paste fails for a file whose name contains <",
      "impact": "Any finding on a file path containing '<' makes the exported triage paste fail validation.",
      "fix_md": "Keep the anchor path raw in report.html or unescape '&lt;' in validate_triage.py.",
      "issue": "...",
      "recommendation": "...",
      "verified": true,
      "verification_status": "confirmed",
      "evidence": "reproduced",
      "repro": {
        "command": "python3 -c '...'",
        "output": "ValueError: F1 anchor mismatch"
      },
      "what_would_confirm": null,
      "assumptions": []
    }
  ]
}
```

### Answer-key fixture (`Q/tests/fixtures/full-code-review/answer-keys/pr50-3605fd8.json`)

`SCHEMA:`
```json
{
  "schema_version": 1,
  "target": {
    "project": "zpyoung/quirk",
    "number": 50,
    "head_sha": "3605fd8",
    "base_ref": "main"
  },
  "defects": [
    {
      "id": "AK-01",
      "title": "write_json crashes on diffs with non-UTF-8 source bytes",
      "source": "both",
      "source_ids": ["F3", "A1.1", "A5.1"],
      "severity": "Should fix",
      "anchors": [
        {"file": "skills/full-code-review/scripts/jsonio.py", "line_min": 1, "line_max": 30},
        {"file": "skills/full-code-review/scripts/prepare_diff.py", "line_min": 395, "line_max": 420},
        {"file": "skills/full-code-review/scripts/prepare_diff.py", "line_min": 1020, "line_max": 1055}
      ],
      "keywords": ["surrogate", "utf-8", "ensure_ascii", "write_json", "UnicodeEncodeError"],
      "verification_note": "Confirmed reproducible: surrogateescape diff bytes fail json.dumps(..., ensure_ascii=False).encode('utf-8')."
    }
  ],
  "examined_non_defects": [
    {
      "source_id": "B24",
      "file": "skills/full-code-review/scripts/resolve_policy.py",
      "line": 322,
      "disposition": "refuted",
      "reason": "Documented behavior in resolve_policy.py:5-6 and policy.md:16."
    }
  ]
}
```

The complete verified PR #50 at `3605fd8` answer key contains 19 confirmed `Should fix` defects (`AK-01` through `AK-19`: standard-run `F1`–`F6` from `pr50-r3/review-pr50-report.json`, built-in confirmed `B1`–`B10`, plus `B12` at `post_author_comments.py:53-75`, `B13` at `post_author_comments.py:85-102` / `comment_body.py:706-723`, and `B16` at `review_memory.py:649-652`), plus `examined_non_defects` recording `B11` (`plausible`), `B24` (`refuted`), and the remaining 46 `confirmed_nit` candidates (`B14`–`B15`, `B17`–`B23`, `B25`–`B61`).

## DO-NOT-CHANGE fences

Back-links: [Key decisions & rationale](logic.md#key-decisions--rationale), [Scope & non-goals](logic.md#scope--non-goals).

- `SK/references/lenses/*.md` (the 14 non-underscore lens files: `adversarial.md`, `comments.md`, `conventions.md`, `correctness.md`, `cross-repo.md`, `db.md`, `observability.md`, `resilience.md`, `risk.md`, `safety.md`, `scope.md`, `test-adequacy.md`, `test-coverage.md`, `tests.md`) — **DO NOT CHANGE.** Reason: `logic.md` locks that the standard run and its lenses are unchanged and never run code, and `Q/tests/full_code_review/test_full_code_review_skill.py:42-67` pins the exact 14-lens roster, front matter, and opening lines.
- `SK/scripts/highlight.py` lines 210–240 (`highlight` / `highlight_lines` span-stripping invariant) — **DO NOT CHANGE.** Reason: existing contract requires that stripping HTML spans reproduces `html.escape(source)`.
- `SK/scripts/forge/__init__.py`, `SK/scripts/forge/github.py`, `SK/scripts/forge/gitlab.py` — **DO NOT CHANGE.** Reason: forge boundary and posting transport are out of scope for deep mode (`logic.md#scope--non-goals`).
- `SK/scripts/validate_triage.py` (`parse_export`, `validate`, `validate_zero_findings`) — **DO NOT CHANGE.** Reason: refuted candidates never enter `report["findings"]`, and plausible findings are triaged normally on the HTML page and blocked at posting time (`comment_body.py`, `post_author_comments.py`, `post_reviewer_review.py`), so the triage paste grammar is unchanged.
- `SK/SKILL.md` line count — **MUST NOT EXCEED 500 LINES.** Reason: enforced by `Q/tests/full_code_review/test_full_code_review_skill.py:24-25`.
- `SK/references/report-template.md` top-level `## N. ...` headings outside code fences — **DO NOT CHANGE** from `[("1", "Summary"), ("2", "Risk Assessment"), ("3", "Findings"), ("4", "Assumptions"), ("5", "Recommendations")]`. Reason: enforced by `Q/tests/full_code_review/test_full_code_review_skill.py:69-75`.

## Always / Ask / Never

Back-links: [Decisions Locked](logic.md#decisions-locked), [Scope & non-goals](logic.md#scope--non-goals).

- **Always:**
  - Keep Python 3.9+ compatibility (`from __future__ import annotations` where type annotations use `|`, standard library only).
  - Resolve throwaway copy and environment paths with `os.path.realpath` before passing them to `sandbox-exec` or git commands.
  - Route every deep candidate and every standard-lens `Must fix` / `Should fix` finding through the checker before it can appear in `report["findings"]` in deep mode.
  - Block `verification_status == "plausible"` findings from posting in both author and reviewer seats.
  - Keep all files under `SK`, `Q/tests/full_code_review`, and `Q/tests/fixtures/full-code-review` free of forbidden org/plugin names enforced by `Q/tests/full_code_review/test_no_org_names.py`.
- **Ask:**
  - Ask the user once per deep run before executing code in throwaway copies when the seat and author trust allow execution. Never persist that consent across runs.
- **Never:**
  - Never prompt for execution consent or run code on a fork PR, an untrusted author's PR, a GitLab reviewer run (`author_trusted is None`), or a `diff-only` run.
  - Never expose real `gh` or `glab` binaries, user git hooks, user `~/.gitconfig`, or forge token env vars inside `deep_sandbox.py exec`.
  - Never run `git worktree prune` in the caller's repository when releasing a throwaway copy.
  - Never show raw, unchecked finder candidates when the time budget expires.

## Cross-cutting

Back-links: [Decisions Locked](logic.md#decisions-locked), [Industry Insights](logic.md#industry-insights).

- **Security & sandbox isolation:**
  - `deep_sandbox.py` disables git hooks (`core.hooksPath=/dev/null`, `core.fsmonitor=false`, removal of `.git/hooks/*` in cloned copies) and isolates `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`, and `TMPDIR` to a per-copy directory.
  - Stub `gh` and `glab` scripts at the front of `PATH` exit 127 immediately, and `GH_TOKEN`, `GITHUB_TOKEN`, `GLAB_TOKEN`, `GITLAB_TOKEN`, `SSH_AUTH_SOCK`, and `GIT_ASKPASS` are stripped from the environment.
  - On macOS, `sandbox-exec` denies `file-write*` everywhere except the canonicalized `copy_dir`, `env_dir`, and `/dev/{null,zero,random,urandom,tty}`, while allowing network (`(allow network*)`) as locked in `logic.md`.
- **Time budget & 80% cutoff:**
  - `deep.md` and `merge_deep_findings.py` track `budget_minutes` (default 60) and `cutoff_minutes = 0.8 * budget_minutes`. Once elapsed time reaches `cutoff_minutes`, no new area finders are dispatched; areas still `pending` are marked `unreached`, in-flight finders finish, all collected candidates are checked by `_checker.md`, and the resulting report is marked `run.incomplete = True` with `meta.verdict = "Incomplete review"` and the unreached areas named in `run.coverage`.
- **Rollback & cleanup:**
  - Every `deep_sandbox.py acquire` manifest is registered in `$REVIEW_RUN_DIR` and released as soon as its finder/checker exits, with a sweep in the coordinator's `finally` block releasing any remaining `copy-*.json` manifests.

## Testing strategy

Back-links: [Behavior & scenarios](logic.md#behavior--scenarios), [Success criteria](logic.md#success-criteria).

- `Q/tests/full_code_review/test_deep_sandbox.py`:
  - Unit and integration tests covering `check-trust` across author seat, trusted same-repo GitHub reviewer seat (Scenario 2), fork PR / untrusted author / GitLab reviewer seat (`author_trusted: None`) / `diff-only` (Scenario 3).
  - Throwaway copy lifecycle (`acquire`, `exec`, `release`) verifying: `source_root` stays untouched, `gh` and `glab` fail with exit 127 inside `exec`, `HOME`/`XDG_*` point inside `env_dir`, forge tokens are stripped, git hooks in `source_root` do not execute, writes outside `copy_dir`/`env_dir` are denied when `sandbox-exec` or `bwrap` is active, and missing-dependency commands return `environment_unavailable` / non-zero cleanly without aborting (Scenario 4).
- `Q/tests/full_code_review/test_build_area_map.py`:
  - Verifies producer/consumer coupling keeps coupled files (such as `assets/report.html` and `scripts/validate_triage.py`, or `scripts/prepare_diff.py` and `scripts/forge/__init__.py`) in the same area when within size bounds, splits areas when exceeding `max_lines` / `max_files`, covers every changed file exactly once, and attaches hotspot questions.
- `Q/tests/full_code_review/test_merge_deep_findings.py`:
  - Verifies confirmed candidates (`reproduced` with command/output and `read from code`), plausible candidates (with `what_would_confirm`), refuted candidates routed to `run.deep.checked_and_dropped` and excluded from `findings` (Scenario 6), standard-lens Must/Should findings checked and dropped when refuted by the checker, deduplication across area finders / contract lens / standard lenses, and budget cutoff marking unreached areas with `run.incomplete = True` and `meta.verdict = "Incomplete review"` (Scenario 5).
- `Q/tests/full_code_review/test_render_report.py` & `Q/tests/full_code_review/test_render_contract.py` & `Q/tests/full_code_review/test_post_author_comments.py` & `Q/tests/full_code_review/test_post_reviewer_review.py` & `Q/tests/full_code_review/test_comment_body.py`:
  - Verifies HTML and Markdown rendering of `evidence` tags (`reproduced`, `read from code`), `repro` command/output block, `plausible` badge and `what_would_confirm`, `run.deep.areas` in "What was run" / Summary, and collapsed `<details>` for `checked_and_dropped`.
  - Verifies that `verification_status: "plausible"` findings never get `post: true` in `comment_body.py`, are skipped by `post_author_comments.py` even when explicitly requested via `--ids`, and are omitted by `post_reviewer_review.py stage` even when triaged as `Blocking` (`fix`) (Scenario 7).
- `Q/tests/full_code_review/test_score_deep_report.py`:
  - Verifies `score_deep_report.py` against `Q/tests/fixtures/full-code-review/answer-keys/pr50-3605fd8.json`, testing 100% recall pass, partial recall fail (exit 1), spot-check `refuted_share > 0.20` fail (exit 1), and budget exceeded fail (Scenario 9).
- **Acceptance bar:**
  - `python3 -m pytest tests/full_code_review -q` passes 100% (including `test_full_code_review_skill.py` and `test_no_org_names.py`).
  - `/usr/local/bin/python3.9 -m pytest tests/full_code_review -q` passes 100% when Python 3.9 is present.
  - Two deep-mode evaluation runs of PR #50 at `3605fd8` each complete within the 60-minute budget, achieve 100% recall (`recall == 1.0`) on `tests/fixtures/full-code-review/answer-keys/pr50-3605fd8.json` via `score_deep_report.py`, and have `refuted_share <= 0.20` on spot check.

## Non-goals

Back-links: [Scope & non-goals](logic.md#scope--non-goals), [Deferred Ideas](logic.md#deferred-ideas).

- Modifying any of the 14 standard lens checklists or allowing standard lenses to execute code.
- Adding cleanup angles (reuse, simplification, efficiency) to deep mode.
- Enabling deep mode via `pack.yaml` or `REVIEW.md` policy keys or auto-enabling it from risk level.
- Running repros for fork PRs, untrusted authors, GitLab reviewer runs, or `diff-only` runs.
- Changing the Step 2 size gate thresholds or behavior (`logic.md` Scenario 8).
- Allowing plausible findings to be posted to GitHub or GitLab.
