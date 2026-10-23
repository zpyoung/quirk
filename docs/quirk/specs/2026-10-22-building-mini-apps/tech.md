# Tech spec: `building-mini-apps`

**Status**: Reviewed · Logic spec: [logic.md](logic.md) · Tier gate fired: touches far more than 3 files across capture, docs, a registry and a gallery app.

All paths below are relative to `skills/building-mini-apps/` (`SKILL_ROOT`) unless they start with `tests/` or `.gitignore`.

## Architecture

Back-link: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| Path | Role |
|---|---|
| `SKILL.md` | Build flow and pattern index |
| `references/apps/<app>.md` | Study note per app (10) |
| `references/patterns/<pattern>.md` | Pattern reference (10) |
| `references/media/<app>/` | Captured frames. Gitignored |
| `gallery/` | A shadcn Vite app. Its `src/` holds the base and every block at the exact path an app receives them |
| `gallery/src/patterns/<pattern>/` | One block: `registry-item.json`, `index.ts`, `demo.tsx`, plus any other `.ts`/`.tsx` |
| `registry/base.registry-item.json` | Manifest for the base item (explicit file list) |
| `registry/registry.json` | Generated. Assembled by `scripts/build_registry.py` |
| `registry/r/<item>.json` | Generated. Built items that `shadcn add` installs; committed |
| `scripts/build_registry.py` | Assembles `registry.json`, runs `shadcn build`, and checks freshness |
| `scripts/new_app.py` | Scaffolds a mini app from the base plus named patterns |
| `scripts/add_patterns.py` | Adds patterns to an existing mini app |
| `scripts/check_docs.py` | Structural checker for study notes and pattern references |

Stack, all pinned and verified by prototype on 2026-10-22: Vite 8, React 19, TypeScript 6, Tailwind v4 through `@tailwindcss/vite`, shadcn CLI `4.22.1` with base `radix` and preset `nova`, and pnpm 10.

App slugs: `linear`, `things`, `raycast`, `craft`, `obsidian`, `tableplus`, `fantastical`, `notion`, `granola`, `figma`.
Pattern slugs: `list-peek`, `expand-in-place`, `action-palette`, `doc-collections`, `workspace-panes`, `staged-table-edit`, `mini-full`, `view-switcher`, `assisted-notes`, `inspector`.

Waves, the scaffold task and the final wave are defined by the in-session plan, not by this spec. Where this spec says "after the scaffold task", it means once the base, the gallery and its dependencies are committed.

## Capture

Back-link: [Data flow](logic.md#data-flow), [Decisions Locked](logic.md#decisions-locked).

- **Search:** `COMMAND: ~/.local/bin/yt-dlp "ytsearch8:<app> app walkthrough 2026" --flat-playlist --print "%(id)s|%(title)s|%(channel)s|%(upload_date)s|%(duration)s"`. Prefer official channels, then recent reviews under about 20 minutes.
- **Download** at most 3 videos per app, at 720p or lower, into the gitignored staging folder:
  `COMMAND: ~/.local/bin/yt-dlp -f "bv*[height<=720][ext=mp4]/b[height<=720]" -o "references/media/<app>/_video/<sourceID>.%(ext)s" <url>`
- **Extract** frames:
  `COMMAND: ffmpeg -i <video> -vf "select='gt(scene,0.3)',scale=1280:-1" -vsync vfr references/media/<app>/<sourceID>-%04d.png`
  - Tune the threshold per video: lower it when too few frames come out.
  - If scene detection yields fewer than 5 frames, use `fps=1` instead.
  - Delete `_video/` once extraction finishes.
- **Docs and public pages:** use `playwright-cli` to screenshot into `references/media/<app>/`. Only open pages that need no login.
- The agent views frames with its image-reading tool to write observations. Frame filenames stand in for timestamps when a frame comes from a page rather than a video.

## Code references

Back-link: [Key decisions & rationale](logic.md#key-decisions--rationale).

Verified shadcn behavior, from the prototype at shadcn 4.22.1:

- `shadcn init -t vite -n <name> -b radix -p nova -y --no-monorepo` scaffolds with no prompts.
- `shadcn add <abs>/r/base.json <abs>/r/<p>.json -y` installs several local items in one call, adds their npm `dependencies`, installs shadcn `registryDependencies` by name, and skips existing files unless `--overwrite` is passed.
- `type: "registry:file"` with `target: "src/patterns/<p>/<file>"` places files exactly at that path.
- **Local items cannot depend on each other.** `./base.json` resolves against the app's cwd, `local:` is an unknown scheme, and a namespace requires a URL. So the base is always passed explicitly next to patterns, and `registryDependencies` lists shadcn component names only.

## Contracts & interfaces

### Base

Back-link: [Conceptual model](logic.md#conceptual-model). These are the files the base registry item ships. Each `gallery/src/...` path is also its target in an app:

- `src/styles/mini-tokens.css`: the house style. It overrides shadcn's CSS variables using the selectors `html:root` and `html.dark`. Those beat shadcn's `:root` and `.dark` on specificity, so the tokens win regardless of where they appear in the cascade. It must not set brand colors from any studied app.
  - **Wiring:** insert `@import "./styles/mini-tokens.css";` immediately after the last top-level `@import` line in `src/index.css`. An `@import` must precede other rules, so it is never appended at the end.
- `src/lib/mini/store.ts`:
  `CONTRACT: useCollection<T extends { id: string }>(name: string, seed?: T[]): { items: T[]; status: "loading" | "ready" | "error"; error?: Error; add(item: T): Promise<void>; update(id: string, patch: Partial<T>): Promise<void>; remove(id: string): Promise<void>; replaceAll(items: T[]): Promise<void> }`
  `CONTRACT: exportAll(): Promise<string>; importAll(json: string): Promise<void>`
  - Backed by `idb-keyval`.
  - **Seed:** `seed` is written only when no stored value exists for `name`. An existing collection, even an empty one, is never reseeded.
  - **Shared state:** every component using the same `name` sees the same items, and a write through one updates all.
  - **Missing id:** `update` or `remove` on an id that isn't there is a no-op that resolves.
  - **Write failure:** the promise rejects with the storage error, and `status` stays `ready` so the UI keeps the last good items. The caller surfaces the error, for example as a toast.
  - **Load failure:** `status` becomes `error` and `error` is set.
  - **Export:** `exportAll` returns `{"version":1,"collections":{"<name>":[...]}}`.
  - **Import:** `importAll` validates that shape first. Invalid JSON, a wrong `version`, or a non-array collection makes it reject and write nothing. On success, the imported collections replace those names, and others are untouched.
- `src/components/mini/app-shell.tsx`: `CONTRACT: AppShell(props: { title: string; sidebar?: ReactNode; toolbar?: ReactNode; children: ReactNode })`, with light/dark following the OS by default.
- `src/components/mini/states.tsx`: `CONTRACT: EmptyState({ title, description?, action? })`, `LoadingState({ label? })`, `ErrorState({ error: Error; onRetry?: () => void })`.
- Keyboard layer: the base declares the npm dependency `react-hotkeys-hook`, and patterns call its `useHotkeys` directly. Bindings must not fire while focus is in an input, textarea or contenteditable unless the pattern states it does, as action-palette's ⌘K does.

### Pattern block

Back-link: [Behavior & scenarios](logic.md#behavior--scenarios).

- `registry-item.json`:
  `SCHEMA: { "name": "<pattern slug>", "title": string, "description": string, "dependencies"?: string[], "registryDependencies"?: string[] }`. There is no `files` key; the build script derives it.
- `index.ts` re-exports the block's public components and types.
- `demo.tsx` default-exports `Demo`, a self-contained demo with sample data that uses the base store and states. It ships to apps as the worked example the agent adapts.
- A block imports only the following: React, its own folder, base files, shadcn components from the pre-installed list below, and its declared `dependencies`. It never imports another pattern.
- Every block renders an empty, a loading and an error state, using the base state components.
- Pre-installed shadcn components in the gallery: button, input, textarea, label, badge, separator, tooltip, kbd, card, skeleton, command, dialog, sheet, popover, dropdown-menu, context-menu, tabs, table, scroll-area, resizable, select, checkbox, calendar, sonner, collapsible, toggle-group. A block needing anything else, npm or shadcn, reports `NEEDS_CONTEXT` rather than editing `gallery/package.json`.

### Scaffold dependencies

The scaffold task installs everything blocks may use, because `gallery/package.json` is frozen afterward:

- the shadcn components listed above;
- `idb-keyval` and `react-hotkeys-hook`, which `registry/base.registry-item.json` also declares as `dependencies` (its `name` is `base`, so the build emits `registry/r/base.json`);
- `react-markdown`, for the gallery only.

`.gitignore` also gains `skills/building-mini-apps/gallery/dist/` and `*.tsbuildinfo`.

### Scripts

Back-link: [Data flow](logic.md#data-flow), [Behavior & scenarios](logic.md#behavior--scenarios).

All scripts run with python3 3.9 or later (no `match`, and `from __future__ import annotations` for `X | Y` hints), use the standard library only, and execute from any cwd.

- `build_registry.py [--check]`
  - Without flags, it writes `registry/registry.json` and then runs `pnpm dlx shadcn@4.22.1 build ../registry/registry.json --output ../registry/r` with cwd `gallery/`.
  - For the base, it reads `registry/base.registry-item.json` with its explicit `files`.
  - For each block, it reads `gallery/src/patterns/*/registry-item.json` and adds every `.ts`/`.tsx` file in that folder as `registry:file` with `target` `src/patterns/<p>/<file>`. Paths in `registry.json` are relative to `gallery/`.
  - `--check` makes no writes and needs no network. It exits 1, naming each item, if any `registry/r/<item>.json` is missing or its file contents differ from the sources. Otherwise it exits 0.
- `new_app.py <target_dir> [--patterns <p1,p2,...>]`
  - It runs init in `<target_dir>`'s parent with `-n <basename>`, then `add` with the base and the patterns by absolute path to `registry/r/`.
  - It then wires the tokens import as the Base section specifies, unless it's already present.
  - It runs `pnpm build`.
  - It starts `pnpm dev`, waits up to 30 s for a line containing `Local:`, then stops the process.
  - `--patterns` is optional. Omitting it installs the base alone (SC-2).
  - Exit 2, checked before any command runs, for any of these:
    - an unknown pattern;
    - a `<target_dir>` that already exists;
    - a missing parent directory for `<target_dir>`.
  - Exit 1 if a step fails, naming that step (`init`, `add`, `tokens`, `build` or `dev`).
  - Exit 0 on success, printing the app path and the patterns.
- `add_patterns.py <app_dir> --patterns <p1,...>` (SC-3)
  - It runs `shadcn add` with the base and the named patterns into an existing app. Existing files are skipped, so base files are left alone.
  - It then rebuilds and runs the same `pnpm dev` check.
  - Exit 2 if `<app_dir>` has no `components.json` or a pattern is unknown, and exit 1 if a step fails.
- `check_docs.py study <app>` / `check_docs.py pattern <pattern>`
  - It exits 1 and lists every missing required heading or empty section, and exits 0 otherwise.

### SKILL.md

Back-link: [Behavior & scenarios](logic.md#behavior--scenarios).

**Frontmatter description:**
- Triggers on a small local app the user will keep and run, such as "build me a mini app", "a little app to track…" or "local tool with saved data".
- Excludes single-file HTML pages, reports and dashboards. Those belong to `writing-html-artifacts`, whose tier 2 also builds React but bundles to one file.

**Required sections, in order:**
- **When to use** (with the boundary against `writing-html-artifacts`).
- **Pattern index**: a table of the ten slugs, a one-line description, studied-from app, and a link to the reference.
- **Building a new app** (SC-1): read the matching references, name the chosen patterns and why, run `new_app.py`, adapt `demo.tsx` and the store names to the domain, and report the path, patterns and build/dev result.
- **When no pattern fits** (SC-2): offer the base alone, and list the nearest patterns with why each falls short.
- **Adding a pattern** (SC-3): run `add_patterns.py`, then wire the new block into the existing keyboard layer and store.
- **Rules**: one neutral house style, no brand assets, data in the browser by default.

`SKILL_DIR` is the folder holding `SKILL.md`, and script paths are built from it, the same convention `writing-html-artifacts` uses.

### Gallery

Back-link: [Key decisions & rationale](logic.md#key-decisions--rationale), SC-6 and SC-7.

- Hash routes at `#/<pattern>`. The nav comes from `import.meta.glob('./patterns/*/demo.tsx')`, so no shared list file exists.
- The reference panel loads `references/patterns/<p>.md` with `import.meta.glob(..., { query: '?raw', import: 'default' })` and renders it with `react-markdown`, which is a gallery-only dependency. `vite.config.ts` `server.fs.allow` includes `SKILL_ROOT`.
- `src/index.css` imports `./styles/mini-tokens.css`.
- `pnpm build` (`tsc -b && vite build`) compiles every block, so a broken block fails the build (SC-6).

## Data models / schemas

Back-link: [Data flow](logic.md#data-flow).

**Study note**, `references/apps/<app>.md`. Required `##` headings, in this order:

- **Sources**: a table with columns `ID | URL | Kind (official/third-party) | Date | Shows`. At least 2 rows.
- **Observations**: one bullet each, carrying a source ID, then a timestamp or frame filename, then the observation, then the patterns it feeds.
- **Unseen**: the interactions no public source showed, or "None".
- **Patterns fed**.

Frames are named `references/media/<app>/<sourceID>-<seconds or slug>.png`. Cap them at about 60 per app.

**Pattern reference**, `references/patterns/<pattern>.md`. Required `##` headings, in this order:

- **When to use**: also says when not to.
- **Anatomy**: a text diagram in a code block.
- **Interaction**: a keys table, focus rules, and empty, loading, error and long-content states.
- **Borrow / Leave out**
- **Block API**: exports and props of `index.ts`.
- **Sources**: links to the study-note observations.

## DO-NOT-CHANGE fences

- Everything outside `skills/building-mini-apps/`, `tests/test_building_mini_apps_skill.py`, `tests/test_writing_specs_skill.py`, `.gitignore` and `README.md`. Other skills and their tests are another feature's surface, and the full suite gates on them.
  - `README.md` may change only by bumping the `**N skills**` count and adding one line for this skill. Three existing tests assert the count.
  - `tests/test_writing_specs_skill.py` may change only by excluding `node_modules` from `test_no_stale_skill_name_references`'s `rglob`. A local `pnpm install` in `gallery/` otherwise makes it read every dependency README.
- `gallery/package.json` and `gallery/pnpm-lock.yaml` after the scaffold task. Pattern tasks run in parallel, so a dependency change by one would collide with the others.
- `gallery/src/components/ui/**` after the scaffold task. These are generated shadcn files, and the pre-installed set is the contract the blocks build against.
- Base contracts after wave 1. Ten blocks build on them concurrently.

## Always / Ask / Never

- **Always:**
  - Keep frames out of git.
  - Cite a source ID for every observation.
  - Run `pnpm build` in `gallery/` before reporting a block done, and confirm `pnpm dev` reaches `Local:`.
  - Use the base store and state components.
- **Ask (via `NEEDS_CONTEXT`):**
  - A new npm or shadcn dependency.
  - A login wall that hides a pattern's core interaction (SC-5).
  - A base contract that doesn't fit a pattern.
- **Never:**
  - Commit media.
  - Use a studied app's logo, icon set, font, illustration or copy.
  - Create accounts.
  - Make one pattern import another.

## Cross-cutting

- **Legal and visibility:** quirk is public, so frames stay in the gitignored `references/media/`, and the house style keeps brand colors out.
- **Network:** `new_app.py` and `build_registry.py` without `--check` need the network for npm. The tests use only `--check` and argument validation.
- **Disk:** videos are deleted after frame extraction.

## Testing strategy

Back-link: [Behavior & scenarios](logic.md#behavior--scenarios).

`tests/test_building_mini_apps_skill.py`, written in the final wave, must cover:

- `SKILL.md` frontmatter: `name`, plus a `description` that carries the trigger phrases "mini app" and "build me".
- Every study note and pattern reference passing `check_docs.py`.
- The checker detecting a missing heading, so a broken harness can't pass.
- `build_registry.py --check` passing, and failing after a source byte is changed in a temp copy.
- Every pattern having `registry-item.json`, `index.ts` and `demo.tsx`.
- `new_app.py` exiting 2 on an unknown pattern, an existing target, and a missing parent, with no subprocess run.
- `add_patterns.py` exiting 2 when there's no `components.json`.
- `SKILL.md` having the required sections and linking every pattern reference.
- `.gitignore` covering `references/media/`.

Acceptance bar: `python3 -m pytest -q` is green, and `pnpm build` in `gallery/` is clean.

## Non-goals

Back-link: [Scope & non-goals](logic.md#scope--non-goals). This spec excludes:

- Playwright tests of the blocks.
- Visual diffing.
- Hosting the registry.
- A CI job for `pnpm build`, since the repo CI is Python-only.
- Native builds.
