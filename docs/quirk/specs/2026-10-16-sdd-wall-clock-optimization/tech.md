# Cutting SDD Wall-Clock Time — Tech Spec

**Status:** Approved · **Logic spec:** [logic.md](logic.md)

## Architecture

Back-links: [logic.md#purpose](logic.md#purpose), [logic.md#conceptual-model](logic.md#conceptual-model), [logic.md#data-flow](logic.md#data-flow), [logic.md#key-decisions--rationale](logic.md#key-decisions--rationale)

The implementation spans one deterministic Python CLI (`skills/adversarial-review/scripts/adversarial-review`, Python 3.9+ standard library only) and three markdown skill definitions (`skills/adversarial-review/`, `skills/subagent-driven-development/`, and `skills/writing-plans/`), validated by pytest suites in `tests/test_adversarial_review.py` (276 existing tests) and `tests/test_adversarial_review_skill.py` (79 existing tests).

1. **Deterministic review CLI (`skills/adversarial-review/scripts/adversarial-review`)**:
   - **Default diff hygiene (`resolve_target`, `read_diff`, `untracked_paths`, `untracked_diff`, `artifact_hash_of`, `unreviewed_since_capture`, `verify_artifact_is_current`, `run_gate`, `build_manifest`)**: Filters out vendored, generated, and lockfile paths by default using `DEFAULT_EXCLUDE_DIRS` and `DEFAULT_EXCLUDE_PATTERNS` via `is_excluded_path` (new function) and `collect_excluded_paths` (new function), unless `--include-all` is passed to `resolve`. Uses `-z` path enumeration (`git diff --numstat -z` / `git ls-files -z`) in `collect_excluded_paths` and a fixed-size list of `:(exclude,glob)` pathspecs built from `DEFAULT_EXCLUDE_DIRS` and `DEFAULT_EXCLUDE_PATTERNS` in `read_diff` so paths with spaces or non-ASCII characters are handled without C-quoting bugs and large vendored trees never hit `ARG_MAX`. Records excluded entries with line stats (`"<path> (<N> lines)"`) in `ResolveResult.excluded_paths`, persists `include_all` in `ResolveResult` so every downstream stage re-derives the identical `artifact_hash` and `unreviewed_paths`, and propagates `excluded_paths` into `GateResult`, `manifest.json`, and `SCOPE_BOUNDING_FIELDS`.
   - **Verified pre-pass check reuse (`run_check`, `run_prepass`, `verify_reused_checks` [new function], `current_tree_hash` [new function], `build_manifest`)**: `run_check` records `duration_ms` and `reused: False`. `prepass` accepts `--reuse-check <path>` (only for `--profile code-diff`) pointing to a JSON check record. `run_prepass` receives `resolved` from `main` and calls `verify_reused_checks` to verify `tree_hash == current_tree_hash(repo_root)`, `clean_tree` boolean agreement, `status`/`exit_code` consistency on every check, complete coverage of expected commands, and (on worktree targets) `full_worktree_hash` agreement over the unfiltered (`include_all=True`) worktree diff before emitting `PrepassResult` with `reused: True` on each check and `tree_hash` at the top level. `build_manifest` preserves `tree_hash` on `manifest.prepass` and `reused` + `duration_ms` on `manifest.prepass.checks[]`.
   - **Diff hunk excerpts for stage-2 and stage-3 prompts (`build_claims`, `run_gate`, `extract_diff_excerpts` [new function])**: Extracts matching diff hunks (plus a `±15`-line window around 1-based new-side line refs) for `evidence[]` and `counter_evidence[]` items whose `kind in ("file-line", "quote", "absence")` and `ref` matches `<path>:<start>[-<end>]`. `build_claims` emits `diff_excerpts` and `excluded_paths` in `claims.json` (staged into `refute-prompt.md`'s `{{ARTIFACT}}`), and `run_gate` emits `contested_excerpts` in `gate.json` when `contested[]` is non-empty (staged into `tiebreak-prompt.md`'s `{{ARTIFACT}}`).
2. **Adversarial review protocol (`skills/adversarial-review/`)**:
   - Updates `SKILL.md`, `profiles/code-diff.md`, `assets/promote-prompt.md`, `assets/refute-prompt.md`, `assets/tiebreak-prompt.md`, and `assets/composition-contract.md` to document shared `resolve.json`/`prepass.json` across concurrent lenses, `--reuse-check`, the `excluded_paths` scope-bounding decision row, excerpted `{{ARTIFACT}}` staging in refute and tiebreak, the ban on running the full test suite when `prepass.status == "pass"`, per-lens closure-round verification over `LAST_ROUND_HEAD..HEAD` (`## Running rounds`), and per-stage effort (`high` for promote and refute, `medium` for tiebreak, capped by the model's `ALIAS_LADDER` thinking ceiling).
3. **SDD control plane (`skills/subagent-driven-development/`)**:
   - Updates `SKILL.md`, `assets/implementer-prompt.md`, and `assets/fixer-prompt.md` to specify the single-card preflight (preserving `task-fallback` when no alias resolves), the orchestrator-recorded `tree_test_cache` keyed by `(tree_identity, exact_command)`, the three-tier human gate protocol (with `orca ask` status handling and synchronous `AskUserQuestion` fallback when no Orca UI is attached), `--depth standard` wave checkpoints, closure-mode final rounds 2–5 with per-lens prefix filtering of prior accepted findings, recurring-defect escalation after 2 failed fixes in the same category and seam, auto-dispatched wave-gate test fixers for unowned pre-wave test assertions, the `>300s` (5-minute) slow-suite advisory on both wave-gate and pre-pass runs, and explicit role effort pins.
4. **In-context planning rubric (`skills/writing-plans/`)**:
   - Updates `SKILL.md` to enforce single-owner test-file assignment within each wave, task-scoped `Acceptance` commands (with full-suite execution reserved for Step 7's wave gate), and explicit alignment of `## After the plan: agent review, then execute` with SDD's inline decomposition carve-out while keeping `executing-plans`'s plan-document reviewer dispatch intact.

## Code references

Back-links: [logic.md#scope--non-goals](logic.md#scope--non-goals), [logic.md#decisions-locked](logic.md#decisions-locked)

- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/adversarial-review/scripts/adversarial-review`
  - Existing constants: `EMPTY_TREE` (`:39`), `CODE_CHECK_DISCOVERY` (`:391-395`), `ALIAS_LADDER` (`:853-860`), `CHAIN_PREDECESSOR` (`:991-997`), `SCOPE_BOUNDING_FIELDS` (`:1071-1082`), `CLAIM_FIELDS` (`:1741`).
  - New constants (near `:45`): `DEFAULT_EXCLUDE_DIRS`, `DEFAULT_EXCLUDE_PATTERNS`, `EXCERPT_FALLBACK_MAX_LINES = 200`, `EXCERPT_CONTEXT_LINES = 15`.
  - Existing functions to modify: `read_diff` (`:116-155`), `untracked_paths` (`:157-182`), `untracked_diff` (`:184-226`), `artifact_hash_of` (`:306-328`), `resolve_target` (`:331-383`), `discover_code_checks` (`:418-421`), `run_check` (`:424-435`), `run_prepass` (`:771-841`), `unreviewed_since_capture` (`:1344-1363`), `verify_artifact_is_current` (`:1366-1394`), `run_gate` (`:1397-1692`), `build_claims` (`:1744-1784`), `build_manifest` (`:1917-2039`), `build_parser` (`:2044-2141`), `main` (`:2144-2200`).
  - New helper functions to add: `is_excluded_path` (near `:115`), `collect_excluded_paths` (near `:155`), `current_tree_hash` (near `:436`), `verify_reused_checks` (near `:450`), `extract_diff_excerpts` (near `:1744`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/adversarial-review/SKILL.md`
  - `## Data flow` (`:58-262`), `## Depth` (`:264-279`), `## Verdict contract` (`:296-324`), `## Dispatch` (`:358-397`), `## Running rounds` (`:407-440`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/adversarial-review/profiles/code-diff.md`
  - `# Profile — \`code-diff\`` (`:1-14`), `## Evidence rules` (`:62-88`), `## Pre-pass context` (`:89-101`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/adversarial-review/assets/promote-prompt.md`
  - Stage placeholders & instructions (`:1-16`), `## Ground truth — already established, do not re-derive` (`:41-49`), `## Tools` (`:78-87`), `## Output` (`:88-120`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/adversarial-review/assets/refute-prompt.md`
  - Stage placeholders (`:1-20`), `## The artifact` (`:66-79`), `## Tools` (`:84-92`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/adversarial-review/assets/tiebreak-prompt.md`
  - Stage placeholders (`:1-15`), `## The artifact` (`:54-66`), `## Tools` (`:71-81`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/adversarial-review/assets/composition-contract.md`
  - `## Input` (`:6-97`), `## Output` (`:98-147`), `### Distinguishing a clean review from a crashed one` (`:202-238`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/subagent-driven-development/SKILL.md`
  - `## Roles` (`:40-54`), `### Step 1: Preflight` (`:83-134`), `### Step 3: Decompose inline` (`:144-189`), `### Step 5: Dispatch` (`:262-331`), `### Step 6: Audit, accept, commit, merge` (`:332-487`), `### Step 7: Gates` (`:488-505`), `### Step 8: Review` (`:506-583`), `### Step 9: Adjudicate and fix` (`:584-636`), `### Step 10: Exit` (`:637-655`), `## Failure routing` (`:656-700`), `## Red Flags` (`:701-753`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/subagent-driven-development/assets/implementer-prompt.md` (`:53-61`) and `fixer-prompt.md` (`:41-47`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/skills/writing-plans/SKILL.md`
  - `## File Structure` (`:95-120`), `## Task Independence` (`:132-150`), `## Task Structure` (`:183-251`), `## Self-Review` (`:275-296`), `## After the plan: agent review, then execute` (`:297-308`).
- `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/tests/test_adversarial_review.py` and `/Users/zpyoung/orca/workspaces/quirk/optimize-sdd/tests/test_adversarial_review_skill.py`.

## Contracts & interfaces

Back-links: [logic.md#tree-once-caching-and-review-staging-hygiene](logic.md#tree-once-caching-and-review-staging-hygiene), [logic.md#three-tier-human-gates-preflight-consolidation-and-adjudication-digests](logic.md#three-tier-human-gates-preflight-consolidation-and-adjudication-digests), [logic.md#stage-sized-checkpoints-closure-rounds-and-recurring-defect-escalation](logic.md#stage-sized-checkpoints-closure-rounds-and-recurring-defect-escalation), [logic.md#plan-time-test-topology-slow-suite-guardrails-and-role-effort](logic.md#plan-time-test-topology-slow-suite-guardrails-and-role-effort)

### 1. Default diff hygiene and `--include-all` in `scripts/adversarial-review`

- **Preconditions**: `resolve` is called with `--target` (git range, empty/`WORKTREE`, or file path) and optional `--include-all` flag (default `False`).
- **Postconditions**:
  - `is_excluded_path(rel_path, include_all)` normalizes `rel_path` with `PurePosixPath(rel_path)`. When `include_all` is `True`, it returns `False`. Otherwise it returns `True` if any directory component in `parts[:-1]` is in `DEFAULT_EXCLUDE_DIRS` (`{"vendor", "node_modules", "dist", "build", ".venv", "__pycache__"}`) or if `fnmatch.fnmatchcase(parts[-1], pat)` matches any pattern in `DEFAULT_EXCLUDE_PATTERNS` (`("*.min.js", "*.min.css", "*.bundle.js", "*.lock", "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "Cargo.lock", "poetry.lock", "uv.lock")`).
  - When `target_kind in ("git-range", "worktree")` and `diff_file is None`:
    - `collect_excluded_paths(target, repo_root, diff_file, untracked_only, include_all)` uses `git --no-pager diff --numstat -z --no-renames [target | HEAD | EMPTY_TREE]` to enumerate changed tracked paths without C-quoting, filters for `is_excluded_path(path, include_all)`, sums `added + deleted` lines per excluded path (using `0` for binary `-` entries), and for `worktree` targets also checks `untracked_paths(repo_root, include_all=True)` for excluded untracked files (counting lines via `read_bytes().splitlines()`). It returns sorted strings formatted as `"<path> (<N> lines)"`.
    - `read_diff` appends `-- .` followed by a fixed-size list of `:(exclude,glob)<dir>/**` and `:(exclude,glob)**/<dir>/**` for each `<dir>` in `DEFAULT_EXCLUDE_DIRS`, plus `:(exclude,glob)<pat>` and `:(exclude,glob)**/<pat>` for each `<pat>` in `DEFAULT_EXCLUDE_PATTERNS` when `include_all` is `False`, so git omits excluded files with a bounded argument vector (never hitting `ARG_MAX` on large vendored trees) and without fragile header splitting on spaces or quotes; `untracked_diff` skips untracked paths where `is_excluded_path(p, include_all)` is `True`.
    - For `target_kind == "worktree"`, `ResolveResult.untracked_paths` records only non-excluded untracked paths (`untracked_paths(repo_root, include_all=include_all)`), and `ResolveResult.full_worktree_hash` records `artifact_hash_of(target, repo_root, diff_file, untracked_only=untracked_paths(repo_root, include_all=True), include_all=True)` so callers and `verify_reused_checks` have the unfiltered worktree hash directly from `resolve.json`.
    - `unreviewed_since_capture(resolved, repo_root)` compares `set(untracked_paths(repo_root, include_all=bool(resolved.get("include_all", False))))` against `set(resolved.get("untracked_paths") or [])`, so excluded untracked files never trigger false `unreviewed_paths` warnings.
    - `verify_artifact_is_current(resolved, repo_root)` and `run_prepass` pass `include_all=bool(resolved.get("include_all", False))` into `artifact_hash_of`.
  - `ResolveResult`, `GateResult` (`run_gate`), and the replay manifest (`build_manifest`) all carry `"excluded_paths": list[str]`. `"excluded_paths"` is added to `SCOPE_BOUNDING_FIELDS` (`:1071`), and a decision row `any exit + excluded_paths nonempty ->` is added to `composition-contract.md`'s `"Distinguishing a clean review from a crashed one"` block, `skills/adversarial-review/SKILL.md`, and SDD Step 8's signal table.
- **Invariants**: `size_metric`, `depth_suggestion`, and `artifact_hash` are computed over the filtered diff when `include_all` is `False`, and every stage re-derives the hash with the same `include_all` setting from `resolve.json`.
- **Errors**: Invalid git ranges or unreadable files raise `UsageError` (exit 2).

`CONTRACT:`
```python
DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset({
    "vendor", "node_modules", "dist", "build", ".venv", "__pycache__",
})
DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    "*.min.js", "*.min.css", "*.bundle.js",
    "*.lock", "pnpm-lock.yaml", "package-lock.json",
    "yarn.lock", "Cargo.lock", "poetry.lock", "uv.lock",
)

def is_excluded_path(rel_path: str, include_all: bool = False) -> bool: ...  # new function
def untracked_paths(repo_root: Path, include_all: bool = True) -> list[str]: ...
def collect_excluded_paths(
    target: str, repo_root: Path, diff_file: str | None,
    untracked_only: list[str] | None = None, include_all: bool = False,
) -> list[str]: ...  # new function
def read_diff(
    target: str, repo_root: Path, diff_file: str | None,
    untracked_only: list[str] | None = None, include_all: bool = False,
) -> str: ...
def untracked_diff(
    repo_root: Path, only: list[str] | None = None, include_all: bool = False,
) -> str: ...
def artifact_hash_of(
    target: str, repo_root: Path, diff_file: str | None, diff: str | None = None,
    untracked_only: list[str] | None = None, include_all: bool = False,
) -> str: ...
def resolve_target(
    target: str, profile: str | None, repo_root: Path, diff_file: str | None,
    include_all: bool = False,
) -> dict[str, Any]: ...
```

### 2. Verified pre-pass check reuse (`--reuse-check`) and shared `prepass.json`

- **Preconditions**: `prepass` is called with `--profile <profile>`, `--resolve <resolve.json>`, and optional `--reuse-check <check-record.json>`. `main` loads `resolved = load_json(args.resolve, "resolve")` and passes `resolved=resolved` and `reuse_check_path=args.reuse_check` to `run_prepass`.
- **Postconditions**:
  - `run_check(command, repo_root)` measures elapsed wall time via `time.monotonic()` and returns `{"name": "code-check", "command": command, "exit_code": int, "status": "pass" | "fail", "output": str, "duration_ms": int, "reused": False}`.
  - When `--reuse-check` is omitted, `run_prepass` runs discovered or `--check-cmd` checks as before and includes `"tree_hash": current_tree_hash(repo_root)` on `PrepassResult`.
  - When `reuse_check_path` is passed:
    1. If `profile != "code-diff"`, `run_prepass` raises `UsageError("--reuse-check is only supported for profile code-diff")` (exit 2).
    2. `verify_reused_checks(reuse_path, repo_root, expected_commands, resolved)` loads the JSON object from `reuse_path` and validates:
       - `record.get("tree_hash")` is a non-empty string equal to `current_tree_hash(repo_root)` (`git rev-parse HEAD^{tree}`).
       - `isinstance(record.get("clean_tree"), bool)` is `True` (no missing-key default).
       - For `resolved.get("target_kind") == "git-range"`, `record["clean_tree"]` must be `True` and `git status --porcelain --untracked-files=no` in `repo_root` must be empty (tracked files clean, so untracked test artifacts like `.pytest_cache` do not invalidate a committed-range check).
       - For `resolved.get("target_kind") == "worktree"`, `record.get("full_worktree_hash")` must be a non-empty string equal to `artifact_hash_of(target, repo_root, diff_file, untracked_only=untracked_paths(repo_root, include_all=True), include_all=True)` — the unfiltered hash over all tracked and untracked changes including lockfiles and vendored files, so editing an excluded file like `Cargo.lock` or `package-lock.json` invalidates the cached test record.
       - `record.get("checks")` is a non-empty list of dicts. For each check, `isinstance(check.get("exit_code"), int)` (and not `bool`), `check.get("status")` is `"pass"` if and only if `exit_code == 0` (and `"fail"` if and only if `exit_code != 0`), `isinstance(check.get("output"), str)`, and `isinstance(check.get("duration_ms", 0), int)` with `duration_ms >= 0`.
       - Every command in `expected_commands` (`discover_code_checks(repo_root, check_cmds)`) appears in `record["checks"]` by exact `command` string.
    3. `run_prepass` computes `observed_artifact_hash` from the live target, builds `checks` in the order of `expected_commands` with `"reused": True` stamped on each check, runs the existing `failed_check_finding` loop so any reused failing check still emits a `stage: "prepass"` finding and exits 1, and returns `PrepassResult` with `"tree_hash": current_tree_hash(repo_root)`.
  - `build_manifest` (`:2017-2023`) records `"tree_hash": prepass.get("tree_hash")` on `manifest["prepass"]` and copies `("name", "command", "exit_code", "status", "reused", "duration_ms")` for each check in `manifest["prepass"]["checks"]`.
  - All three concurrent lenses in a round (`C`, `S`, `X`) may share one `resolve.json` and one `prepass.json`, each passing its own `--id-prefix` (`C`, `S`, `X`) to `claims` and `gate`.
- **Invariants**: `observed_artifact_hash` is always computed live during `prepass` and verified against `resolve.json` by `run_gate`. A failing reused check exits 1 and produces a `failing-check` finding identically to a live failing check.
- **Errors**: Any validation failure in `verify_reused_checks` raises `UsageError` (exit 2) naming the specific field or hash mismatch.

`CONTRACT:`
```python
def current_tree_hash(repo_root: Path) -> str | None: ...  # new function
def verify_reused_checks(
    reuse_path: str, repo_root: Path, expected_commands: list[str],
    resolved: dict[str, Any] | None,
) -> list[dict[str, Any]]: ...  # new function
def run_prepass(
    profile: str, target: str, repo_root: Path, check_cmds: list[str],
    diff_file: str | None = None, untracked_only: list[str] | None = None,
    include_all: bool = False, reuse_check_path: str | None = None,
    resolved: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]: ...
```

### 3. Diff hunk excerpts in `claims` (`diff_excerpts`) and `gate` (`contested_excerpts`)

- **Preconditions**:
  - `claims` is called with `--findings <findings.json>`, `--resolve <resolve.json>`, `--id-prefix <prefix>`, and optional `--repo-root <path>` (default `"."`).
  - `gate` is called with its existing arguments (`--findings`, `--model`, `--prepass`, `--resolve`, `--depth`, `--repo-root`).
- **Postconditions**:
  - `extract_diff_excerpts(findings, resolved, repo_root)` inspects `evidence[]` and `counter_evidence[]` on every finding in `findings` for items with `kind in ("file-line", "quote", "absence")` whose `ref` matches `<path>:<start>[-<end>]` (1-based line numbers on the new/post-change side of the file).
  - If `resolved.get("size_metric", 0) <= EXCERPT_FALLBACK_MAX_LINES` (200) or no `<path>:<start>[-<end>]` references exist on `findings`, `extract_diff_excerpts` returns the full resolved artifact text (filtered diff or path content).
  - Otherwise, for each cited `(path, start, end)`, it extracts any overlapping diff hunk from the resolved diff plus a `±15`-line (`EXCERPT_CONTEXT_LINES`) numbered window from `repo_root / path` when the file exists on disk, deduplicated in file order. If `resolved.get("excluded_paths")` is non-empty, it prepends a comment header `# Excluded by default diff hygiene: <comma-separated excluded_paths>`.
  - `build_claims` adds `"diff_excerpts": extract_diff_excerpts(judged, resolved, repo_root)` and `"excluded_paths": resolved.get("excluded_paths", [])` to `claims.json`.
  - `run_gate` adds `"excluded_paths": (resolved.get("excluded_paths", []) if isinstance(resolved, dict) else [])` to `gate.json`, and when `contested` is non-empty and `isinstance(resolved, dict)`, adds `"contested_excerpts": extract_diff_excerpts(contested, resolved, repo_root)` to `gate.json`.
  - In `assets/refute-prompt.md` (`:3, :76`) and `assets/tiebreak-prompt.md` (`:3, :63`), the placeholder name remains `{{ARTIFACT}}`, and the staging instructions specify substituting `claims.json`'s `.diff_excerpts` into `{{ARTIFACT}}` for refute and `gate.json`'s `.contested_excerpts` into `{{ARTIFACT}}` for tiebreak (with full files accessible via `read`).
- **Invariants**: `CLAIM_FIELDS` is unchanged; `merge_judgments` and `run_gate` continue to validate chains identically.
- **Errors**: Unreadable or malformed `resolve` or `findings` JSON raises `UsageError` (exit 2).

`CONTRACT:`
```python
def extract_diff_excerpts(
    findings: list[dict[str, Any]],
    resolved: dict[str, Any] | None,
    repo_root: Path,
) -> str: ...  # new function
def build_claims(
    findings_path: str, resolve_path: str, id_prefix: str = "F",
    repo_root: Path = Path("."),
) -> dict[str, Any]: ...
```

### 4. Protocol Contracts Across `subagent-driven-development`, `adversarial-review`, and `writing-plans`

- **Preconditions**: SDD is invoked on a feature branch with an approved spec, or `adversarial-review` / `writing-plans` is invoked standalone or in-context.
- **Postconditions**:
  1. **Consolidated 1-card preflight (`skills/subagent-driven-development/SKILL.md:83-134`)**:
     - Preflight runs `git rev-parse --abbrev-ref HEAD`, `git status --porcelain`, and `pi-watch --check <alias>` in a temporary scratch directory across all 6 aliases (`codex, gemini, terra, opus, sonnet, flash`) before prompting the user.
     - Because `orca ask` specs are flat (non-branching), preflight encodes backend selection as a single `backend_pairing` question whose options are pre-verified `(IMPLEMENTER, REVIEWER_ALIAS)` pairs, ordered with cross-family full-independence pairs first (`claude-task + codex (Recommended)`, `claude-task + gemini`, `claude-task + terra`, `pi-codex + opus`, `pi-codex + gemini`) followed by same-family pairs labeled `(reduced independence)`. If **no** reviewer alias resolves via `pi-watch --check`, preflight warns once and records `REVIEWER_ALIAS = "task-fallback"` (`Agent` path, `independence: "reduced"`), preserving the existing fallback contract (`:123-125`).
     - If `git status --porcelain` is non-empty, the same preflight card includes `dirty_tree_action` with three options: `stash_untracked` (`git stash push --include-untracked` before recording `RUN_BASE`), `commit_existing` (commit the pre-existing changes on the branch before recording `RUN_BASE`), or `abort` (stop the run). If `stash_untracked` or `commit_existing` is chosen, the orchestrator executes it and re-verifies `git status --porcelain` is empty before recording `RUN_BASE`. The Never rule (`:739`) is updated to: *"Never start wave dispatch on a dirty tree; resolve dirty state at preflight before recording `RUN_BASE`."*
     - If `discover_code_checks` finds no runnable test runner or a preflight environment probe fails, the same preflight card includes `env_readiness` asking how to run checks or abort.
  2. **Three-tier human gate & `orca ask` status handling (`skills/subagent-driven-development/SKILL.md` Steps 1, 7, 8, 9, 10, Failure routing)**:
     - **Tool selection**: Use `orca ask` when running inside an Orca session (`ORCA_PANE_KEY` or `ORCA_WORKSPACE_ID` set). If `orca ask` returns `status: "unavailable"` or the `orca` CLI is not installed, fall back to `AskUserQuestion` (under `AskUserQuestion`, Tier 2 blocks synchronously since `AskUserQuestion` has no timeout parameter; Tier 3 adjudications still log without asking).
     - **Tier 1 (blocking, no `--timeout-ms`)**: Consolidated preflight card, and Step 10 blocked handoff when the 5-round cap is reached with an open `CRITICAL` or `HIGH` finding or when a component chain fails twice with no safe default. On `status: "declined"` for a Tier 1 card, stop the run cleanly without re-asking. On `status: "partial"`, re-ask the skipped required question once.
     - **Tier 2 (10-minute deadline, `orca ask --timeout-ms 600000` with explicit recommended `default`)**: Used for:
       - `NEEDS_CONTEXT` not derivable from the spec or codebase,
       - Mid-wave scope-violation re-planning splits,
       - Wave-gate test failures that expose a contract conflict rather than a stale pre-wave test assertion,
       - Reviewer `kind: "question"` items from `GateResult.questions[]`,
       - Recurring-defect escalations after two failed fixer rounds in the same category and seam.
       While a Tier 2 card is open, the orchestrator continues advancing unblocked components and polls `orca ask wait` across chunks without ever ending its turn. On `status: "timed_out"`, `status: "partial"` (question in `skipped[]`), or `status: "declined"`, the orchestrator resolves the question to its declared recommended `default` and records `<question_id>: <default_value> (assumed, <status>)` in the run journal.
     - **Tier 3 (logged adjudication digest, 0 wait)**: Step 9 adjudicates findings immediately against the contract and `GateResult`, records rulings in the run journal, prints a compact per-round table (`ID | Lens | Effective Severity | Ruling | One-line Reason`), and dispatches fixers immediately without asking. If the user sends a message vetoing a dismissal, regrade, or fix at any point, the orchestrator queues a follow-up fix task into the next batch without aborting in-flight workers.
  3. **Orchestrator-verified `tree_test_cache` and Step 7 → Step 8 reuse (`skills/subagent-driven-development/SKILL.md` Steps 6, 7, 8)**:
     - Define `worktree_tree_identity(WT, WAVE_BASE)` as `(git -C "$WT" rev-parse HEAD^{tree}, sha256(canonical_json(CHAIN_SNAPSHOT_AFTER)))`, where `CHAIN_SNAPSHOT_AFTER` is the recomputed `(mode, blob)` map Step 6 builds after the task returns (`:382`). For a clean committed tree (Step 7 wave gate), `tree_identity` is `(git rev-parse HEAD^{tree}, "clean")`.
     - `tree_test_cache` in the run journal is populated **only** by commands the orchestrator itself executed (or `adversarial-review prepass`), never from a worker's text claim alone, preserving `"a claim never overrides a run"` (`:672`, `:734`).
     - At Step 6, the orchestrator checks `tree_test_cache` for `(worktree_tree_identity, acceptance_cmd)`. On a miss, it runs the task's narrow acceptance command once and stores the result; on a hit (for example, re-evaluating an unchanged tree), it reuses the green entry.
     - At Step 7, the orchestrator checks `tree_test_cache` for `((HEAD^{tree}, "clean"), full_suite_cmd)`. On a miss, it runs the full build and test suite once, stores the result in `tree_test_cache`, and writes `$WORK/gate-check.json` in `ReusedCheckInput` format.
     - At Step 8, the orchestrator runs `adversarial-review resolve` once and `adversarial-review prepass` once passing `--check-cmd "$FULL_SUITE_CMD" --reuse-check "$WORK/gate-check.json"`. If `prepass --reuse-check` exits 2 (for example, because a non-ignored file dirtied tracked state), the orchestrator logs the reuse miss and immediately re-runs `prepass` without `--reuse-check`. All three lenses (`C`, `S`, `X`) share that single `resolve.json` and `prepass.json`.
  4. **Slow-suite advisory (`>300s`) and auto-dispatched wave-gate test fixer (`skills/subagent-driven-development/SKILL.md` Steps 7, 8)**:
     - Whenever Step 7's full-suite run or Step 8's `prepass` (`checks[].duration_ms > 300000`) exceeds 300 seconds (5 minutes), the orchestrator records a slow-suite advisory in the run journal and final summary recommending `pytest-xdist` (`-n auto`) and Playwright `BrowserContext` reuse per worker, without modifying target-repo config mid-run.
     - If Step 7 fails solely because an unowned test file outside the wave's `scope.files` asserts pre-wave behavior that the wave's contract intentionally replaced, the orchestrator automatically dispatches a scoped wave-gate fixer (`effort: "high"`) with that test file in `scope.files`, runs Step 6's audit/commit gate on the fixer, and re-runs Step 7. If the failure instead reveals a contract conflict, the orchestrator raises a Tier 2 `orca ask` (`--timeout-ms 600000`).
  5. **Stage-sized checkpoints, closure rounds 2–5, and recurring-defect escalation (`skills/subagent-driven-development/SKILL.md` Steps 8–10, `skills/adversarial-review/SKILL.md`, `profiles/code-diff.md`, `assets/promote-prompt.md`, `assets/composition-contract.md`)**:
     - Non-final wave checkpoints pass `--depth standard` to all three lenses. Final Round 1 passes `--depth deep` over `RUN_BASE..HEAD`.
     - At the start of each final review round `r`, the orchestrator records `ROUND_<r>_HEAD` (with `LAST_ROUND_HEAD = ROUND_<r-1>_HEAD` for `r >= 2`) in the run journal.
     - For Final Rounds `r >= 2`, if every fixer in round `r-1` stayed within its declared component `scope.files`, Step 8 runs in **closure mode** through a single channel (`criteria`):
       - `target` is `"$LAST_ROUND_HEAD..HEAD"`.
       - For each lens (`id_prefix` in `C`, `S`, `X`), the orchestrator appends a `### Closure Round Verification` section to that lens's `{{CRITERIA}}` listing: (a) **only that lens's own prior accepted findings** matching its `id_prefix` (`C1..Cn` for `C`, `S1..Sn` for `S`, `X1..Xn` for `X`, with `id`, `severity`, `category`, `claim`, `evidence[].ref`) and (b) the touched contract seams (`scope.files` of the round `r-1` fix batch). Filtering per lens by `id_prefix` ensures `claims --id-prefix <P>` and `gate --id-prefix <P>` never encounter a foreign prefix that `validate_finding` would reject. Prior accepted findings are **never** placed in `dismissed[]` (which is reserved for rejected/dismissed findings).
       - `profiles/code-diff.md` and `assets/promote-prompt.md` state that in a closure round, the reviewer: (1) checks each listed prior accepted finding in `### Closure Round Verification` against the current working tree via `read` — omitting it if fixed, or re-reporting it with its **original `id`** (which already carries this lens's prefix) if still open; and (2) reviews `$LAST_ROUND_HEAD..HEAD` and its touched contract seams for new regressions (`"id": null`). Files cited by prior accepted findings in `### Closure Round Verification` are in scope to verify closure even if untouched by the fix delta.
       - If any fixer in round `r-1` modified files outside its declared component scope (or required a wave re-plan), round `r` falls back to full discovery over `RUN_BASE..HEAD`.
     - **Recurring-defect escalation**: If a standing finding in round `r >= 3` shares both `category` and target file/contract seam with an accepted finding from rounds `r-2` and `r-1` (meaning two consecutive fixer attempts failed to close that defect class on that seam), Step 9 stops dispatching narrow fixers for it and escalates via a root-cause design task or a Tier 2 `orca ask` (`--timeout-ms 600000`, default = dispatch a widened root-cause redesign task covering the full module seam).
  6. **Single-owner test topology, narrow reproductions, and role effort pins (`skills/writing-plans/SKILL.md`, `skills/adversarial-review/`, `skills/subagent-driven-development/`)**:
     - `skills/writing-plans/SKILL.md` (`## File Structure`, `## Task Independence`, `## Task Structure`, `## Self-Review`) requires every test file created or modified in a wave to belong to a single owning task (or a single serialized component chain), and requires each task's `Acceptance` command to run only its owned test files (reserving the full suite for Step 7's wave gate). `implementer-prompt.md:53-61` and `fixer-prompt.md:41-47` instruct workers to run their exact `{{ACCEPTANCE}}` command and never run the full repository suite when `{{ACCEPTANCE}}` is scoped to specific test files.
     - `skills/writing-plans/SKILL.md:302-304` notes that standalone `writing-plans` and `quirk:executing-plans` run `plan-document-reviewer-prompt.md`, while `quirk:subagent-driven-development` skips it in favor of branch-level adversarial review.
     - `profiles/code-diff.md`, `promote-prompt.md`, and `refute-prompt.md` forbid running the full test suite when `prepass.status == "pass"`; reproductions must run the narrowest single test file, test function (`-k`), or command that demonstrates the defect.
     - Role effort is documented as a protocol table in `skills/subagent-driven-development/SKILL.md` (`## Roles` / `### Step 5` / `### Step 8`) and `skills/adversarial-review/SKILL.md` (`## Dispatch`) (not a Python constant in `scripts/adversarial-review`): `high` for implementers, promote reviewers, refute reviewers, and fixers; `medium` for tiebreak arbiters; and `low` or `medium` for read-only Explore/survey subagents. On `pi-watch` dispatches, the stage passes `--thinking` set to the lower of the role's target effort and `model.json`'s `thinking` ceiling under the ordering `low < medium < high`, respecting model ceilings such as `flash` (`medium`). `manifest.reviewer.thinking` continues to record `model.json`'s `thinking` value. On `Agent` dispatches, the stage specifies the role's effort level without relying on experimental harness-only flags.
- **Invariants**: All six DO-NOT-CHANGE fences below hold throughout.
- **Errors**: Unrecoverable chain failures or 5-round cap with open `CRITICAL`/`HIGH` trigger Tier 1 hard stops at handoff.

## Data models / schemas

Back-links: [logic.md#tree-once-caching-and-review-staging-hygiene](logic.md#tree-once-caching-and-review-staging-hygiene), [logic.md#glossary](logic.md#glossary)

`SCHEMA:`
```json
{
  "ResolveResult": {
    "profile": "code-diff | spec-design | plan | prose-claim",
    "target_kind": "git-range | worktree | path",
    "target_ref": "string",
    "artifact_hash": "sha256-hex",
    "diff_file": "string | null",
    "untracked_paths": ["string"],
    "excluded_paths": ["vendor/bundle.js (98000 lines)"],
    "include_all": false,
    "full_worktree_hash": "sha256-hex | null (present when target_kind == worktree)",
    "size_metric": 0,
    "depth_suggestion": "quick | standard | deep",
    "contract_surface": false,
    "chain": {"run_id": "hex", "artifact_hash": "sha256-hex", "step": "resolve", "predecessor": null}
  },
  "ReusedCheckInput": {
    "tree_hash": "git-tree-sha",
    "clean_tree": true,
    "full_worktree_hash": "sha256-hex-required-when-target-kind-is-worktree",
    "checks": [
      {
        "name": "code-check",
        "command": "python3 -m pytest -q",
        "exit_code": 0,
        "status": "pass | fail",
        "duration_ms": 462000,
        "output": "string"
      }
    ]
  },
  "PrepassResult": {
    "status": "pass | fail | could-not-run",
    "tree_hash": "git-tree-sha | null",
    "checks": [
      {
        "name": "code-check",
        "command": "python3 -m pytest -q",
        "exit_code": 0,
        "status": "pass | fail",
        "duration_ms": 462000,
        "reused": true,
        "output": "string"
      }
    ],
    "findings": [],
    "observed_artifact_hash": "sha256-hex | null",
    "chain": {"run_id": "hex", "artifact_hash": "sha256-hex", "step": "prepass", "predecessor": "sha256-hex"}
  },
  "ClaimsOutput": {
    "claims": [{"id": "C1", "severity": "HIGH", "confidence": "MEDIUM", "category": "slug", "claim": "string", "evidence": []}],
    "findings": [],
    "carried_kinds": ["limitation", "question"],
    "diff_excerpts": "string",
    "excluded_paths": ["string"],
    "chain": {"run_id": "hex", "artifact_hash": "sha256-hex", "step": "claims", "predecessor": "sha256-hex"}
  },
  "CompositionContractInput": {
    "target": "str",
    "profile?": "code-diff | spec-design | plan | prose-claim",
    "lens?": "str",
    "id_prefix?": "C | S | X | F",
    "depth?": "quick | standard | deep",
    "model?": "str",
    "author_family?": "anthropic | openai | google | other",
    "criteria": "str (includes ### Closure Round Verification for this lens's id_prefix on rounds >= 2)",
    "dismissed[]": [{"id": "str", "claim": "str", "ruling_reason": "str"}],
    "resolve_file?": "path to shared resolve.json across concurrent lenses",
    "prepass_file?": "path to shared prepass.json across concurrent lenses",
    "reuse_check?": "path to ReusedCheckInput JSON for prepass --reuse-check",
    "include_all?": "bool (disables default diff exclusions when true)"
  }
}
```

## DO-NOT-CHANGE fences

Back-links: [logic.md#conceptual-model](logic.md#conceptual-model), [logic.md#key-decisions--rationale](logic.md#key-decisions--rationale)

- **Fence 1 (`skills/adversarial-review/scripts/adversarial-review:991-1035, 1498-1565, 1949-1992`) — Cryptographic run-chain and `observed_artifact_hash` verification**:
  - Reason: `CHAIN_PREDECESSOR`, `link_from`, `verify_artifact_is_current`, and the `observed_artifact_hash == prepass_link["artifact_hash"]` check in `run_gate` prevent stale or cross-run files from laundering a failing review into `PASS`. Shared `resolve.json`/`prepass.json` across lenses and `--reuse-check` must satisfy this chain rather than weakening or bypassing it.
- **Fence 2 (`skills/adversarial-review/SKILL.md:45-56`, `assets/composition-contract.md:21-31`) — Asymmetric context / withholding author reasoning**:
  - Reason: Reviewers must never receive commit messages, design rationale, or implementer reports. Closure-round context stages only prior accepted finding records (`id`, `severity`, `category`, `claim`, `evidence`), the fix delta (`LAST_ROUND_HEAD..HEAD`), and the verbatim `criteria`, never fixer narratives.
- **Fence 3 (`skills/adversarial-review/scripts/adversarial-review:1275-1280, 1590-1591`) — Pre-pass provenance and tiebreak no-bash boundary (`assets/tiebreak-prompt.md:71-81`)**:
  - Reason: Only findings originating from `PrepassResult.findings` carry `stage: "prepass"` credit, and tiebreak arbiters must never be granted `bash` or shell access.
- **Fence 4 (`skills/subagent-driven-development/SKILL.md:190-220, 332-487`) — Disjoint component write scopes, `CHAIN_SNAPSHOT_<n>` symmetric-difference attribution, and the wave-end commit barrier**:
  - Reason: No two concurrent tasks may share a file, no task or component may commit before all components in the wave return, and workers never commit their own work. Tree-test caching and narrow task acceptance must not alter snapshot attribution or the wave-end barrier.
- **Fence 5 (`skills/subagent-driven-development/SKILL.md:637-655`, `tests/test_adversarial_review_skill.py:258-330, 625-630`) — Step 8/9 delegation invariants and Step 10 blocked handoff on open `CRITICAL`/`HIGH`**:
  - Reason: Existing skill tests assert that Step 8 delegates to `adversarial-review`, passes `depth` explicitly, keeps all three lenses (`correctness / logic`, `spec compliance`, `security and failure modes`) and both review modes (`Checkpoint`, `Final loop`), retains `not proof the dispatches happened`, and keeps `effective severity`, `connected components`, `dismissed`, and `fixer-prompt.md` in Step 9. Step 10 must never auto-ship an open `CRITICAL` or `HIGH` at the 5-round cap.
- **Fence 6 (`skills/executing-plans/SKILL.md:52-64`, `tests/test_writing_specs_skill.py:91-132`) — Cross-file markdown links, heading anchors, and `executing-plans` plan review**:
  - Reason: `test_writing_specs_skill.py` verifies all relative links and `#anchor` headings across `writing-specs`, `brainstorming`, `subagent-driven-development`, and `executing-plans`. Editing `writing-plans` and `subagent-driven-development` must preserve existing heading slugs referenced externally and keep `plan-document-reviewer-prompt.md` active for `executing-plans`.

## Always / Ask / Never

Back-links: [logic.md#decisions-locked](logic.md#decisions-locked), [logic.md#scope--non-goals](logic.md#scope--non-goals)

**Always**
- Verify `HEAD^{tree}`, `clean_tree` boolean, `status`/`exit_code` consistency, command coverage, `observed_artifact_hash`, and (on worktree targets) `full_worktree_hash` before accepting `--reuse-check` in `scripts/adversarial-review`, and fall back to a live `prepass` run in SDD Step 8 if `--reuse-check` exits 2.
- Share one `resolve.json` and one `prepass.json` across the `C`, `S`, and `X` lenses within a single review round, passing distinct `--id-prefix C`, `S`, and `X` to `claims` and `gate`.
- Filter prior accepted findings by lens `id_prefix` when staging `### Closure Round Verification` into `{{CRITERIA}}` for closure rounds 2–5.
- Register mid-run Tier 2 questions via `orca ask --timeout-ms 600000` with an explicit `default` (falling back to synchronous `AskUserQuestion` only when `orca ask` is `unavailable`), keep running unblocked components while polling `orca ask wait`, and log `<decision> (assumed, <status>)` on `timed_out`, `partial`, or `declined`.
- Print the per-round adjudication digest table in Step 9 before dispatching fixers, and route any user veto into the next fix batch.
- Pin `high` effort on implementers, promote reviewers, refute reviewers, and fixers; `medium` on tiebreak arbiters; and `low` or `medium` on read-only Explore/survey subagents (capped by the model's `ALIAS_LADDER` thinking ceiling on `pi-watch`).

**Ask (via Tier 1 or Tier 2 `orca ask`)**
- Tier 1 (blocking, no timeout): Single consolidated preflight card (`backend_pairing`, plus `dirty_tree_action` when dirty and `env_readiness` when probes fail), and Step 10 blocked handoff when the 5-round cap is reached with an open `CRITICAL`/`HIGH` or a chain fails twice with no safe default.
- Tier 2 (10-minute deadline with default): `NEEDS_CONTEXT` not answerable from the spec/codebase, mid-wave scope-conflict splits, wave-gate test failures exposing a contract conflict, reviewer `kind: "question"` items, and recurring-defect escalations after two failed fixer attempts.

**Never**
- End an orchestrator turn while an `orca ask` card is still pending.
- Populate `tree_test_cache` from a worker's text claim alone without an orchestrator or `prepass` execution on that `tree_identity`.
- Place prior accepted findings into `dismissed[]` or pass another lens's `id_prefix` findings into `### Closure Round Verification`.
- Run the full test suite inside a promote or refute reviewer when `prepass.status == "pass"`.
- Pass `--check-cmd "true"` to fake a green pre-pass.
- Mutate a target repository's test configuration or install packages mid-run to speed up a slow suite.
- Create new skill directories (which would desynchronize the skill count in `README.md`).

## Cross-cutting

Back-links: [logic.md#tree-once-caching-and-review-staging-hygiene](logic.md#tree-once-caching-and-review-staging-hygiene), [logic.md#three-tier-human-gates-preflight-consolidation-and-adjudication-digests](logic.md#three-tier-human-gates-preflight-consolidation-and-adjudication-digests)

- **Security & prompt-injection containment**: `diff_excerpts` in `refute-prompt.md` and `contested_excerpts` in `tiebreak-prompt.md` remain wrapped inside `<<<ARTIFACT-BEGIN>>>` and `<<<ARTIFACT-END>>>` with the existing untrusted-data warning so excerpting never strips prompt-injection guards.
- **Scope-bounding transparency**: `excluded_paths` is included in `SCOPE_BOUNDING_FIELDS`, `GateResult`, and `manifest.json` alongside `unreviewed_paths`, with its own `any exit + excluded_paths nonempty ->` decision row in `composition-contract.md`, `skills/adversarial-review/SKILL.md`, and SDD Step 8's signal table. If a caller needs vendored or lockfile changes reviewed, `--include-all` disables the filter.
- **Backward compatibility of CLI flags**: All new `scripts/adversarial-review` flags (`--include-all` on `resolve`, `--reuse-check` on `prepass`, `--repo-root` on `claims`) are optional with defaults that preserve existing behavior on ordinary source files, keeping all 276 existing tests in `tests/test_adversarial_review.py` passing.
- **Observability & auditability**: `PrepassResult` and `manifest.prepass` record `"tree_hash"` and per-check `"reused"` and `"duration_ms"`; `ResolveResult`, `GateResult`, and `manifest` record `"excluded_paths"`; and the run journal records `(assumed, <status>)` on deadline-resolved questions and logs the `>300s` slow-suite advisory.

## Testing strategy

Back-links: [logic.md#behavior--scenarios](logic.md#behavior--scenarios), [logic.md#scope--non-goals](logic.md#scope--non-goals)

- **`tests/test_adversarial_review.py`**:
  - Add unit and CLI integration tests for `resolve` default exclusions (`vendor/`, `node_modules/`, `dist/`, `build/`, lockfiles, `*.min.js`), verifying `excluded_paths` population with line counts (`"<path> (<N> lines)"`), `size_metric` reduction, excluded untracked files not appearing in `unreviewed_paths[]`, `--include-all` override, and `excluded_paths` propagation to `gate` and `manifest`.
  - Add tests for `prepass --reuse-check`:
    - Happy path where `tree_hash`, `clean_tree`, command list, and `artifact_hash` / `full_worktree_hash` match: 0 check subprocesses spawned, `"reused": True` and `"duration_ms"` stamped in `PrepassResult` and `manifest.prepass.checks[]`, `"tree_hash"` recorded in `PrepassResult` and `manifest.prepass`, and `gate` + `manifest` exit 0.
    - Reused failing check (`exit_code: 1, status: "fail"`): `prepass` exits 1 and emits a `stage: "prepass"` finding (`failing-check`).
    - Rejection paths (exit 2): `tree_hash` mismatch, `status`/`exit_code` mismatch (`exit_code: 1, status: "pass"`), missing `clean_tree` boolean, dirty tracked working tree on `git-range`, modified excluded or untracked file (`full_worktree_hash` mismatch) on `worktree`, missing expected command in `checks[]`, and `--reuse-check` passed with `--profile spec-design`.
  - Add tests for sharing a single `resolve.json` and `prepass.json` across three lens invocations (`--id-prefix C`, `S`, `X`) through `claims` → `merge` → `gate` → `manifest`.
  - Add tests for `claims` emitting `diff_excerpts` and `excluded_paths` (for `file-line`, `quote`, and `absence` refs) and `gate` emitting `contested_excerpts` (including `counter_evidence` refs) while keeping `CLAIM_FIELDS` intact.
- **`tests/test_adversarial_review_skill.py`**:
  - Add structural assertions verifying:
    - `profiles/code-diff.md`, `promote-prompt.md`, and `refute-prompt.md` forbid running the full test suite when `prepass` is `pass` and require narrow single-test reproductions.
    - `refute-prompt.md` and `tiebreak-prompt.md` document staging `diff_excerpts` and `contested_excerpts` into `{{ARTIFACT}}`.
    - `composition-contract.md` documents `resolve_file`, `prepass_file`, `reuse_check`, `include_all`, `excluded_paths[]`, and `contested_excerpts`, and includes an `excluded_paths` decision row in `"Distinguishing a clean review from a crashed one"`.
    - `skills/subagent-driven-development/SKILL.md` specifies the single-card preflight (`backend_pairing` with `task-fallback`, `dirty_tree_action`, `env_readiness`), orchestrator-verified `tree_test_cache`, three-tier human gates (`--timeout-ms 600000`, `assumed, timed_out`, per-round adjudication digest), `--depth standard` at checkpoints and `--depth deep` in Final Round 1, closure mode in Final Rounds 2+ over `LAST_ROUND_HEAD..HEAD` with per-lens `id_prefix` filtering, recurring-defect escalation, auto-dispatched wave-gate test fixers, the 5-minute (`300s` / `300000ms`) slow-suite advisory on wave gates and pre-pass, and role effort pins.
    - `skills/writing-plans/SKILL.md` specifies single-owner test files per wave and task-scoped `Acceptance` commands.
- **Full verification command**:
  `COMMAND:`
  ```bash
  python3 -m pytest -q tests/test_adversarial_review.py tests/test_adversarial_review_skill.py tests/test_writing_specs_skill.py tests/test_simplifying_safely_skill.py tests/test_adhd_skill.py
  ```

## Non-goals

Back-links: [logic.md#scope--non-goals](logic.md#scope--non-goals), [logic.md#deferred-ideas](logic.md#deferred-ideas)

- Modifying target repositories' pytest/Playwright configurations or installing `pytest-xdist` during an SDD run.
- Speculative off-critical-path wave checkpoints (starting Wave N+1 before Wave N's checkpoint completes).
- Introducing a separate `sdd-ctl` wrapper binary or SQLite daemon outside `scripts/adversarial-review`.
- Relying on Claude Code harness-specific features (such as experimental agent teams or prompt-caching flags).
- Lowering effort below `high` on implementers, promote reviewers, refute reviewers, or fixers.
