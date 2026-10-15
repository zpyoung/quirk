# quirk:full-code-review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use quirk:subagent-driven-development (recommended) or quirk:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. "Follow the step exactly" means **satisfy the stated acceptance criteria** — if a contract is ambiguous, ask before guessing.

**Status:** Draft (agent-reviewed; fixes applied)

**Executor:** quirk:executing-plans, this session and later ones (plan persisted for that reason).

**Goal:** Port `sakura:review-mr-combined` into quirk as `quirk:full-code-review`: forge-neutral (GitHub + GitLab + none), org-neutral, with packs and `REVIEW.md` policy.

**Goals / Non-Goals:**
- Goals: everything in `docs/quirk/specs/2026-10-15-full-code-review/logic.md#done-when`, built in the order of `docs/quirk/specs/2026-10-15-full-code-review/tech.md#build-order-and-pr-stack`.
- Non-goals: any edit under the sakura install; any edit to `skills/requesting-code-review`, `skills/receiving-code-review`, `skills/adversarial-review`; CI gating; running the smoke corpus in CI; version bumps (release automation owns them).

**Architecture:** see `docs/quirk/specs/2026-10-15-full-code-review/tech.md#architecture`
**Alternatives considered:** see `docs/quirk/specs/2026-10-15-full-code-review/logic.md#approach`
**Tech Stack:** see `docs/quirk/specs/2026-10-15-full-code-review/tech.md#architecture`
**Constraints:** see `docs/quirk/specs/2026-10-15-full-code-review/tech.md#always--ask--never` and `#do-not-change-fences`
**Cross-cutting:** see `docs/quirk/specs/2026-10-15-full-code-review/tech.md#cross-cutting`

**Coupling map.** Every script imports from `forge/` after Task 2; `comment_body.py`, `post_reviewer_review.py`, and `validate_triage.py` import `review_memory.py`; `render_report.py` imports `md_render.py` and `highlight.py` and reads `assets/report.html`; the triage paste grammar couples `assets/report.html` and `validate_triage.py`. Tasks are a strictly ordered PR stack, so no two run concurrently; each task's `scope.files` is its audit boundary.

**Session setup** (run at the start of every session; all commands below run from the repo root `/Users/zpyoung/orca/workspaces/quirk/code-review`):

`COMMAND:`
```bash
export SRCS=/Users/zpyoung/.claude/plugins/cache/sakura/sakura/1.9.7/skills/review-mr-combined
export SRCSH=/Users/zpyoung/.claude/plugins/cache/sakura/sakura/1.9.7/shared/mr
export V39="${V39:-$(mktemp -d)/venv39}"
[ -x "$V39/bin/python" ] || { python3.9 -m venv "$V39" && "$V39/bin/pip" install -q pytest; }
export V312="${V312:-$(mktemp -d)/venv312}"
[ -x "$V312/bin/python" ] || { python3.12 -m venv "$V312" && "$V312/bin/pip" install -q pytest; }
```

`SK` = `skills/full-code-review`, `T` = `tests/full_code_review` (prose shorthand only).

**Branches (stacked PRs):** T1 on `zpyoung/code-review` (carries the spec commits). Each later task branches off the previous tip: `zpyoung/fcr-2-gitlab-seam`, `zpyoung/fcr-3a-dispatch`, `zpyoung/fcr-3b-identity`, `zpyoung/fcr-4-policy`, `zpyoung/fcr-5-github`, `zpyoung/fcr-6-extras`. Opening PRs is a user decision at the end (quirk:finishing-a-development-branch).

**Standard test acceptance** (referenced as "standard suite" below):

`COMMAND:`
```bash
python3 -m pytest -q tests/full_code_review
"$V312/bin/python" -m pytest -q tests/full_code_review
"$V39/bin/python" -m pytest -q tests/full_code_review
```
Expected: each prints `0 failed` (no `failed` or `error` in the summary line).

---

### Task 1: Verbatim port, tests green under quirk's pytest

```yaml
dependencies: []
scope:
  files: [skills/full-code-review/**, tests/full_code_review/**, README.md]
```

**Behavior:** the ported scripts and their 418 collected tests pass from quirk's tree. No renames or logic changes; SKILL.md still describes sakura paths and is rewritten in Task 3b.

**Contract:**
- Copy `$SRCS/{SKILL.md,references,scripts,assets}` to `SK/`, excluding `references/provenance.md`, `references/repo-guidance/`, `__pycache__`, `.pytest_cache`. Copy `$SRCSH/review_memory.py` to `SK/scripts/review_memory.py`. Never move or edit anything under `$SRCS` or `$SRCSH`.
- The three scripts that insert `../../../shared/mr` on `sys.path` stop doing so and import `review_memory` as a sibling: `comment_body.py:17`, `post_reviewer_review.py:20`, `validate_triage.py:11`.
- `README.md` skill count goes from 25 to 26 (two repo tests assert it matches `skills/*/SKILL.md`).
- Copy `$SRCS/tests/*.py` into `T/`. Add `T/__init__.py` and `T/conftest.py` that put `SK/scripts` on `sys.path`. Each test file's own `sys.path.insert(…"..","scripts")` header and `test_review_memory.py:9` resolve to `SK/scripts`; `test_render_report.py:14-15` resolves `SK/assets/report.html`.

**Acceptance (`COMMAND:`):** the standard suite, plus

```bash
python3 -m pytest -q tests/full_code_review | tail -1
python3 -m pytest -q
git rev-parse HEAD
```
Expected: the first prints `418 passed` (skips allowed only if the total passed+skipped is 418); the whole-repo suite shows `0 failed`; record the printed SHA as `T1_SHA` in the Task 2 notes.

- [x] Step 1 (`COMMAND:`): `mkdir -p skills/full-code-review tests/full_code_review && rsync -a --exclude tests --exclude references/provenance.md --exclude references/repo-guidance --exclude __pycache__ --exclude .pytest_cache "$SRCS"/ skills/full-code-review/ && cp "$SRCSH"/review_memory.py skills/full-code-review/scripts/ && cp "$SRCS"/tests/*.py tests/full_code_review/`
- [x] Step 2: rewire imports and test paths per the Contract; run the acceptance; fix only path issues.
- [x] Step 3: commit `feat(full-code-review): port review-mr-combined verbatim`.

---

### Task 2: Extract GitLab code behind the forge seam (refactor-only)

```yaml
dependencies: [T1]
scope:
  files: [skills/full-code-review/scripts/forge/__init__.py, skills/full-code-review/scripts/forge/gitlab.py, skills/full-code-review/scripts/prepare_diff.py, skills/full-code-review/scripts/borrow_review_source.py, skills/full-code-review/scripts/post_reviewer_review.py, skills/full-code-review/scripts/review_memory.py]
```

**Behavior:** every `glab` invocation and GitLab JSON parse lives in `forge/gitlab.py`; observable behavior and every test are unchanged.

**Contract:**
- `forge/__init__.py` defines the `Forge` Protocol, `ForgeError`, and every dataclass in `tech.md#forge-interface` (the SCHEMA block: `User`, `ChangedFile`, `Change`, `Anchor`, `Note`, `Thread`, `Receipt`, `StagedInline`, `StagedReply`, `PendingItem`, `StageResult`).
- `forge/gitlab.py` defines `GitLabForge` implementing the full Protocol, built from the symbols listed in `tech.md#symbols-that-move-into-forgegitlabpy`; its runner is `gitlab._api(host, method, endpoint, payload=None, timeout=120)`.
- The original scripts keep module-level names with unchanged signatures that delegate to `GitLabForge` and are looked up on the module at call time, because the tests replace them as attributes: `prepare_diff.glab_mr_changes(iid, host, project, cwd=".", metadata=None)`, `glab_mr_details(iid, host, project)`, `glab_current_user(host)`, `glab_find_mr_for_branch(b, p, h=None)`, `_run(cmd, timeout=90)`; `post_reviewer_review._api(host, method, endpoint, payload=None, timeout=120)`, `_request_changes`; `review_memory.fetch_discussions(host, project, iid, api=None)`; `borrow_review_source._clone_project(host, project, root)`, `_run(cmd, timeout=180, env=None)`. Where a test replaces `post_reviewer_review._api`, `GitLabForge` must route through that replaced callable (pass the runner in, or look it up through the script module).
- Fence (`tech.md#do-not-change-fences`): reviewer staging invariants in `post_reviewer_review.py` (504-506, 491-494, 733-734, 738-743, 747-752, 428-434) keep their semantics and order.

**Acceptance (`COMMAND:`):** the standard suite, plus

```bash
git diff --stat "$T1_SHA" -- tests/full_code_review
grep -rnE "\[\"glab\"|'glab'|\"glab\"" skills/full-code-review/scripts --include='*.py' | grep -v '/forge/'
```
Expected: the diff stat prints nothing; the grep prints nothing.

**Execution note (2026-10-15):** done. `GitLabForge` currently exposes only `change_label` and `head_refspec`; the scripts call the functional API in `forge/gitlab.py` with late-bound runners. Full Protocol conformance (dataclass-returning methods) moved to Task 3a Step 2, where the scripts switch to dispatching through a `Forge`. `ReviewError` is now an alias of `forge.ForgeError` (a `RuntimeError` subclass).

- [x] Step 1: `forge/__init__.py` types and Protocol; commit.
- [x] Step 2: `GitLabForge` read path (change, details, user, branch lookup, file-list recovery inputs) with `prepare_diff.py` shims; acceptance; commit.
- [x] Step 3: clone and head refspec with `borrow_review_source.py` shims; commit.
- [x] Step 4: threads, drafts, publish, approve, request-changes with `post_reviewer_review.py` and `review_memory.py` shims; commit.

---

### Task 3a: Forge dispatch, detection, and neutral vocabulary

```yaml
dependencies: [T2]
scope:
  files: [skills/full-code-review/scripts/**, skills/full-code-review/assets/report.html, skills/full-code-review/assets/sample-report.json, skills/full-code-review/references/orchestration.md, skills/full-code-review/references/html-report.md, skills/full-code-review/references/posting.md, skills/full-code-review/references/report-template.md, tests/full_code_review/**]
```

**Behavior:** scripts pick a forge with `detect_forge` and talk only to the `Forge` object; context and report use neutral vocabulary.

**Contract:**
- `detect_forge` and `--forge github|gitlab|none` exactly as `tech.md#detect_forge`; `DEFAULT_HOST` removed; `prepare_diff.py` uses `detect_forge` and writes `tech.md#contextjson-rename-of-the-sakura-shape`.
- Scripts call `Forge` methods; the Task 2 shims are deleted and tests retarget to `forge.gitlab._api` or a fake `Forge`. Reviewer-staging fence unchanged.
- Report: `schema_version: 1`, `meta.forge`, `meta.target: "change"|"branch"|"local"`, `meta.number` (`tech.md#reportjson-additions-schema_version-1`) across `render_report.py`, `validate_triage.py`, `comment_body.py`, `post_reviewer_review.py`, `review_memory.py`, `assets/sample-report.json`, `build_sample_report.py` output in `report.html`. `validate_triage.export_label` uses `Forge.change_label` ("MR !N" for GitLab, "PR #N" for GitHub).
- Fence: the paste grammar in `assets/report.html` export JS and `validate_triage.parse_export` change in the same commit, covered by a round-trip test (render a report, extract the export text the page would produce from the embedded handoff/test fixture, validate it); `validate_triage.py` anti-forgery checks keep their semantics.
- New `T/test_forge_detect.py` covering `tech.md#testing-strategy` row for it.

**Acceptance (`COMMAND:`):** the standard suite, plus

```bash
grep -rnE '\bDEFAULT_HOST\b|"mr"|\bmeta\.iid\b|\["iid"\]' skills/full-code-review/scripts --include='*.py' | grep -v '/forge/gitlab.py'
```
Expected: the grep prints nothing.

**Execution note (2026-10-15):** Steps 1-2 done for `prepare_diff.py`. The `Forge` Protocol was narrowed to the dict shapes the scripts already consume (documented in `forge/__init__.py`); the speculative dataclasses were removed. `borrow_review_source.py`, `review_memory.py`, and `post_reviewer_review.py` keep calling `forge.gitlab` functions until Task 5, where the GitHub adapter supplies the second implementation and those three switch to `Forge` dispatch together (designing the reviewer abstraction from GitLab alone would guess its shape). `make_forge("github", …)` raises until Task 5.

- [x] Step 1: `test_forge_detect.py` red; `detect_forge` green; drop `DEFAULT_HOST`; commit.
- [x] Step 2 (prepare_diff only; see note): give `GitLabForge` full Protocol conformance (dataclass-returning methods, `list_threads` returning the neutral discussion-dict shape documented in `tech.md#symbols-that-move-into-forgegitlabpy`); switch scripts to `Forge` dispatch; delete shims; retarget tests; commit.
- [x] Step 3: context/report vocabulary across scripts, assets, references, tests, with the paste round-trip test, in one commit.

---

### Task 3b: Identity, lenses, guidance CLIs, SKILL.md

```yaml
dependencies: [T3a]
scope:
  files: [skills/full-code-review/**, tests/full_code_review/**]
```

**Behavior:** no Recharge or sakura identity remains; the 14 lenses are generic; SKILL.md routes to references in ≤ 500 lines.

**Contract** (each defined in `tech.md`; section in brackets):
- Lens IDs, `lenses/` directory, front matter, `tests.md` split into three lenses plus `lenses/_mutation-probe.md`; `references/dimensions/` removed [Lens front matter; Marker, storage, and naming → lens-ID table].
- Org text stripped: framing lines `correctness.md:8`, `safety.md:8`, `adversarial.md:10`, `tests.md:8`, `code-comments.md:4,12`; examples `adversarial.md:74`, `correctness.md:52`, `tests.md:66`, `scope.md:169,181-182` replaced with neutral ones; `cross-repo.md:15,29` reworded to the sibling scan plus optional search hook [Cross-repo search hook].
- `lenses/risk.md` generic rubric [Generic risk rubric].
- Marker, localStorage, handoff delimiter, ledger dir, borrowed ref, source marker file, temp prefixes, reply text renamed; legacy one-line marker parsing removed [Marker, storage, and naming].
- `--no-escalate` replaces `--no-opus` / `SAKURA_REVIEW_NO_OPUS`; lens model fallback rule written into `references/orchestration.md` [Lens model selection and fallback].
- `discover_guidance.py`: remove `--sakura-guidance-dir`, `--repo-key`, and the `"sakura"` output key; output is `{repo_key, target_repo}`; its test updated accordingly.
- `add_guidance.py`: final interface `--note TEXT --target review-md|project-pack|user-pack --git-root ROOT` with the paths and errors in [add_guidance.py]; `test_add_guidance.py` rewritten to cover the three targets and the three error cases.
- Astryx attribution comment [HTML report design tokens].
- SKILL.md: `name: full-code-review`; description names GitHub, GitLab, and local changes; ≤ 500 lines; detail lives in `references/posting.md`, `references/degradation.md`, `references/orchestration.md`; scripts referenced as `${CLAUDE_PLUGIN_ROOT}/skills/full-code-review/scripts/…`; flag table [SKILL.md flag surface] listing only flags implemented so far (`--pack`, `--seat`, `--stats` arrive later).
- New `T/test_no_org_names.py` and `T/test_full_code_review_skill.py` per [Testing strategy]. `test_no_org_names.py` builds its pattern from string fragments (for example `"sak" + "ura"`) so its own source does not match.

`REGEX:` (case-insensitive; the pattern `test_no_org_names.py` assembles) `\b(recharge|rechargeapps|sakura|sourcebot)\b|\bkai:`

**Coherence sweep** (run before Step 1 to scope the work and at the end as acceptance):

`COMMAND:`
```bash
grep -rniE 'sakura|recharge|sourcebot|kai:|shared/mr|references/dimensions|no-opus|merge_request|diff_refs|draft_note|\bglab\b|gitlab|\bmr\b|\biid\b|MR !' skills/full-code-review tests/full_code_review \
  | grep -vE '^skills/full-code-review/scripts/forge/gitlab\.py:|^tests/full_code_review/test_forge_gitlab\.py:|^tests/full_code_review/test_post_reviewer_review\.py:|^tests/full_code_review/test_forge_detect\.py:|^skills/full-code-review/references/posting\.md:' \
  | grep -viE 'gitlab|glab'
```
Allowlist rationale: `forge/gitlab.py` and the GitLab fakes legitimately use GitLab endpoint vocabulary (`merge_requests`, `iid`, `diff_refs`, `draft_notes`); `posting.md` has GitLab sections; any remaining line that names GitLab or glab by name (e.g. "GitLab MR" in forge-neutral prose listing both forges) is reviewed by hand rather than failed. Expected at the end: the command prints nothing.

**Acceptance (`COMMAND:`):** the standard suite, the coherence sweep above, plus

```bash
wc -l < skills/full-code-review/SKILL.md
```
Expected: suite `0 failed`; sweep prints nothing; `wc` prints a number ≤ 500.

- [ ] Step 1: lens rename, split, front matter, org-text strip, generic risk rubric; commit.
- [ ] Step 2: marker/storage/ledger/ref/temp renames, legacy marker removal, `--no-escalate`, fallback rule; commit.
- [ ] Step 3: `discover_guidance.py` and `add_guidance.py` interfaces with tests; commit.
- [ ] Step 4: SKILL.md rewrite, references reshuffle, attribution comment, `test_full_code_review_skill.py`, `test_no_org_names.py`; commit.

---

### Task 4: Policy, report contract, seat and probe rules

```yaml
dependencies: [T3b]
scope:
  files: [skills/full-code-review/scripts/resolve_policy.py, skills/full-code-review/scripts/policy_yaml.py, skills/full-code-review/scripts/prepare_diff.py, skills/full-code-review/scripts/forge/__init__.py, skills/full-code-review/scripts/forge/gitlab.py, skills/full-code-review/scripts/render_report.py, skills/full-code-review/scripts/comment_body.py, skills/full-code-review/scripts/post_reviewer_review.py, skills/full-code-review/assets/report.html, skills/full-code-review/references/policy.md, skills/full-code-review/references/orchestration.md, skills/full-code-review/references/html-report.md, skills/full-code-review/SKILL.md, tests/full_code_review/test_resolve_policy.py, tests/full_code_review/test_render_contract.py, tests/full_code_review/test_seat_mixed.py, tests/full_code_review/test_comment_body.py, tests/full_code_review/test_post_reviewer_review.py, tests/full_code_review/test_render_report.py, tests/full_code_review/test_prepare_diff.py, tests/full_code_review/test_forge_gitlab.py]
```

**Behavior:** packs and `REVIEW.md` shape the run; generated files are excluded; floor-below findings never post; incomplete runs are never clean; mixed authorship asks; the probe follows the trust rule.

**Contract:**
- `resolve_policy.py` CLI, layers, target-ref reads, merge rules, `--apply`, `check-attr --source` behavior and git < 2.40 fallback, errors [`tech.md#resolve_policypy`]; output [`tech.md#policyjson`]; config keys and block-only rule [same section's CONFIG]. `policy_yaml.py` is a byte-identical copy of `skills/filing-requests/scripts/_yaml_mini.py`.
- `policy.guidance_files` = every `guidance/*.md` in the user pack (or `--pack`) and the project pack; SKILL.md passes them, with `discover_guidance.py` output, to the `conventions` lens.
- `references/policy.md` documents layers, paths (`${XDG_CONFIG_HOME:-~/.config}/quirk/review/`, `<repo>/.quirk/review/`, `--pack`), keys, the block-only YAML rule, the target-branch rule, and the `!.quirk/review/` gitignore note.
- Report keys `run.incomplete`, `run.dimensions_failed`, `run.models`, `run.verification`, `run.excluded_generated`, `run.policy_sources`, `run.severity_floor` validated by `render_report.py`; incomplete banner and no clean verdict; floor-below findings rendered with `post: false` from `comment_body.py` and omitted by `post_reviewer_review.py stage` [`tech.md#reportjson-additions-schema_version-1`].
- `GitLabForge.commit_authors` (commit `author_email` matched against `User.emails`), `mixed_authorship`, `--seat` [`tech.md#seat-detection`]; `Change.is_fork` and `Change.author_trusted` for GitLab [`tech.md#forge-interface`]; probe rule in SKILL.md [`tech.md#always--ask--never` → Never].
- SKILL.md: policy step after source selection and before the size gate; `--pack` and `--seat` added to the flag table.

**Acceptance (`COMMAND:`):** the standard suite, plus

```bash
python3 -m pytest -q tests/full_code_review/test_resolve_policy.py tests/full_code_review/test_render_contract.py tests/full_code_review/test_seat_mixed.py -v
cmp skills/full-code-review/scripts/policy_yaml.py skills/filing-requests/scripts/_yaml_mini.py
```
Expected: `0 failed`; `cmp` prints nothing. `test_resolve_policy.py` asserts: four-layer precedence; reviewer-seat reads from a target ref that differs from the working tree (real temp git repo); nearest `REVIEW.md` overrides the root key by key; lens replace vs add; `skip` union; `models` merge; a flow mapping exits 2 naming file and line; `--apply` drops a `linguist-generated` file and a `skip_globs` match and recomputes `size`; a `.gitattributes` change present only at the PR head excludes nothing in reviewer seat; `guidance_files` lists pack guidance files.

- [ ] Step 1: `policy_yaml.py` copy and `resolve_policy.py`, one red/green cycle per assertion group above; commit.
- [ ] Step 2: report contract keys, renderer banner, floor handling in both posting paths; commit.
- [ ] Step 3: commit authors, mixed authorship, `--seat`, fork/trust fields, probe rule; commit.
- [ ] Step 4: `references/policy.md`, SKILL.md policy step, guidance wiring, flags; commit.

---

### Task 5: GitHub adapter

```yaml
dependencies: [T4]
scope:
  files: [skills/full-code-review/scripts/forge/github.py, skills/full-code-review/scripts/forge/__init__.py, skills/full-code-review/scripts/prepare_diff.py, skills/full-code-review/scripts/borrow_review_source.py, skills/full-code-review/scripts/post_reviewer_review.py, skills/full-code-review/scripts/review_memory.py, skills/full-code-review/scripts/comment_body.py, skills/full-code-review/references/posting.md, skills/full-code-review/SKILL.md, tests/full_code_review/test_forge_github.py, tests/full_code_review/test_prepare_diff.py, tests/full_code_review/test_borrow_review_source.py, tests/full_code_review/test_post_reviewer_review.py, tests/full_code_review/test_review_memory.py]
```

**Behavior:** both seats work on GitHub PRs with the same guarantees as GitLab.

**Contract:** `tech.md#github-adapter-specifics` and `#forge-interface` in full. Invariants mapped from the GitLab fence: refuse when the viewer already has a PENDING review; stage is one create with anchors pre-validated (unplaceable → overview + warning); false-422 adoption by overview digest; exact comment-set equality and unchanged head + merge base immediately before submit; `published` recorded before ledger work; cleanup is a printed `gh api … -X DELETE …/reviews/{id}` the agent never runs; author inline via `POST …/pulls/{n}/comments`, overview via `POST …/issues/{n}/comments`; `list_threads` via GraphQL `reviewThreads`; `commit_authors` from `pulls/{n}/commits` `author.login`; `is_fork` from `head.repo.full_name != base.repo.full_name`; `author_trusted` from `author_association`.

**Ask gate:** before Step 3, verify on a real PR the user owns that `addPullRequestReviewThreadReply` with `pullRequestReviewId` attaches a reply to a pending review. Ask the user before creating any PR or review. If it does not attach, stop and escalate (affects `logic.md#forge-support`).

**Acceptance (`COMMAND:`):** the standard suite, plus

```bash
python3 -m pytest -q tests/full_code_review/test_forge_github.py -v
grep -rnE "\[\"gh\"|'gh'|\"gh\"" skills/full-code-review/scripts --include='*.py' | grep -v '/forge/'
```
Expected: `0 failed`; grep prints nothing. `test_forge_github.py` patches a `FakeGitHub` onto `github._api` and `github._graphql` and covers every bullet in the `test_forge_github.py` row of `tech.md#testing-strategy`.

- [ ] Step 1: read path (`get_change`, file pagination and missing-patch flag, merge base, `current_user`, `find_change_for_branch`, `commit_authors`, fork/trust, `head_refspec`, `clone`); commit.
- [ ] Step 2: author seat posting and `list_threads`; commit.
- [ ] Step 3: Ask gate, then reviewer stage/publish/complete/cleanup with all invariants and support replies; commit.
- [ ] Step 4: `posting.md` GitHub sections and SKILL.md wording; commit.

---

### Task 6: Measurement, verification, cross-repo, example pack, smoke corpus, GitLab polish

```yaml
dependencies: [T5]
scope:
  files: [skills/full-code-review/scripts/review_memory.py, skills/full-code-review/scripts/smoke_check.py, skills/full-code-review/scripts/forge/gitlab.py, skills/full-code-review/scripts/post_reviewer_review.py, skills/full-code-review/scripts/prepare_diff.py, skills/full-code-review/references/orchestration.md, skills/full-code-review/references/policy.md, skills/full-code-review/references/lenses/cross-repo.md, skills/full-code-review/references/example-pack/**, skills/full-code-review/SKILL.md, tests/full_code_review/test_memory_stats.py, tests/full_code_review/test_review_memory.py, tests/full_code_review/test_smoke_check.py, tests/full_code_review/test_forge_gitlab.py, tests/full_code_review/test_post_reviewer_review.py, tests/full_code_review/test_resolve_policy.py, tests/fixtures/full-code-review/smoke/**]
```

**Behavior / Contract** (each from `tech.md`):
- `review_memory.py stats` [`#review_memorypy-stats`]: both seat vocabularies, empty-ledger output, skip-with-warning for unreadable records; extend `_safe_record` if it collapses reviewer dispositions; `--stats` in SKILL.md.
- Cross-family verification procedure in `references/orchestration.md` [`#cross-family-verification`], recording `run.verification`.
- Sibling-clone scan limits and `cross_repo.search_agent` in `lenses/cross-repo.md` [`#cross-repo-search-hook`].
- `references/example-pack/` and its assertions in `test_resolve_policy.py` [`#example-pack`].
- Five smoke cases and `smoke_check.py` [`#smoke-checker`, `#smoke-corpus`]; "Running the smoke corpus" section in `orchestration.md`.
- GitLab polish [`#gitlab-adapter-specifics`]: `Content-Type: application/json` on writes (update `FakeGitLab` expectations); items on `too_large`/`collapsed` files move to the overview with a warning.

**Acceptance (`COMMAND:`):** the standard suite, plus

```bash
python3 -m pytest -q
python3 -m pytest -q tests/full_code_review/test_memory_stats.py tests/full_code_review/test_smoke_check.py tests/full_code_review/test_forge_gitlab.py -v
```
Expected: `0 failed` everywhere.

**Manual done-when checks** (results go in the PR description):
- Smoke corpus: for each case, copy `tests/fixtures/full-code-review/smoke/<case>/repo/` to a temp dir, `git init` and commit it, apply `change.patch`, run the skill with `--local --no-open`, then `python3 skills/full-code-review/scripts/smoke_check.py --report <report.json> --expected tests/fixtures/full-code-review/smoke/<case>/expected.json` → exit 0 for all five.
- Zero-config: run the skill `--local --no-open` in a repo with no `REVIEW.md` and no pack → a report renders.

- [ ] Step 1: stats; commit.
- [ ] Step 2: cross-family verification and cross-repo docs; commit.
- [ ] Step 3: example pack and tests; commit.
- [ ] Step 4: smoke fixtures, checker, tests; commit.
- [ ] Step 5: GitLab polish and `test_forge_gitlab.py`; commit.
- [ ] Step 6: manual done-when checks.
