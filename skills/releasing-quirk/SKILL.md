---
name: releasing-quirk
description: Use when releasing the quirk plugin - commits any pending changes, bumps the version using semver based on the actual diff, and pushes to origin. Triggers on "release quirk", "ship quirk", "bump and push quirk", or "cut a quirk release".
---

# Releasing Quirk

## Overview

Cut a release of the quirk plugin: verify tests, choose a semver bump from the actual diff, sync the three version files, commit, push.

**Core principle:** The bump level is derived from what changed, not from a guess.

**Announce at start:** "I'm using the releasing-quirk skill to cut a release."

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

If tests fail, stop. Do not bump or push a broken tree.

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

If there are uncommitted changes that don't belong in the release, stop and ask the user.

### Step 3: Decide the Bump

Read the diff, then pick **one** of patch / minor / major using these rules. Don't average — pick the highest level that any single change triggers.

| Bump | When to pick it |
|------|-----------------|
| **patch** | Bug fixes, doc fixes, internal refactors, test-only changes, hook lint tweaks, README/typo edits. No user-visible behavior change beyond fixing what was broken. |
| **minor** | New skill, new slash command, new hook, new template, or new opt-in functionality on an existing skill/command. Backward-compatible additions. |
| **major** | Removing or renaming a skill / command / hook, breaking change to an artifact file format, breaking change to a hook contract or `plugin.json` schema, anything that would break an existing user's project on upgrade. |

**Heuristics from commit messages** (use as a sanity check, not the source of truth):

- `feat:` → at least minor.
- `fix:` / `docs:` / `chore:` / `test:` / `refactor:` → patch unless they remove something user-facing.
- `BREAKING CHANGE:` in any commit body → major.
- Skill/command file deleted or renamed in `git diff --stat` → major.

State the chosen bump and the one-sentence reason before editing files.

### Step 4: Bump the Three Version Files

Current version lives in **all three** of these and they must stay in sync:

- `pyproject.toml` — `version = "X.Y.Z"`
- `.claude-plugin/plugin.json` — `"version": "X.Y.Z"`
- `.claude-plugin/marketplace.json` — `"version": "X.Y.Z"` (inside `plugins[0]`)

Read the current version from `pyproject.toml`, compute the new one, then use Edit to update all three. Do not use `sed -i` — Edit is safer and the diff is reviewable.

After editing, verify they match:

```bash
grep -E '"version"|^version' pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

All three should print the new version.

### Step 5: Commit

If there are unrelated uncommitted changes you've already cleared with the user, commit them **first** with their own message, then make a dedicated bump commit. Don't bury the version bump inside an unrelated commit.

```bash
git add pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore: bump version to X.Y.Z"
```

Use `chore:` for the bump commit — the substantive `feat:` / `fix:` commits should already exist from the work being released.

### Step 6: Push

```bash
git push origin main
```

If the push is rejected (non-fast-forward), stop. Do not force-push. Ask the user how to reconcile.

### Step 7: Report

One short line: new version, commit SHA, how many commits were pushed.

```
Released 5.3.0 (abc1234). Pushed 7 commits to origin/main.
```

## Quick Reference

| Step | Command / Action |
|------|------------------|
| 1 | `pytest -q` |
| 2 | `git status && git log --oneline origin/main..HEAD` |
| 3 | Pick patch / minor / major from diff |
| 4 | Edit `pyproject.toml`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` |
| 5 | `git commit -m "chore: bump version to X.Y.Z"` |
| 6 | `git push origin main` |
| 7 | Report new version + SHA |

## Common Mistakes

**Bumping before tests pass**
- **Problem:** Tagged release is broken on arrival.
- **Fix:** `pytest -q` is step 1, no exceptions.

**Only updating one or two version files**
- **Problem:** Marketplace shows stale version while plugin.json advanced; install-from-marketplace gets the wrong code.
- **Fix:** Always update all three; verify with the grep in Step 4.

**Patching when you removed a skill**
- **Problem:** Users upgrade and silently lose a skill they were invoking.
- **Fix:** Any rename or removal of a skill/command/hook is a major bump.

**Burying the bump in a `feat:` commit**
- **Problem:** History no longer answers "when did 5.2.0 ship?"
- **Fix:** Dedicated `chore: bump version to X.Y.Z` commit, separate from feature commits.

**Force-pushing on rejection**
- **Problem:** Overwrites someone else's pushed commits.
- **Fix:** Stop on rejection, ask the user, never `--force` without explicit instruction.

## Red Flags

**Never:**
- Bump without running tests.
- Use `sed -i` to edit version files.
- Force-push to `main`.
- Decide the bump from the commit message alone — read the diff.

**Always:**
- Run from the quirk repo root.
- Update all three version files together.
- State the bump level and reason before editing.
- Use a dedicated `chore:` commit for the bump.
