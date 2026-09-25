# Changelog

All notable changes to quirk are recorded here, newest first. Versions are
calendar-based (**CalVer**, `YYYY.M.D` unpadded); the `releasing-quirk` skill
stamps and prepends each entry (newest on top). Since the version no longer encodes
compatibility, breaking changes are called out in a `### ⚠️ BREAKING` subsection.

## 2026.9.25

### Changes
- **Interactive logic specs:** brainstorming can opt into `logic.json` as the source
  and a local, single-file review page with scope, risk, scenario, and sign-off
  gates. A Python 3.9 stdlib renderer validates, exports, folds signed decisions,
  and generates the downstream `logic.md`; Markdown remains the default.
- Added a data-driven Astryx review page with optional coverage, certainty,
  story-map, and automatically laid-out state-machine views. The prebuilt page
  is shipped with quirk; authoring a spec requires no Node build.

## 2026.9.17

### ⚠️ BREAKING
- **`quirk:writing-tech-spec` is gone; it's merged into `quirk:writing-specs`.**
  The logic-spec and tech-spec rubrics are now consolidated under one skill —
  `writing-specs/SKILL.md` plus `logic-spec.md` and `tech-spec.md` — with
  brainstorming running the logic-spec half after design approval and the
  execution skills running the tech-spec half in-context when the complexity
  gate fires. Anything invoking `quirk:writing-tech-spec` directly breaks;
  invoke `quirk:writing-specs` instead.
- **The typed-artifacts SessionStart hook (`load_artifact_tail.sh`) no longer
  tails raw file content.** It previously printed the last 50 lines of each
  artifact file; it now shells out to `bin/pm.py --index` / `--next` for a
  bounded, computed summary (open/placed counts plus a shortlist of next
  candidates), falling back to `[quirk:pm] index unavailable` if `pm.py`
  fails. Anything parsing the hook's prior raw-tail output breaks.

### Changes
- **New: `bin/pm.py`, a read-only view over typed-artifact markdown**
  (`--index`, `--next`, `--doctor`). Phase 1 has no Status field, no Blocked
  by, and no ROADMAP.md, so every well-formed entry reads as open and
  unplaced; lifecycle counts and roadmap-derived findings are Phase 2+. Wired
  into the SessionStart hook (see BREAKING above).
- **New skill: `simplifying-safely`** — use when asked to simplify, clean up,
  or refactor code, review a diff/PR/draft for over-engineered additions, or
  author/edit a spec, CLAUDE.md, skill file, or other agent-facing document.
  Where a correctness check exists (in practice, code) no simplification
  ships until it's re-validated against that check; elsewhere the call stays
  with human judgment rather than passing to a simplicity signal.
- `subagent-driven-development` gained a selectable implementer backend
  (IMPLEMENTER / AUTHOR_FAMILY / REVIEWER_ALIAS resolved at preflight with a
  single dispatch seam) and waves are now partitioned by connected components
  of write scope.
- `quirk:brainstorming` gained outcome-altitude elicitation: a two-tier
  coverage model (Essential / Default-able) with an outcome-altitude screen
  and forking-power ordering.
- Skills that told Claude to dispatch subagents "via the `Task` tool" now say
  `Agent` (current Claude Code's name for it), with hardened offline
  fallbacks so a tool-name mismatch is never read as "tool unavailable."
- Typed artifacts (`BUGS.md`, `DEFERRED.md`, `TEST_BACKLOG.md`, `proposals.md`,
  `docs/adr/`) are now tracked in the quirk repo itself.

## 2026.7.31

### ⚠️ BREAKING
- **`subagent-driven-development` lost its captain tier and its worktree/merge lane.**
  The skill was rewritten around cheap fast implementers plus one adversarial review
  loop at the end: two tiers instead of three, working in-place with disjoint file
  scopes. Eleven prompt assets and four scripts were removed —
  `scripts/sdd-acceptance`, `scripts/sdd-dispatch`, `scripts/sdd-ledger`,
  `scripts/sdd-wave`, and the `assets/*captain*`, `*merge-resolver*`,
  `*spec-reviewer*`, `*code-quality-reviewer*` and `*codex-adversarial*` prompts.
  Anything invoking those paths directly breaks; there is no shim. Re-invoke the
  skill and let it drive, rather than calling its internals.

### Changes
- **New skill: `filing-requests`** — a guided, evidence-gathering session for filing a
  bug, feature request, or code-change request. Emits a terse markdown artifact and,
  on explicit confirmation, a GitHub issue. Its spine is a canonical JSON document
  where every field carries its provenance (`observed` with a source, `reported`,
  `inferred`, or `missing` with a reason), which is what makes the anti-slop rules
  structural rather than advisory: a field with no provenance cannot render. Three
  gates are enforced by script — a non-waivable gate that refuses to emit a feature
  request without a stated problem and a testable criterion, a secret scan scoped by
  output rather than by field, and a separate confirmation before anything is filed.
  Eight stdlib-only scripts; PyYAML is used when present and never required.
- **New skill: `adversarial-review`** — attacks finished work with typed reviewer
  profiles, a promote/refute two-stage, and an evidence gate, plus SDD delegation.
- **New skill: `writing-scannable-prose`** — dependency-checked compression for
  technical docs.
- `subagent-driven-development` rewritten (see BREAKING above): three reviewers with
  distinct lenses, a checkpoint review after any non-final wave, and a final loop that
  runs to clean or five rounds.
- `releasing-quirk` now documents the commit message it actually uses.

## 2026.7.9

### ⚠️ BREAKING
- **Versioning switched from semver to CalVer.** Releases are now stamped with the
  day they ship (`YYYY.M.D`, e.g. `2026.7.9`); a 2nd+ release on the same day
  appends a micro (`2026.7.9.1`). This is a deliberate one-way door — earlier
  semver releases (`≤ 5.9.0`) still sort *before* every CalVer version because
  `2026 > 5`, so upgrades stay monotonic. quirk's own `version` field is an
  opaque string to Claude Code, so installs are unaffected; the only breakage is
  for anyone who pinned quirk via a semver-*range* dependency — replace such
  constraints with an exact/date-based pin.

### Changes
- Rewrote the `releasing-quirk` skill: the version is now derived from today's
  date (via `python3`, portable across macOS/BSD) with same-day micro
  resolution, rather than judged as a patch/minor/major bump from the diff.
- Releases are now fully autonomous — compute, sync the three version files,
  write the changelog, commit, and `git push origin main` with no confirmation
  gate. Test failures and non-fast-forward pushes still stop the process.
- Added this `CHANGELOG.md`; breaking changes are surfaced here now that the
  version no longer signals them.
