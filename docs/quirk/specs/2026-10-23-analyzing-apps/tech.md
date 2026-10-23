# Tech spec: analyzing an app for `building-mini-apps`

**Status**: Reviewed · Logic spec: [logic.md](logic.md) · Tier gate fired: touches more than 3 files (guide, SKILL.md, two scripts, tests).

All paths are relative to the repo root unless absolute. `SKILL` below means `skills/building-mini-apps/`.

## Architecture

Back-link: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| File | Change | Role |
|---|---|---|
| `SKILL/references/analyzing-apps.md` | new | The guide the agent follows for "analyze <app> as a mini app" |
| `SKILL/SKILL.md` | modify | New `## Analyzing an app` section; description trigger; one build-flow line about blueprints |
| `SKILL/scripts/capture.py` | new | `preflight`, `search`, `video` subcommands wrapping git, yt-dlp and ffmpeg |
| `SKILL/scripts/check_docs.py` | modify | Names derived from files on disk; new `blueprint` and `observations` kinds |
| `tests/test_building_mini_apps_skill.py` | modify (additions only) | check_docs coverage for the new kinds and the growing app list |
| `tests/test_building_mini_apps_capture.py` | new | capture.py contracts, no network |
| `tests/test_building_mini_apps_analyzing.py` | new | SKILL.md section, description trigger, guide existence and links |
| `SKILL/references/apps/sentry.md`, `SKILL/references/blueprints/sentry.md` | new, acceptance run | Output of running the guide on Sentry through Stop 2 |

Python 3 stdlib only. `capture.py` shells out to `git`, `yt-dlp` and `ffmpeg`. Playwright screenshots are taken with `playwright-cli` directly, as documented in the guide, not wrapped.

## Code references

Back-link: [Key decisions & rationale](logic.md#key-decisions--rationale).

- `SKILL/scripts/check_docs.py`: `SKILL_ROOT`, `APPS`, `PATTERNS`, `KINDS`, `HEADING_RE`, `TABLE_ROW_RE`, `sections(text)`, `check(kind, name)`, `main(argv)`. Exit 0 ok, 1 problems (each printed as `<kind> <name>: <problem>`), 2 usage.
- `SKILL/scripts/_mini.py`: `usage_error(message) -> 2`, `SKILL_ROOT`. Style reference for capture.py: module docstring states usage and exit codes; `main(argv: list[str] | None = None) -> int`; `argparse` as in `new_app.py:75`.
- `tests/test_building_mini_apps_skill.py`: helpers `_run_script(script, *args)`, `_copy_skill(dest)` (copies SKILL minus `node_modules` and `media`), `_missing_sections(text)`, `REQUIRED_SECTIONS`, fixed `APPS` and `PATTERNS` lists.
- Capture commands from the first study, `docs/quirk/specs/2026-10-22-building-mini-apps/tech.md` § Capture: search `ytsearch8:<app> app walkthrough 2026 --flat-playlist --print "%(id)s|%(title)s|%(channel)s|%(upload_date)s|%(duration)s"`; download `-f "bv*[height<=720][ext=mp4]/b[height<=720]"`; extract `select='gt(scene,0.3)',scale=1280:-1` with `-vsync vfr`; fall back to `fps=1` under 5 frames.
- `.gitignore:18` ignores `skills/building-mini-apps/references/media/`, so `_video/` and `_staging/` under it are ignored too.

## Contracts & interfaces

Back-link: [Data flow](logic.md#data-flow), [Behavior & scenarios](logic.md#behavior--scenarios).

### `check_docs.py`

```
CONTRACT: check_docs.py study <app> | pattern <pattern> | blueprint <app>
CONTRACT: check_docs.py observations <app> <bullets_file> [--frames]
```

- **Names come from disk.** `study` accepts any `<app>` with `SKILL/references/apps/<app>.md`; `pattern` any `<pattern>` with `SKILL/references/patterns/<pattern>.md`; `blueprint` any `<app>` with `SKILL/references/blueprints/<app>.md` **and** a study note. A name with no file exits 1 with `missing file <path>` (or `no study note for <app>` for a blueprint). The fixed `APPS` / `PATTERNS` tuples go away. Names must match `REGEX: ^[a-z0-9][a-z0-9-]*$`, else exit 2.
- **`study` and `pattern` behave exactly as today** on the existing 20 documents.
- **`blueprint <app>`** problems (each one printed, exit 1 if any):
  - Required `##` headings, in order: `Core jobs`, `Screens`, `Coverage`, `Composition`, `Proposed patterns`, `Proposed revisions`. Each non-empty; `None` is a valid body for the two Proposed sections.
  - `Core jobs` holds a table `ID | Job | State`, at least one row; IDs match `REGEX: ^J[0-9]+$` and are unique; State is one of `proposed`, `confirmed`, `covered`.
  - `Coverage` holds a table `Row | Mark | Pattern | Evidence`. The Row cell starts with a job ID (`J3`) or the word `Screen:`. Mark is one of `matched`, `approximated`, `left out`.
  - Every job whose State is `confirmed` or `covered` has at least one Coverage row starting with its ID followed by a word boundary, so `J1` does not match `J10`.
  - Table header rows (`| ID | Job | State |`, `| Row | Mark | ...`, and the study note's `| ID | URL | ...`) are skipped. `TABLE_ROW_RE` already skips separator rows but not headers.
  - Each Evidence cell holds at least one citation. A citation is a frame filename matching `REGEX: [A-Z][0-9]+-[A-Za-z0-9_-]+\.png` that appears in the study note's `## Observations` text, or a source ID matching `REGEX: \bS[0-9]+\b` that is a row in the study note's `## Sources` table. The literal `unseen` is allowed only when Mark is `left out`. Any citation that does not resolve is a problem naming it.
- **`observations <app> <bullets_file>`** checks a capture subagent's staged result before the coordinator appends it. Each non-blank line must be a bullet `- S<n>, ...` or a trailing `Unseen: <text>` line (non-empty text; not checked for sources or frames). A bullet's source ID must be a row in the study note's Sources table. With `--frames`, every frame path the bullet cites (`references/media/<app>/<file>.png`) must exist under `SKILL`. It prints each failing line's number and reason and exits 1 if any fail, 0 if all are clean. It never edits either file.

### `capture.py`

```
CONTRACT: capture.py preflight
CONTRACT: capture.py search <app> [--query TEXT] [--limit N]
CONTRACT: capture.py video <app> <source_id> <url> [--threshold FLOAT]
```

Exit 0 ok, 1 a named failure, 2 usage (bad args, `source_id` not matching `REGEX: ^S[0-9]+$`, app not matching the name regex above).

- **Tool lookup.** `yt-dlp` resolves from `CONFIG: CAPTURE_YTDLP` env, else `PATH`, else `~/.local/bin/yt-dlp`; `ffmpeg` from `CONFIG: CAPTURE_FFMPEG`, else `PATH`; `playwright-cli` from `CONFIG: CAPTURE_PLAYWRIGHT`, else `PATH`. The env overrides exist for tests.
- **`preflight`** prints one line per check and exits 1 if any fail: `SKILL_ROOT` is inside a git work tree (`git -C SKILL_ROOT rev-parse --show-toplevel` succeeds), `SKILL_ROOT/references` is writable, and each of the three tools resolves. The git failure message says the skill must run from a quirk checkout, not an installed plugin copy (SC-2).
- **`search`** runs yt-dlp's flat-playlist search (default query `<app> app walkthrough <current year>`, default limit 8) and prints the `id|title|channel|upload_date|duration` lines unchanged.
- **`video`** downloads to `SKILL/references/media/<app>/_video/`, extracts frames into `SKILL/references/media/<app>/`, prints each frame's path relative to `SKILL` (`references/media/<app>/S1-t0042.png`, the form bullets cite), and **always deletes `_video/`** before exiting: on success, on download failure, and on extraction failure.
  - Frames are named `<source_id>-t<SSSS>.png`, where `SSSS` is the frame's whole-second timestamp, zero-padded to 4 digits. When two frames fall in the same second, keep the first. This matches the existing notes (`S1-t0042.png`). ffmpeg's index-numbered output carries no timestamp, so take each frame's `pts_time` from the `showinfo` filter's stderr lines and rename the indexed files to match.
  - Scene detection runs at `--threshold` (default 0.3) and scales to 1280 wide. Under 5 frames, it reruns at `fps=1` instead and replaces the scene frames.
  - It never overwrites an existing frame with a different source ID, and it never touches files outside `references/media/<app>/`.

### The guide, `references/analyzing-apps.md`

Back-link: [Data flow](logic.md#data-flow), [Decisions Locked](logic.md#decisions-locked).

Required `##` sections, in order: `When this runs`, `Preflight`, `Core jobs (Stop 1)`, `Survey`, `Capture`, `Blueprint (Stop 2)`, `Building approved proposals`, `Resuming a run`, `Rules`. It must:

- Quote the exact `capture.py` and `check_docs.py` commands, with `$SKILL_DIR` as SKILL.md does.
- Carry the capture subagent brief inline: one source per subagent; write bullets to `references/media/<app>/_staging/<source_id>.md`; bullet format below; trigger empty, error, loading, hover, focus and keyboard states on purpose in a live demo; mark what the source can't show; no logins.
- State the coordinator's merge step: run `check_docs.py observations <app> <staged> --frames`, append only clean lines to the study note's `## Observations`, then rerun or record as Unseen any failing ones.
- State both stops as `orca ask` questions when the host has it, else as plain questions in chat, and that the run ends its turn at each stop.
- For "Building approved proposals", state that each new pattern goes through the reference-then-block flow, then `build_registry.py`, the pattern index row in SKILL.md, and the pattern lists in `tests/test_building_mini_apps_skill.py`; and that revisions keep the Block API backward compatible.
- Carry these rules in its `## Rules` section:
  - A clone matches screens, layout, navigation, keys and states, and keeps the house style.
  - No brand assets, and the clone's UI never names the studied app.
  - A component needed by two patterns is copied into each block; no cross-pattern imports.
  - Dependencies are proposed in the blueprint, approved at Stop 2, and land in that pattern's registry item only.
  - Public no-login demos only; ask before any signup.
  - No capture cap; coverage is the stop.
  - Frames are never committed.
  - A gap pattern is named for the interaction, and its When to use fits another app.
- In the capture brief, state the login-wall steps (SC-3): record the job as Unseen with the reason, have the coordinator ask about signup, and carry on with the other sources.

### SKILL.md changes

Back-link: [Key decisions & rationale](logic.md#key-decisions--rationale).

- The frontmatter description adds the phrase `analyze <app> as a mini app` and keeps `build me` and `mini app`.
- `## Analyzing an app` goes between `## Adding a pattern` and `## Rules`: the trigger, the two stops, the output files, and a link to `references/analyzing-apps.md`. Keep it under about 15 lines.
- `## Building a new app` step 1 gains one sentence: for a clone of an analyzed app, read `references/blueprints/<app>.md` first and use the patterns it names.
- In `## Rules`, "No brand assets" gains that a clone's UI never names the studied app. "Ask before adding dependencies" gains that approval at an analysis's Stop 2 counts. The intro line "The patterns copy how well-known apps behave, not how they look" stays.

## Data models / schemas

Back-link: [Conceptual model](logic.md#conceptual-model).

**Staged observation bullet** (one per line, in `_staging/<source_id>.md` and then in the study note):

```
SCHEMA: - <source_id>, `references/media/<app>/<frame>.png`: <observation> → feeds: <pattern slugs or proposed slugs>; jobs: <J ids>
SCHEMA: - <source_id>, text of <url or page section>: <observation> → feeds: <...>; jobs: <...>
```

The second form is for text-only sources and cites no frame.

**Blueprint**, `references/blueprints/<app>.md`:

```
SCHEMA: ## Core jobs        table: ID | Job | State          (State: proposed | confirmed | covered)
SCHEMA: ## Screens          one bullet per screen or state: name, what it shows, jobs it serves
SCHEMA: ## Coverage         table: Row | Mark | Pattern | Evidence
SCHEMA: ## Composition      shell layout, shared collections (useCollection names), key map across patterns, domain model fields
SCHEMA: ## Proposed patterns   per proposal: slug, interaction, When to use (non-<app> example), components, dependencies + reason; or "None"
SCHEMA: ## Proposed revisions  per proposal: pattern, additive change, evidence; or "None"
```

Run state lives in Core jobs' State column. `proposed` means the run is at Stop 1. `confirmed` means capture is under way. `covered` means the job's flow and states have evidence or Unseen entries. A resumed run reads this column and the Sources table, and does not trust chat history.

## DO-NOT-CHANGE fences

Back-link: [Decisions Locked](logic.md#decisions-locked).

- `SKILL/references/patterns/*.md`, `SKILL/gallery/**`, `SKILL/registry/**`: no pattern changes this run. Proposals are built only after Stop 2, in a later run.
- `SKILL/references/apps/<the ten>.md`: the bullet `jobs:` suffix is for new notes only. The ten stay valid without it.
- Existing tests in `tests/test_building_mini_apps_skill.py`: add, never edit or delete. They are the regression guard for the 20 existing documents and the scripts' current CLI.
- `check_docs.py`'s existing CLI, output line format and exit codes. The test suite and the first spec's tech.md depend on them.
- Everything outside `SKILL/`, the three test files and `docs/quirk/specs/2026-10-23-analyzing-apps/`. Other skills' tests gate on their own files.

## Always / Ask / Never

Back-link: [Decisions Locked](logic.md#decisions-locked).

- **Always:** keep frames, videos and `_staging/` under the gitignored `references/media/`; delete `_video/` on every exit path; stdlib only; run `python3 -m pytest tests/test_building_mini_apps_skill.py tests/test_building_mini_apps_capture.py tests/test_building_mini_apps_analyzing.py -q` before reporting.
- **Ask (`NEEDS_CONTEXT`):** any need to touch a fenced path; any new third-party Python dependency.
- **Never:** network access in tests; commit a frame; let `capture.py` write outside `references/media/<app>/`.

## Cross-cutting

Back-link: [Scope & non-goals](logic.md#scope--non-goals).

- **Legal and visibility:** quirk is public. Media stays gitignored. Study notes and blueprints hold text only. A blueprint's domain model uses the app's real entities and field names (issues, events, releases), but no UI copy, product name or brand strings from the app.
- **Disk:** `_video/` deletion is the only cleanup. Frames remain locally as evidence, same as the first ten.

## Testing strategy

Back-link: [Behavior & scenarios](logic.md#behavior--scenarios).

- `tests/test_building_mini_apps_skill.py` (additions): `blueprint` passes on a valid fixture blueprint written into a `_copy_skill` tree next to an existing study note (cite `linear`'s real frames and source IDs); fails, naming the cause, on each of: a missing heading, a confirmed job with no coverage row, an unresolvable citation, `unseen` on a `matched` row, a bad State value. `study` passes for a new note added to the copy, which proves the list grows. `observations` passes clean bullets and flags an unknown source ID; with `--frames` it flags a missing frame and passes one created on disk. Name regex violations exit 2.
- `tests/test_building_mini_apps_capture.py`: uses fake `yt-dlp` and `ffmpeg` executables through the env overrides, inside a `_copy_skill` tree. Covers: frame naming `S1-t0042.png` from fake output; `_video/` removed after success, after a failing download, and after a failing extraction; the `fps=1` rerun when under 5 frames; usage exit 2 on a bad source ID; `preflight` exit 1 naming a missing tool and naming a non-git skill root. No network, and no real ffmpeg required. If the frame-timestamp design needs real ffmpeg, guard that one test with `pytest.mark.skipif(shutil.which("ffmpeg") is None)`.
- `tests/test_building_mini_apps_analyzing.py`: SKILL.md has `## Analyzing an app` between `## Adding a pattern` and `## Rules`, and links `references/analyzing-apps.md`; the description contains `analyze` and `as a mini app`; the guide exists with its required sections in order; every `$SKILL_DIR/scripts/<name>.py` the guide names exists.
- Acceptance bar: all three files pass, and the existing 58 tests still pass unchanged.

## Non-goals

Back-link: [Scope & non-goals](logic.md#scope--non-goals).

- Building any proposed pattern, or the Sentry clone.
- A wrapper around `playwright-cli`.
- Mechanically requiring a frame or `jobs:` suffix on every bullet, or tying Coverage `Screen:` rows to Screens bullets.
- Verifying states coverage mechanically. The guide asks for it, and `check_docs` checks only that each confirmed job has a cited coverage row.
