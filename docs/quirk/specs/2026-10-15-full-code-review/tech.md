# quirk:full-code-review — tech spec

**Status:** Reviewed
**Logic spec:** [logic.md](logic.md) — this document owns *where* and *contracts*; the logic spec owns *why* and *behavior*.

Paths below use these roots:

- `SRC` = `/Users/zpyoung/.claude/plugins/cache/sakura/sakura/1.9.7` (read-only port source)
- `SRCS` = `SRC/skills/review-mr-combined`; a bare citation like "SRC `prepare_diff.py:567`" means `SRCS/scripts/prepare_diff.py`, and `glab-recipes.md` / `review_memory.py` citations mean `SRC/shared/mr/`
- `Q` = `/Users/zpyoung/orca/workspaces/quirk/code-review` (this repo)
- `SK` = `Q/skills/full-code-review`

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Approach](logic.md#approach).

The skill is a port of `SRC/skills/review-mr-combined` plus `SRC/shared/mr/review_memory.py`, reorganized so that only `scripts/forge/` knows about GitHub or GitLab. Everything is Python 3.9+, standard library only; Pygments stays optional (built-in lexer fallback already exists in `highlight.py`). GitHub and GitLab are reached only through the `gh` and `glab` CLIs, which own authentication.

Target layout:

- `SK/SKILL.md` — ≤ 500 lines; routes to references.
- `SK/references/`
  - `orchestration.md` — ported; lens roster, finding schema, merge rules.
  - `policy.md` — new; packs, `REVIEW.md`, precedence, front-matter keys.
  - `posting.md` — ported; author and reviewer delivery for both forges.
  - `html-report.md` — ported; `report.json` contract at `schema_version` 1.
  - `report-template.md` — ported.
  - `degradation.md` — moved out of SKILL.md's "Graceful degradation".
  - `lenses/<lens-id>.md` — 14 checklists plus `_mutation-probe.md`, ported from `references/dimensions/`.
  - `example-pack/` — new; see "Example pack".
- `SK/scripts/`
  - `prepare_diff.py` — ported; forge-neutral diff and seat orchestration.
  - `borrow_review_source.py` — ported; worktree or clone at the change head.
  - `resolve_policy.py` — new; merges built-in roster, packs, `REVIEW.md`; filters the context.
  - `discover_guidance.py` — ported; repo conventions discovery.
  - `add_guidance.py` — ported; three write targets.
  - `post_reviewer_review.py` — ported; reviewer batch stage, publish, complete.
  - `comment_body.py`, `validate_triage.py` — ported.
  - `review_memory.py` — moved from `SRC/shared/mr/`; adds `stats`.
  - `render_report.py`, `md_render.py`, `highlight.py`, `build_sample_report.py`, `vendor_astryx_tokens.sh` — ported.
  - `smoke_check.py` — new; deterministic checker for the smoke corpus.
  - `policy_yaml.py` — copy of `Q/skills/filing-requests/scripts/_yaml_mini.py` under a distinct module name, so the two never collide in `sys.modules` during one pytest session.
  - `forge/__init__.py` (protocol, data classes, `detect_forge`), `forge/gitlab.py` (every `glab` call), `forge/github.py` (every `gh` call).
- `SK/assets/` — `report.html`, `sample-report.json`.
- `Q/tests/full_code_review/` — `__init__.py`, `conftest.py` (puts `SK/scripts` on `sys.path`), the 11 ported test files, and the new files under Testing strategy.
- `Q/tests/fixtures/full-code-review/smoke/<case>/` — smoke corpus.

How the files relate at run time follows the logic spec's four stages:

1. `prepare_diff.py` calls `forge.detect_forge()` then `Forge.get_change()` / `current_user()` and writes `context.json`.
2. `borrow_review_source.py` (reviewer seat) produces the source root. `resolve_policy.py` reads packs and `REVIEW.md` from that root (target-branch ref in reviewer seat), writes `policy.json`, and rewrites `context.json` with generated files excluded and size recomputed. `discover_guidance.py` supplies conventions files.
3. The coordinator (SKILL.md prose) dispatches lens subagents per `policy.json`, optionally runs cross-family verification through `pi-watch`, and writes `report.json`; `review_memory.py reconcile` adds memory fields.
4. `render_report.py` → triage page → `validate_triage.py` → `review_memory.py save` → `comment_body.py` / `post_reviewer_review.py`, which post through `Forge`.

SKILL.md references bundled files as `${CLAUDE_PLUGIN_ROOT}/skills/full-code-review/...`, matching `Q/skills/adversarial-review/SKILL.md:61`.

## Code references

Back-links: [Approach](logic.md#approach), [Forge support](logic.md#forge-support).

### Port source → destination

| Source | Destination | Notes |
|---|---|---|
| `SRC/skills/review-mr-combined/SKILL.md` (710 lines) | `SK/SKILL.md` | Rewrite to ≤ 500 lines; move posting, degradation, policy detail to references |
| `…/references/dimensions/*.md` (12 files) | `SK/references/lenses/*.md` | Rename per lens-ID table; strip org text |
| `…/references/orchestration.md` (347) | `SK/references/orchestration.md` | Roster rows at SRC lines 126-141; finding schema 172-183; dedup 301-303; escalation 143-160 |
| `…/references/{posting,html-report,report-template}.md` | same names under `SK/references/` | Posting gains GitHub sections |
| `…/references/provenance.md`, `…/references/repo-guidance/*` | not ported | Org-specific |
| `…/agents/sourcebot-researcher.md` | not ported | Replaced by the pack search hook |
| `…/scripts/` (11 `.py` + 1 `.sh`) | `SK/scripts/` | See per-file notes below; drop `DEFAULT_HOST` (SRC `prepare_diff.py:20`, used at 49) entirely — host comes only from the remote, `--host`, or forge detection |
| `SRC/shared/mr/review_memory.py` (930) | `SK/scripts/review_memory.py` | Imports become sibling imports |
| `…/assets/*` | `SK/assets/` | Rename storage keys and handoff delimiter |
| `…/tests/*.py` (11 files, 418 collected tests including parametrized cases) | `Q/tests/full_code_review/` | Replace each file's `sys.path.insert(…"..","scripts")` with the conftest path; `test_review_memory.py:9` import path changes |

### Symbols that move into `forge/gitlab.py`

Extracted verbatim in behavior; each keeps a module-level shim in its original script until the rename phase (see Testing strategy, "Extraction phase").

- `prepare_diff.py`: the `glab` calls inside `glab_mr_changes` (SRC:567), `glab_mr_details` (655), `glab_current_user` (683), `glab_find_mr_for_branch` (712) — now `forge.gitlab.fetch_changes`, `mr_details`, `current_user`, `find_mr_for_branch`. `reconstruct_diff_from_changes`, `_is_binary_change`, `_same_blob`, `_can_be_metadata_only`, `_reported_change_count`, and `_prepare_gitlab_changes` stay in `prepare_diff.py`: they turn a list of per-file change records into a unified diff, which GitHub's file list needs too once mapped to the same record shape (Task 3a renames them neutrally). The GitLab parts of `resolve_host_project` (48-50) go in Task 3a with `DEFAULT_HOST`.
- `borrow_review_source.py`: `_clone_project` (133), the `refs/merge-requests/<iid>/head` refspec in `_add_worktree` (150).
- `post_reviewer_review.py`: `_api` (70), `_identity` (111), `_mr` (118), `_list_drafts` (178), `_draft_summary` (199), `_changed_paths` (324), `_cleanup_commands` (428), `_discussion_resolved` (689), `_request_changes` (802), the `position` payload in `_plan` (417-423), the approve call in `complete` (833), the note URL form in `_discussion_markers` (655-657).
- `review_memory.py`: `_default_api` (246) and the paging loop of `fetch_discussions` (261) — now `forge.gitlab.get_json` and `forge.gitlab.fetch_discussions`. The discussion dict shape (`{id, resolved, notes: [{id, body, author{id, username}, web_url?, position{new_path, new_line, old_path, old_line}?}]}`) becomes the forge-neutral thread shape that every adapter's `list_threads` returns, so `_note_author` and `_discussion_details` stay; only the GitLab note-URL fallback (517-523) moves to `forge.gitlab.note_url` in Task 3a.

### Symbols that stay forge-neutral (do not move)

`parse_unified_diff`, `split_diff_by_file`, `batch_files`, `count_changed_lines`, `classify_files`, `is_test_file`, `is_source_file`, `resolve_scope_intent`, `detect_seat`, `git_diff_branch`, `git_diff_local`, `_git_diff_path`, `_git_diff_range`, `_fail` (prepare_diff); `render_block`, `parse_block`, `finding_body`, `support_body`, `overview_body` (comment_body); all of `validate_triage.py` except `export_label`; `_anchor`, `_fingerprint`, `reconcile`, `commit_report`, `marker_fingerprints`, `note_is_from` (review_memory); all of `render_report.py`, `md_render.py`, `highlight.py`.

### Names to create

- `SK/scripts/forge/__init__.py`: `Forge` (Protocol), `User`, `Change`, `ChangedFile`, `Thread`, `Note`, `Anchor`, `Receipt`, `ForgeError`, `detect_forge`.
- `SK/scripts/forge/github.py`: `GitHubForge`.
- `SK/scripts/forge/gitlab.py`: `GitLabForge`.
- `SK/scripts/resolve_policy.py`: `resolve_policy`, `apply_policy`, `main`.
- `SK/scripts/review_memory.py`: `stats` subcommand and `compute_stats`.
- `SK/scripts/smoke_check.py`: `check`, `main`.

## Contracts & interfaces

### Forge interface

Back-links: [Forge support](logic.md#forge-support), [Data flow](logic.md#data-flow).

CONTRACT:
```
class Forge(Protocol):
    name: Literal["github", "gitlab"]
    host: str
    project: str                       # "owner/repo" or "group/sub/project"
    change_label(number: int) -> str   # "PR #12" | "MR !12"

    current_user() -> User                                   # User{id: str, username: str, emails: list[str]}
    get_change(number: int) -> Change
    find_change_for_branch(branch: str) -> int | None
    commit_authors(number: int) -> list[str] | None          # usernames; None when unresolvable
    changed_paths_between(base: str, head: str) -> list[str]
    head_refspec(number: int) -> str                         # "refs/pull/N/head" | "refs/merge-requests/N/head"
    clone(dest: str, shallow: bool) -> None
    list_threads(number: int) -> list[Thread]

    # author seat
    post_inline(number: int, body: str, anchor: Anchor, head_sha: str) -> Receipt
    post_overview(number: int, body: str) -> Receipt

    # reviewer seat
    pending_items(number: int) -> list[PendingItem]          # this user's unpublished drafts / pending review comments
    stage(number: int, overview: str, inline: list[StagedInline], replies: list[StagedReply], head_sha: str) -> StageResult
    publish(number: int, staged: StageResult) -> None
    complete(number: int, action: Literal["approve","request-changes","comment-only"], head_sha: str, body: str) -> None
    cleanup_commands(number: int, staged: StageResult) -> list[str]
```

SCHEMA (dataclasses in `forge/__init__.py`; fields derived from the structures the ported scripts already pass around):
```
User{id: str, username: str, emails: list[str]}
ChangedFile{old_path: str, new_path: str, status: "added"|"modified"|"deleted"|"renamed", diff: str | None, too_large: bool, binary: bool}
Change{number: int, title: str, description: str, web_url: str, state: "open"|"closed"|"merged",
       author: User, source_branch: str, target_branch: str, refs: {base, start, head},
       files: list[ChangedFile], file_list_complete: bool, is_fork: bool, author_trusted: bool | None}
Anchor{path: str, line: int, side: "new"|"old", old_path: str | None, start_line: int | None}
Note{id: str, author: User, body: str, url: str}
Thread{id: str, resolved: bool, path: str | None, line: int | None, notes: list[Note]}
Receipt{thread_id: str, note_id: str, url: str, inline: bool, head_sha: str}
StagedInline{finding_id: str, fingerprint: str | None, body: str, anchor: Anchor}
StagedReply{finding_id: str, fingerprint: str | None, body: str, thread_id: str}
PendingItem{id: str, body: str}
StageResult{review_id: str | None, created: list[{id, kind, finding_id, fingerprint, body_sha256}],
            moved_to_overview: list[str], warnings: list[str]}
```
`StageResult` is embedded in `staged-review.json` alongside the keys SRC `post_reviewer_review.py:534-549` already writes.

Rules every adapter follows:

- All calls go through one module-level runner per adapter (`gitlab._api` / `github._api`) so tests can replace it. Signature for both: `_api(host, method, endpoint, payload=None, timeout=120)`; GitHub also exposes `_graphql(host, query, variables)`.
- Errors raise `ForgeError(code, message)` with `code` in `{"auth", "not_found", "conflict", "validation", "transient", "unknown"}`. No adapter retries a write; a lost write response is resolved by re-listing (see stage rules).
- `Change.refs` is `{base, start, head}`, all 40-hex lowercase. GitLab maps `diff_refs`. GitHub sets `base = start = compare(base.sha...head.sha).merge_base_commit.sha` and `head = head.sha`.
- `Change.files` is the forge's file list; `Change.file_list_complete` is false when the forge truncated it (GitLab `overflow`/`changes_count` "N+", GitHub missing `patch` or a short page count). Recovery from local git stays in `prepare_diff.py` and is forge-neutral.
- `post_inline` and `stage` require each anchor to be inside a parsed hunk on its side; an adapter receiving an out-of-hunk anchor raises `ForgeError("validation")` before any network call (callers move such items to the overview first). Every write method requires `head_sha` to equal the live change head and raises `ForgeError("conflict")` otherwise.
- `Change.is_fork` is true when source and target projects differ. `Change.author_trusted` is `True`/`False`/`None`: GitHub uses `author_association in {OWNER, MEMBER, COLLABORATOR}`; GitLab returns `None` unless the author is the viewer.

### GitHub adapter specifics

Back-links: [Forge support](logic.md#forge-support), [Industry Insights](logic.md#industry-insights).

COMMAND (all with `gh api --hostname <host>`):
```
repos/{o}/{r}/pulls/{n}                                   # Change core; head.sha, base.sha, head.repo, base.repo, author_association
repos/{o}/{r}/pulls/{n}/files --paginate                  # file list + per-file patch
repos/{o}/{r}/compare/{base}...{head}                     # merge_base_commit.sha; changed paths
repos/{o}/{r}/pulls/{n}/commits --paginate                # commit_authors
repos/{o}/{r}/pulls?head={owner}:{branch}&state=open      # find_change_for_branch
user                                                      # current_user
repos/{o}/{r}/pulls/{n}/reviews                           # pending review detection (state == PENDING, user.login == viewer)
repos/{o}/{r}/pulls/{n}/reviews/{id}/comments             # pending_items
-X POST repos/{o}/{r}/pulls/{n}/reviews                   # stage: one call, no "event" field
-X POST repos/{o}/{r}/pulls/{n}/reviews/{id}/events       # publish: event=COMMENT
-X POST repos/{o}/{r}/pulls/{n}/comments                  # author inline
-X POST repos/{o}/{r}/issues/{n}/comments                 # author overview
graphql reviewThreads(first:100) with isResolved, path, line, comments{databaseId, body, author{login}, url}   # list_threads
```

- **Stage is one atomic create.** GitHub allows one pending review per user and cannot append comments to it over REST, so `stage` sends the overview as `body` and every inline item as `comments[]` (`path`, `line`, `side` RIGHT/LEFT, optional `start_line`/`start_side`, `body`) with `commit_id = head_sha`, in a single POST.
- **Pre-validate every anchor** against the file's parsed hunks before the POST: the line must fall inside a hunk on the requested side. An unplaceable item is moved to the overview body with a warning rather than sent, because one bad anchor fails the whole create.
- **False 422.** On any create error, re-list reviews; if a PENDING review by the viewer exists whose body digest equals the staged overview digest, adopt it as the staged result; any other pending review is reported as unrecognized and never deleted.
- **Support replies** are added to the pending review after creation through GraphQL `addPullRequestReviewThreadReply` with `pullRequestReviewId`. The implementer must confirm this mutation attaches the reply to the pending review before relying on it; if it does not, stop and escalate (it bears on the locked parity decision).
- **Complete.** `approve` and `request-changes` create a second, separate review with `event` APPROVE or REQUEST_CHANGES and `commit_id = head_sha`; request-changes uses the overview's first line as body because GitHub rejects an empty body for that event. `comment-only` makes no call.
- **Cleanup** command for a staged review: `gh api --hostname H -X DELETE repos/{o}/{r}/pulls/{n}/reviews/{id}`.

### GitLab adapter specifics

Back-links: [Forge support](logic.md#forge-support).

Behavior is exactly what the ported scripts do today: draft notes per item, refuse over existing drafts, exact draft-set equality before `draft_notes/bulk_publish`, approve via `POST …/approve {"sha"}`, request-changes via GraphQL `mergeRequestRequestChanges`, user-run `DELETE …/draft_notes/<id>` cleanup. Endpoint strings stay identical so the ported `FakeGitLab` in `test_post_reviewer_review.py:56-115` keeps matching.

- Add `-H "Content-Type: application/json"` to write calls (SRC `glab-recipes.md:183-188` documents a 415 without it; SRC `post_reviewer_review.py:70-76` omits it).
- Before staging an inline draft on a file whose diff GitLab marked `too_large`/`collapsed`, move that item to the overview with a warning (GitLab issue #579609: such drafts vanish on publish).

### detect_forge

Back-links: [Data flow](logic.md#data-flow).

CONTRACT:
```
detect_forge(origin_url: str | None, override: str | None, cwd: str) -> ForgeChoice
ForgeChoice{name: "github" | "gitlab" | "none", host: str | None, project: str | None, reason: str}
```

- `override` (`--forge github|gitlab|none`) wins.
- Host `github.com` → github; `gitlab.com` → gitlab.
- Any other host: run `gh auth status --hostname <host>` and `glab auth status --hostname <host>`; exactly one success picks that forge; both or neither → `none` with a reason naming `--forge`.
- No origin, or `--local` with no change number → `none` is allowed; `--local` never needs a forge.
- Host and project parsing reuses `_origin_identity` (SRC `borrow_review_source.py:55`), which already handles HTTPS, SSH, and scp forms.

### Seat detection

Back-links: [Data flow](logic.md#data-flow), [Machinery](logic.md#machinery).

- Keep `detect_seat` (SRC `prepare_diff.py:703`) unchanged.
- New `mixed_authorship(change, viewer, commit_authors) -> bool`: true when the viewer authored the change and some commit author differs, or the viewer did not author it and appears among commit authors.
- When `mixed_authorship` is true and the session is interactive, SKILL.md asks one question (author or reviewer); non-interactive runs stop with a message naming `--seat`.
- `--seat author|reviewer` exists only for that case and is rejected otherwise.
- When `commit_authors` returns `None`, skip the check and add an Assumptions line.
- Keep every coherence check in SRC `prepare_diff.py:906-953` (state open, refs 40-hex, head race, base/start race, identity present).

### resolve_policy.py

Back-links: [Customization](logic.md#customization), [Lens roster](logic.md#lens-roster), [Model mapping](logic.md#model-mapping).

COMMAND:
```
python3 resolve_policy.py --context CONTEXT --source-root ROOT [--policy-ref SHA] \
    [--pack DIR] --lenses-dir SK/references/lenses --out POLICY [--apply]
```

- Layers, lowest to highest: built-in roster (`SK/references/lenses/*.md` front matter) → user pack (`--pack`, else `${XDG_CONFIG_HOME:-~/.config}/quirk/review/` if it exists) → project pack (`<ROOT>/.quirk/review/`) → `REVIEW.md` files.
- When `--policy-ref` is given (reviewer seat: the target branch SHA), the project pack and `REVIEW.md` files are read with `git -C ROOT show <ref>:<path>`, never from the working tree.
- `REVIEW.md` selection: the root file plus any `REVIEW.md` in an ancestor directory of a changed file; a deeper file overrides a shallower one key by key.
- Merge rules: scalars override; `skip` is a union; `models` merges per lens; a lens file whose ID matches a built-in replaces its checklist; an unknown ID adds a lens (its front matter must declare `run_when` and may declare `model`).
- `--apply` rewrites `CONTEXT` in place (atomic write): removes excluded files from `changed_files`, `test_files`, `source_files`, `diff`, and `batches`, recomputes `size`, and records them in `excluded_generated`. Excluded = `linguist-generated` set, or a match against merged `skip_globs`. Attributes are read with `git -C ROOT check-attr --source <policy-ref> linguist-generated -- <paths>` in reviewer seat, so a PR cannot hide files by editing `.gitattributes`; author seat and local runs read the working tree. If the installed git lacks `check-attr --source` (git < 2.40), skip attribute-based exclusion, keep `skip_globs`, and add a warning.
- Exit 0 on success; exit 2 with `{"error": …}` on a malformed pack or front matter, naming file and line (use `policy_yaml` errors).

### Lens front matter

Back-links: [Lens roster](logic.md#lens-roster).

CONFIG (front matter at the top of every `lenses/<id>.md`):
```
id: correctness
run_when: always        # always | has_description | code_changed | source_or_config_changed | tests_changed | source_without_tests | not_diff_only
model: sonnet           # sonnet | opus | haiku
escalate: true          # may escalate one tier on High/Do-Not-Ship risk or Critical severity
batched: true           # false for risk, adversarial, scope (run once over whole diff)
```

### review_memory.py stats

Back-links: [Quality measurement](logic.md#quality-measurement).

COMMAND: `python3 review_memory.py stats [--repo PATH] [--all]`

- Reads every ledger record under `$XDG_STATE_HOME/quirk/review-memory/` for the repo identity (or all with `--all`).
- Groups decided findings by `dimension`. Kept = `fix | later | detail | blocking | non-blocking | question`; dismissed = `ignore | drop`; undecided = `none`. The ledger's existing `disposition` field must carry reviewer-seat values; extend `_safe_record` (SRC `review_memory.py:734`) if it currently collapses them.
- Prints JSON `{lenses: [{id, kept, dismissed, undecided, dismiss_rate}], records: N}` sorted by `dismiss_rate` descending. An empty or missing ledger prints `{lenses: [], records: 0}` and exits 0; an unreadable or future-schema record is skipped with a warning in a `warnings` list, never rewritten.

### add_guidance.py

Back-links: [Customization](logic.md#customization).

COMMAND: `python3 add_guidance.py --note TEXT --target review-md|project-pack|user-pack --git-root ROOT`

- `review-md` appends to `<ROOT>/REVIEW.md` (creating it with empty front matter if absent); `project-pack` appends to `<ROOT>/.quirk/review/guidance/lessons.md`; `user-pack` to `${XDG_CONFIG_HOME:-~/.config}/quirk/review/guidance/lessons.md`.
- Prints `{path, commit_hint}`; never commits.
- Errors (exit 2, `{"error": …}`): `--git-root` not a git work tree for `review-md`/`project-pack`; unknown `--target`; empty `--note`.

### Lens model selection and fallback

Back-links: [Model mapping](logic.md#model-mapping), [Lens roster](logic.md#lens-roster).

- The coordinator dispatches each lens with `policy.lenses[].model`, escalated one tier (haiku → sonnet → opus) when `escalate` and `policy.escalation` are true and risk is High/Do Not Ship or a block reports Critical. `--no-escalate` forces `escalation: false`.
- If the dispatch errors for a model reason (unknown model, quota, provider error), retry once with the lens's built-in default tier from its own front matter. Record the model that actually ran in `run.models` and add an Assumptions line naming both.
- Only a lens that still fails after that retry, or fails for a non-model reason (timeout, malformed output after one re-ask), goes into `run.dimensions_failed` and sets `run.incomplete: true`.

### Cross-family verification

Back-links: [Model mapping](logic.md#model-mapping).

- Runs only when merged policy has `cross_family.enabled: true`.
- Gate: `pi-watch --check <alias>`; on success, one `pi-watch --alias <alias> --no-tools --require-trailer VERDICTS "<prompt>"` call per batch of Must/Should findings, with each finding's text, file, line, and the relevant diff hunk inline.
- The prompt asks for `uphold` or `refute` plus one-line reason per finding ID; parse the trailer.
- Refuted findings are removed and listed under Assumptions with the reason. A malformed or missing trailer keeps every finding and records a warning.
- If the alias does not resolve, run the same verification with a `sonnet` subagent and record the fallback (logic spec: fall back to the default Claude tier, disclosed).

### Cross-repo search hook

Back-links: [Lens roster](logic.md#lens-roster).

CONFIG: `cross_repo.search_agent: <subagent type>` in a pack or `REVIEW.md`.

- When set, the cross-repo lens dispatches that agent with the changed exported symbols and treats its results as evidence.
- Always: also scan sibling clones (`git -C <dir> rev-parse` succeeds) in the parent directory of the repo root, depth 1, at most 20 repos, `git grep -n -w <symbol>` with a 10-second timeout per repo.

### Smoke checker

Back-links: [Quality measurement](logic.md#quality-measurement), [Done when](logic.md#done-when).

COMMAND: `python3 smoke_check.py --report REPORT --expected EXPECTED`

- `EXPECTED` per case: `{lens, file, line_min, line_max}`.
- Pass when some finding has that lens in its dimensions, the same file, a line overlapping the range, and severity Must or Should.
- Exit 0 pass, 1 miss (prints the miss), 2 bad input.

### SKILL.md flag surface

Back-links: [Behavior & scenarios](logic.md#behavior--scenarios).

| Flag | Meaning | Defined in |
|---|---|---|
| `<number>` / `--branch <name>` / `--local` | target | prepare_diff.py |
| `-R <project>` | project when outside its checkout | prepare_diff.py |
| `--forge github\|gitlab\|none` | override detection | detect_forge |
| `--seat author\|reviewer` | only for mixed authorship | Seat detection |
| `--pack <dir>` | stand in for the user pack | resolve_policy.py |
| `--no-escalate` | disable model escalation | Lens model selection |
| `--fresh` | discard remembered decisions | review_memory.py load |
| `--format html\|md\|both`, `--no-open` | render options | render_report.py |
| `--add-guidance "<note>"` | capture a lesson, then stop | add_guidance.py |
| `--stats` | per-lens keep/dismiss rates, then stop | review_memory.py stats |

## Data models / schemas

### context.json (rename of the sakura shape)

Back-links: [Data flow](logic.md#data-flow).

SCHEMA:
```
{
  "schema": 1,
  "forge": "github" | "gitlab" | "none",
  "seat": "author" | "reviewer",
  "source": "forge" | "git",
  "mode": "change" | "branch" | "local",
  "host": str | null, "project": str | null,
  "source_branch": str | null, "target_branch": str | null,
  "refs": {"base": sha|null, "start": sha|null, "head": sha|null},
  "changed_files": [str], "test_files": [str], "source_files": [str],
  "diff_unavailable": [str], "not_text_reviewable": [str], "untracked_files": [str],
  "excluded_generated": [str],
  "file_list_recovery": null | {...unchanged...},
  "diff": str, "batched": bool, "batches": [{"files": [str], "diff": str}],
  "change": null | {
    "number": int, "label": str, "title": str, "description": str, "web_url": str,
    "state": str, "author": {"id": str, "username": str},
    "is_fork": bool, "author_trusted": bool | null,
    "current_user": {"id": str, "username": str},
    "mixed_authorship": bool | null
  },
  "has_description": bool,
  "scope_intent": {"guess": str, "basis": str, "statement"?: str, "source"?: str},
  "size": {"files": int, "lines": int}
}
```

`mode: "mr"` and the `mr` object become `"change"` and `change` in the rename phase; until then the sakura names stay.

### policy.json

Back-links: [Customization](logic.md#customization), [Model mapping](logic.md#model-mapping).

SCHEMA:
```
{
  "schema": 1,
  "lenses": [{"id": str, "checklist": abs_path, "model": str, "escalate": bool,
              "run_when": str, "batched": bool,
              "source": "builtin" | "user-pack" | "project-pack" | "review-md"}],
  "skipped": [{"id": str, "by": str}],
  "severity_floor": "Must fix" | "Should fix" | "Nit",
  "escalation": bool,
  "cross_family": {"enabled": bool, "alias": str | null},
  "critical_paths": [glob], "skip_globs": [glob],
  "cross_repo": {"search_agent": str | null},
  "sources": [{"kind": str, "path": str, "ref": str | null}],
  "guidance_files": [abs_path],
  "warnings": [str]
}
```

CONFIG (keys accepted in `pack.yaml` and `REVIEW.md` front matter; block mappings only, because `policy_yaml` rejects flow mappings, while flow sequences of scalars are allowed):
```
severity_floor: Should fix
escalation: true
models:
  correctness: opus
  db: haiku
skip: [observability]
cross_family:
  enabled: false
  alias: codex
critical_paths: ["src/billing/**"]
skip_globs: ["**/*.lock", "migrations/**"]
cross_repo:
  search_agent: null
```

Unknown keys produce a warning, not an error. A flow mapping produces exit 2 with file and line whether or not PyYAML is installed: `resolve_policy.py` always parses with `policy_yaml`, never PyYAML, so behavior does not depend on the machine. `references/policy.md` documents the block-only rule.

### report.json additions (schema_version 1)

Back-links: [Verdict and output](logic.md#verdict-and-output), [Lens roster](logic.md#lens-roster).

SCHEMA (new or changed keys; everything else as in SRC `render_report.py:_prepare_report` 348-503):
```
"schema_version": 1,
"meta": {"forge": "github"|"gitlab"|"none", "target": "change"|"branch"|"local", "number": int, ...},
"run": {
  "incomplete": bool,
  "dimensions_failed": [str],
  "models": {"<lens>": "<model actually used>"},
  "verification": {"enabled": bool, "model": str|null, "checked": int, "refuted": int, "fallback": str|null},
  "excluded_generated": [str],
  "policy_sources": [{"kind": str, "path": str, "ref": str|null}],
  "severity_floor": str
}
```

- `meta.target: "mr"` and `meta.iid` are replaced by `"change"` and `meta.number`.
- The renderer refuses a clean verdict when `run.incomplete` is true and shows a banner listing `dimensions_failed`.
- Findings below `run.severity_floor` render on the page but get `post: false` in `comment_body.py` output and are omitted by `post_reviewer_review.py stage`.
- Additive-only rule: later versions may add keys; removing or retyping a key requires a new `schema_version`.

### Marker, storage, and naming

Back-links: [Home and relationships](logic.md#home-and-relationships).

CONFIG:
```
marker block opener      <!-- quirk-review:v1          (was <!-- sakura-review:v1; grammar unchanged, SRC comment_body.py:121-162)
legacy one-line marker   not ported                    (SRC review_memory.py:30)
handoff delimiter        <!-- quirk-review handoff: not validated, not used for posting -->
localStorage keys        quirk-review-<slug>[-reviewer]-<digest>, quirk-review:rail-width
ledger                   ${XDG_STATE_HOME:-~/.local/state}/quirk/review-memory/<target_key>.json
borrowed ref             refs/quirk-review/<n>/head
source marker file       .quirk-review-source
temp prefixes            quirk-review-clone-, quirk-review-worktree-, quirk-review-cleanup-, quirk-review.
escalation off flag      --no-escalate  (replaces --no-opus and SAKURA_REVIEW_NO_OPUS)
support reply text       "quirk full-code-review found this independently"
```

Lens IDs (fingerprints use these strings verbatim; they are bare, not namespaced):

| Lens ID | Checklist | Source file |
|---|---|---|
| `correctness` | `lenses/correctness.md` | `dimensions/correctness.md` |
| `safety` | `lenses/safety.md` | `dimensions/safety.md` |
| `risk` | `lenses/risk.md` | `dimensions/risk-assessment.md` (rewritten generic) |
| `adversarial` | `lenses/adversarial.md` | `dimensions/adversarial.md` |
| `scope` | `lenses/scope.md` | `dimensions/scope.md` |
| `db` | `lenses/db.md` | `dimensions/db-query.md` |
| `cross-repo` | `lenses/cross-repo.md` | `dimensions/cross-repo.md` |
| `conventions` | `lenses/conventions.md` | `dimensions/conventions-and-reuse.md` |
| `comments` | `lenses/comments.md` | `dimensions/code-comments.md` |
| `observability` | `lenses/observability.md` | `dimensions/observability.md` |
| `resilience` | `lenses/resilience.md` | `dimensions/resilience-and-scope.md` |
| `test-adequacy` | `lenses/test-adequacy.md` | `dimensions/tests.md` §A + §D |
| `tests` | `lenses/tests.md` | `dimensions/tests.md` §B + §D |
| `test-coverage` | `lenses/test-coverage.md` | `dimensions/tests.md` §C + §D |

Split `tests.md` into three files sharing a fourth, `lenses/_mutation-probe.md` (§D), which each test lens references.

### Generic risk rubric

Back-links: [Lens roster](logic.md#lens-roster).

`lenses/risk.md` keeps the output block shape of SRC `risk-assessment.md` (risk level Low/Medium/High/Do Not Ship, severity, rationale). It replaces the Recharge tiers at SRC lines 41-52 and the per-store flag guidance at 93-100 with:

- blast radius (who and how much is affected if wrong);
- reversibility (can it be rolled back, is data mutated);
- rollout safety (flag, staged deploy, migration ordering);
- whether the change touches any merged `critical_paths` (touching one raises the floor of the rating to Medium).

### Example pack

Back-links: [Done when](logic.md#done-when).

`SK/references/example-pack/` contains `pack.yaml` (sets `critical_paths` and one `models` override), `lenses/risk.md` (a replacement rubric for a payments domain), and `lenses/license-headers.md` (an added lens with `run_when: code_changed`). `test_resolve_policy.py` asserts that resolving with `--pack` pointing here yields the replaced `risk` checklist path and a `license-headers` lens with `source: "user-pack"`.

### HTML report design tokens

Back-links: [Deferred Ideas](logic.md#deferred-ideas).

The logic spec deferred "replacing the internal design tokens". The survey found they are not internal: `@astryxdesign/theme-neutral@0.6.2` and `@astryxdesign/core@0.6.2` are public npm packages (MIT, `github.com/facebook/astryx`). Keep them vendored verbatim between the existing `/* BEGIN astryx-tokens */` markers in `assets/report.html`, keep `vendor_astryx_tokens.sh`, and add a one-line license attribution comment next to the markers. The Figtree font continues to load from Google Fonts; the page degrades to system fonts offline.

### Smoke corpus

Back-links: [Quality measurement](logic.md#quality-measurement).

`Q/tests/fixtures/full-code-review/smoke/<case>/` holds `repo/` (a tiny tree), `change.patch`, and `expected.json`. Five cases, one per lens: `correctness` (off-by-one in a loop bound), `safety` (string-built SQL), `test-adequacy` (a test that asserts nothing about the changed branch), `db` (query inside a loop), `scope` (an unrelated rename riding along). `references/orchestration.md` gets a short "Running the smoke corpus" section: apply the patch in a temp copy, run the skill with `--local --no-open`, then `smoke_check.py`.

## Build order and PR stack

Back-links: [Approach](logic.md#approach), [Done when](logic.md#done-when).

Each step is one PR on a stack, merged in order; each leaves `python3 -m pytest -q` green.

1. **Verbatim port.** Copy SRCS (minus `provenance.md`, `repo-guidance/`) and `SRC/shared/mr/review_memory.py` into `SK/`, rewire imports and test paths into `Q/tests/full_code_review/`, make all 418 tests pass on Python 3.9, 3.11, and 3.12. No behavior or naming changes. Large but mechanical; the PR description says so.
2. **GitLab extraction.** Create `forge/__init__.py` (Protocol and types) and `forge/gitlab.py` with `GitLabForge` implementing the full Protocol; move the symbols listed under "Symbols that move into `forge/gitlab.py`" into it, leaving module-level shims in the original scripts that delegate to `GitLabForge`. Refactor-only: no test edits.
3. **Neutralize and rename**, as two PRs.
   - **3a, forge dispatch and vocabulary:** `detect_forge` and `--forge`; scripts obtain a `Forge` from `detect_forge` and call its methods; shims removed and tests retargeted to patch `forge.gitlab._api` / `GitLabForge`; drop `DEFAULT_HOST`; context and report vocabulary (`mr` → `change`, `iid` → `number`, `meta.target`, `meta.forge`, `schema_version`); `change_label`.
   - **3b, identity and lenses:** lens IDs, `lenses/` front matter and org-text strip, generic risk rubric, marker/storage/ledger/ref names, `--no-escalate` and fallback rule text, `discover_guidance.py` loses `--sakura-guidance-dir` and its `"sakura"` output key, `add_guidance.py` gets its final `--target` interface, SKILL.md rewrite to ≤ 500 lines, `test_no_org_names.py`.
4. **Policy and report contract.** `resolve_policy.py` with packs and `REVIEW.md`, `policy.guidance_files` populated from every pack's and the project pack's `guidance/*.md` and passed to the conventions lens, generated-file exclusion, incomplete reports, `run.verification` and the other new `run.*` keys, severity floor, mixed-authorship seat, probe trust rule.
5. **GitHub adapter.** `forge/github.py` and `test_forge_github.py`, posting.md GitHub sections, the `addPullRequestReviewThreadReply` check (Ask item). Highest priority after step 4, because the first user is on GitHub.
6. **Measurement and extras.** `review_memory.py stats`, cross-family verification, cross-repo sibling scan and search hook, example pack, smoke corpus and `smoke_check.py`.
7. **GitLab polish.** Content-Type header on writes and the `too_large`/`collapsed` overview fallback. Lowest priority; may ship with step 6.

## DO-NOT-CHANGE fences

Back-links: [Home and relationships](logic.md#home-and-relationships), [Machinery](logic.md#machinery).

- **Anything under `SRC/`.** It is the read-only port source and is sakura's live install; the logic spec leaves sakura untouched.
- **`Q/skills/requesting-code-review/`, `Q/skills/receiving-code-review/`, `Q/skills/adversarial-review/`.** The logic spec keeps them independent; this work must not edit or call them.
- **`validate_triage.py` binding and anti-forgery checks** (SRC 54-198: target/mode match, group order, counts, duplicate/missing IDs, anchor and severity forgery). They are what makes a pasted decision safe to post from; rename labels only.
- **The paste grammar shared by `assets/report.html` export JS and `validate_triage.parse_export`.** Changing one side without the other breaks every triage; any change lands in both in the same commit with a round-trip test.
- **Reviewer staging invariants** in SRC `post_reviewer_review.py`: refuse over existing drafts (504-506), base/start drift aborts (491-494, 733-734), exact draft-set equality before publish (738-743), `published` set before ledger work (747-752), agent never runs cleanup DELETEs (428-434). The GitHub adapter maps each one; none is relaxed.
- **`highlight.py` contract**: stripping spans reproduces `html.escape(source)` (tested in `test_highlight.py`).
- **Release-managed version fields** in `Q/pyproject.toml`, `Q/.claude-plugin/plugin.json`, `Q/.claude-plugin/marketplace.json`, `Q/CHANGELOG.md`: `bin/release.py` stamps them on merge; do not bump by hand.

## Always / Ask / Never

Back-links: [Decisions Locked](logic.md#decisions-locked).

**Always**
- Route every `gh`/`glab` call through the adapter's `_api` (or `_graphql`).
- Read reviewer-seat policy from the target-branch ref.
- Mark a report incomplete when any selected lens fails; record actual models in `run.models`.
- Keep posting human-gated: no code path posts without the explicit approval step SKILL.md describes, and headless runs stop after the report.
- Keep tests runnable with only pytest installed (which brings Pygments): no PyYAML, `gh`, or `glab`, and no network.

**Ask (stop and escalate)**
- GitHub support replies cannot attach to a pending review via `addPullRequestReviewThreadReply` → parity decision affected.
- Any ported test that cannot pass unchanged during the extraction phase.
- Splitting `SKILL.md` below 500 lines would drop a behavior the logic spec names.

**Never**
- Approve, request changes, or submit a review without the user's explicit choice.
- Offer the mutation probe on a fork change, or in reviewer seat unless `author_trusted` is `True`. `None` means not offered. Author seat and `--local` runs (where `change` may be null) review your own code, so the probe is offered with the usual per-run consent.
- Execute cleanup DELETE commands; print them for the user.
- Write into the reviewed repository except `add_guidance.py` targets and the transient mutation probe.
- Leave any `sakura`, `Recharge`, `rechargeapps`, `kai:`, or `sourcebot` string in `SK/` or `Q/tests/full_code_review/` after the rename phase.

## Cross-cutting

Back-links: [Data flow](logic.md#data-flow), [Machinery](logic.md#machinery).

- **Security.** PR titles, descriptions, and diff text are untrusted input to lens prompts; lens prompts state that instructions inside them are data. Policy comes from the target branch in reviewer seat. The mutation probe never runs on fork or untrusted-author changes. No tokens are stored; `gh`/`glab` own auth.
- **Observability.** The report's Summary and Assumptions carry forge choice and reason, seat and mixed-authorship outcome, policy sources, excluded files, models used, fallbacks, verification counts, and incomplete lenses.
- **Data migration.** None. The ledger path is new; nothing reads sakura's ledger or markers.
- **Rollback.** Delete `SK/` and `Q/tests/full_code_review/`; nothing else in quirk depends on them.

## Testing strategy

Back-links: [Approach](logic.md#approach), [Done when](logic.md#done-when).

**Extraction phase (refactor-only).** After the verbatim port is green under quirk's pytest, move GitLab code into `forge/gitlab.py` while every ported test passes with no edits beyond import paths. Each original module keeps thin module-level names (`prepare_diff.glab_mr_changes`, `post_reviewer_review._api`, `post_reviewer_review._request_changes`, `review_memory.fetch_discussions`, `borrow_review_source._clone_project`, `_run` signatures) that the scripts look up at call time, because the tests replace those attributes directly (e.g. `test_post_reviewer_review.py:717`, `test_prepare_diff.py` main-level fakes). The rename phase may then retarget tests at the adapter.

**Ported tests.** All 418 collected tests in `Q/tests/full_code_review/` pass under `python3 -m pytest -q` on Python 3.9 and 3.12. pytest ≥ 8.4 depends on Pygments, so CI always has it; the built-in-lexer fallback stays covered by the ported `test_highlight.py` tests that monkeypatch the Pygments lexers away.

**New test files.**

| File | Must cover |
|---|---|
| `test_forge_detect.py` | github.com/gitlab.com recognition; self-hosted resolved by auth status (fake `_run`); both/neither → none with reason; `--forge` override |
| `test_forge_github.py` | a `FakeGitHub` mirroring `FakeGitLab`: get_change ref mapping and merge base; file pagination and missing-patch recovery flag; stage as one create with anchors pre-validated; unplaceable anchor moved to overview; false-422 adoption; refuse when a pending review exists; exact comment-set equality before publish; head/merge-base drift aborts; complete approve/request-changes bodies; cleanup command text; fork and author_trusted mapping |
| `test_forge_gitlab.py` | Content-Type header on writes; too_large/collapsed items moved to overview |
| `test_seat_mixed.py` | mixed-authorship truth table; `None` authors skip with assumption; `--seat` rejected when not mixed |
| `test_resolve_policy.py` | precedence of all four layers; target-ref reads via `git show` (real temp repo); REVIEW.md nearest-wins; lens replace vs add; skip union; models merge; malformed YAML exit 2 with file:line; `--apply` exclusion via `linguist-generated` and `skip_globs` with size recomputed; example pack assertions |
| `test_memory_stats.py` | kept/dismissed/undecided grouping across both seat vocabularies; sort order |
| `test_add_guidance.py` | extend ported tests for the three targets |
| `test_smoke_check.py` | pass, miss, overlap edges, severity filter, bad input |
| `test_render_contract.py` | `schema_version` present; incomplete banner and no clean verdict; floor-below findings rendered but `post: false` |
| `test_no_org_names.py` | REGEX below finds nothing under `SK/` and `Q/tests/full_code_review/` |
| `test_full_code_review_skill.py` | `SKILL.md` ≤ 500 lines; `name:` equals dir; every `references/…` and `scripts/…` path in SKILL.md exists; every lens file has valid front matter and `id` equals filename |

REGEX (case-insensitive): `\b(recharge|rechargeapps|sakura|sourcebot)\b|\bkai:`

**Acceptance bar.** `python3 -m pytest -q` green in CI. The smoke corpus run by hand passes all five cases on the default model map. A `--local` run on a repo with no `REVIEW.md` or pack produces a report. These three plus `test_no_org_names.py` are the logic spec's Done-when list.

## Non-goals

Back-links: [Scope & non-goals](logic.md#scope--non-goals).

- No changes to sakura or to quirk's other review skills.
- No CI mode, exit-code gating, or headless posting.
- No forges beyond GitHub and GitLab; no GitHub Enterprise-specific API differences beyond host routing.
- No automated execution of the smoke corpus in CI (it needs live models).
- No migration from sakura's ledger or markers.
- No `agents/` directory in quirk; lens agents are dispatched with general subagent types from SKILL.md, matching the decision in `docs/quirk/specs/2026-07-27-adversarial-review/logic.md`.
