---
name: releasing-quirk
description: Use when releasing the quirk plugin - commits any pending changes, stamps a calendar-based (CalVer) version from today's date, writes the changelog, and pushes to origin autonomously. Triggers on "release quirk", "ship quirk", "bump and push quirk", or "cut a quirk release".
---

# Releasing Quirk

## Overview

Cut a release of the quirk plugin: verify tests, stamp today's date as the version (CalVer), sync the three version files, write the changelog, commit, and push — autonomously.

**Core principle:** The version *is* the release date, not a judgment call. Breaking changes are called out in the changelog, since the version no longer encodes them.

**Announce at start:** "I'm using the releasing-quirk skill to cut a release."

## Versioning scheme

Versions are **CalVer**: `YYYY.M.D`, unpadded — `2026.7.9`, never `2026.07.09`.

- Unpadded is valid 3-segment semver, so no validator rejects it and it sorts correctly. Zero-padding is rejected: PEP 440 tooling normalizes `2026.07.09` → `2026.7.9`, which would silently **desync** the three version files.
- A 2nd+ release on the same day appends a micro: `2026.7.9.1`, `2026.7.9.2`. The first release of a day stays plain 3-segment (`2026.7.9`).
- "Today" is the machine's **local** date (`date.today()`), so a release cut just before midnight uses that day's date — no surprises.
- The scheme is monotonic over the old semver line: `2026.* > 5.x` because `2026 > 5` under both string and numeric compare. No git tags are created (same as before) — same-day detection reads the version files, not tags.

## Preconditions

Run from the quirk repo root (the directory containing `pyproject.toml` and `.claude-plugin/`). Verify before doing anything:

```bash
test -f pyproject.toml && test -f .claude-plugin/plugin.json && test -f .claude-plugin/marketplace.json \
  || { echo "Not in quirk repo root"; exit 1; }
```

If not in the right directory, stop and tell the user.

## The Process

### Step 1: Verify Tests

```bash
pytest -q
```

If tests fail, stop. Do not release a broken tree. Autonomy does not mean shipping red.

### Step 2: Survey Changes

```bash
git status
git fetch origin
git log --oneline origin/main..HEAD
git diff origin/main..HEAD --stat
git diff           # any unstaged changes
git diff --staged  # any staged changes
```

You need to know:
- What's already committed but unpushed.
- What's still uncommitted (and whether it should be in this release).

If there are uncommitted changes that don't belong in the release, stop and ask the user. Otherwise proceed without a gate.

### Step 3: Compute the CalVer Version

Derive the version from today's date and the current version. Do **not** use `date +%Y.%-m.%-d` — the `%-` unpadding flag is GNU-only and fails on macOS/BSD `date`. Use `python3` (already a project dependency), reading `pyproject.toml` as the same-day source of truth (there are no tags):

```bash
python3 - <<'PY'
import datetime, re, pathlib
today = datetime.date.today()
cal = f"{today.year}.{today.month}.{today.day}"          # unpadded, e.g. 2026.7.9
current = re.search(r'^version = "([^"]+)"', pathlib.Path("pyproject.toml").read_text(), re.M).group(1)
parts = current.split(".")
if parts[:3] == cal.split("."):                          # already released today → advance the micro
    micro = int(parts[3]) + 1 if len(parts) > 3 else 1
    print(f"{cal}.{micro}")
else:                                                    # first release today (or coming from semver)
    print(cal)
PY
```

- First release of the day → `2026.7.9`.
- Re-run the same day → `2026.7.9.1`, then `.2`, ... (idempotent: always advances, never collides).
- Coming from an old semver version like `5.9.0` → `2026.7.9`.

### Step 4: Sync the Three Version Files

The version lives in **all three** of these and they must stay in sync:

- `pyproject.toml` — `version = "..."`
- `.claude-plugin/plugin.json` — `"version": "..."`
- `.claude-plugin/marketplace.json` — `"version": "..."` (inside `plugins[0]`)

Use `Edit` to update all three to the new version. Do **not** use `sed -i` — Edit is safer and the diff is reviewable.

After editing, verify they match:

```bash
grep -E '"version"|^version' pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

All three should print the new version.

### Step 5: Write the Changelog

The version no longer signals compatibility, so read the diff **only to write release notes**. `CHANGELOG.md` is [Keep a Changelog](https://keepachangelog.com)-style but CalVer-dated, newest release on top. **Prepend** a section for this release:

```markdown
## 2026.7.9

### ⚠️ BREAKING
- <what broke and what the user must do about it>

### Changes
- <one line per notable commit since the last release>
```

The heading is the version itself (already the date). Fill **Changes** from the notable commits in `git log origin/main..HEAD`.

Include the **`### ⚠️ BREAKING`** subsection only when one of these breaking signals fires (omit it entirely otherwise):
- A skill / command / hook file **removed or renamed** (`git diff origin/main..HEAD --stat`).
- `BREAKING CHANGE:` in any commit body.
- A breaking change to an artifact file format, a hook contract, or the `plugin.json` schema.

### Step 6: Commit and Push — Autonomously

No confirmation gate. Stage the three version files plus the changelog, commit, and push:

```bash
git add pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md
git commit -m "chore: release <version>"
git push origin main
```

If there are unrelated uncommitted changes you've already cleared with the user, commit them **first** with their own message, then make the dedicated release commit — don't bury the release in an unrelated commit.

If the push is rejected (non-fast-forward), stop. Do **not** force-push. Ask the user how to reconcile.

### Step 7: Report

One short line: new version, commit SHA, how many commits were pushed.

```
Released 2026.7.9 (abc1234). Pushed 3 commits to origin/main.
```

## Dry run (validation)

This is a prose skill, not code. To validate a change to it, do a **dry run**: run Steps 3–5 to compute the version and changelog and show the diff, confirm the three files match via the Step 4 grep, but skip the `git push` in Step 6. The normal release path has no such gate — the dry run is only for verifying the skill itself before a real autonomous run.

## Quick Reference

| Step | Command / Action |
|------|------------------|
| 1 | `pytest -q` |
| 2 | `git status && git log --oneline origin/main..HEAD` |
| 3 | Compute CalVer from today's date via `python3` + same-day micro from `pyproject.toml` |
| 4 | Edit `pyproject.toml`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` |
| 5 | Prepend a `CHANGELOG.md` entry (headline any breaking changes) |
| 6 | `git commit -m "chore: release <version>" && git push origin main` |
| 7 | Report new version + SHA |

## Common Mistakes

**Bumping before tests pass**
- **Problem:** The release is broken on arrival.
- **Fix:** `pytest -q` is Step 1, no exceptions.

**Zero-padding the date**
- **Problem:** `2026.07.09` gets normalized to `2026.7.9` by PEP 440 tooling, silently desyncing the three files.
- **Fix:** Always unpadded — `2026.7.9`. The `python3` snippet in Step 3 produces the correct form.

**Using `date` to compute the version**
- **Problem:** `date +%-m` / `%-d` (unpadded) is GNU-only and fails on macOS/BSD.
- **Fix:** Use the `python3` snippet in Step 3.

**Adding a micro on the first release of the day**
- **Problem:** `2026.7.9.1` when no `2026.7.9` shipped yet — wrong and non-obvious.
- **Fix:** The first release of a day is plain `YYYY.M.D`; `.N` only when today's date already shipped (Step 3 handles this from `pyproject.toml`).

**Only updating one or two version files**
- **Problem:** Marketplace shows a stale version while `plugin.json` advanced; install-from-marketplace gets the wrong code.
- **Fix:** Always update all three; verify with the grep in Step 4.

**Skipping the changelog or burying breaking changes**
- **Problem:** CalVer no longer encodes compatibility, so an unlisted breaking change is invisible to users on upgrade.
- **Fix:** Always prepend a `CHANGELOG.md` entry; headline breaking changes in a `### ⚠️ BREAKING` subsection.

**Force-pushing on rejection**
- **Problem:** Overwrites someone else's pushed commits.
- **Fix:** Stop on rejection, ask the user, never `--force` without explicit instruction.

## Red Flags

**Never:**
- Release without running tests.
- Zero-pad the date segments (`2026.07.09`).
- Compute the version with `date +%-m` / `%-d` (BSD/macOS unsafe).
- Use `sed -i` to edit version files.
- Encode breaking-ness in the version — it goes in the changelog.
- Force-push to `main`.

**Always:**
- Run from the quirk repo root.
- Compute the date with `python3`, reading `pyproject.toml` as the same-day source of truth.
- Update all three version files together.
- Prepend a `CHANGELOG.md` entry, headlining any breaking changes.
- Use a dedicated `chore: release <version>` commit.
