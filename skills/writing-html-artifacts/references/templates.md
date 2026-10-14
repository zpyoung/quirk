# Templates

Everything this skill builds comes from a template, so a project's own template gets every guarantee a built-in one has. Read this when matching a request to a template, writing a `.src.html` source file, or creating or repairing a custom template. For the design rules a template's slots follow, see [design reference](design-reference.md). For companion screens, which are built from the `companion` template, see [companion](companion.md).

## What a template is

A template is a directory holding a manifest (`template.json`), fixed chrome, one to three freeform slots, and a filled-in example that doubles as its verify fixture. It can also hold token overrides, a rules addendum, and extra vendored libraries.

- **Chrome** is fixed: theme, theme toggle, license notices, header. You do not write it.
- **Slots** are the freeform regions you fill. Consistency comes from the shared chrome and tokens.
- Built-ins are `report`, `components`, `companion` and `app` (tier 2). Custom templates live at project or user level and can be either tier.

## Lookup order and name clashes

The lookup order is project, then user, then built-in. All paths are relative to the root named:

1. Project: `<project>/.quirk/html-templates/<name>/` (committed with the repo)
2. User: `~/.quirk/html-templates/<name>/`
3. Built-in: `templates/<name>/` under the skill directory

- A name that exists at two levels resolves to the higher level. The project `report` hides the built-in `report`.
- The first valid match wins. An invalid match is skipped with a warning and the search continues down the order. No valid match at any level is an error (exit 2).
- Run `scripts/quirk_html.py templates list [--project-dir DIR]` to see every template that resolves (`name`, `level`, `tier`, `description`, `path`) and every one that was skipped (`warnings`).
- Match the request against each `description`; every description starts "Use when". Then say which template you picked, its level, and the tier before you build. The user can name a template directly.

## `template.json`

```json
{
  "schema": 1,
  "name": "report",
  "description": "Use when the user wants a branded report, explainer, or small tool as a single page.",
  "tier": 1,
  "libraries": ["simple-css", "alpine"],
  "optional_libraries": ["chartjs", "mermaid"],
  "slots": { "main": { "required": true, "description": "The report body" } },
  "skeleton": "skeleton.html",
  "tokens": "tokens.json",
  "rules": "rules.md",
  "example": "example.src.html"
}
```

| Field | Rule |
|---|---|
| `schema` | integer, only `1` is valid |
| `name` | must equal the directory name; `[a-z0-9-]{1,40}` |
| `description` | 30 to 400 characters, starts with "Use when"; this is what requests are matched against |
| `tier` | `1` (assembled single file) or `2` (React project bundled to one file) |
| `libraries` | tier 1: libraries always inlined, in order; names from the skill's `vendor/libraries.json` or from this template's own `vendor/libraries.json` |
| `optional_libraries` | tier 1: libraries a source file may add through its header's `libraries` field |
| `slots` | tier 1: 1 to 3 entries, each `{"required": bool, "description": str}` |
| `skeleton` | tier 1: relative path to the skeleton HTML |
| `tokens` | optional: relative path to a token file layered last (see below) |
| `rules` | optional: relative path to a design-rules addendum, read with the design reference |
| `example` | tier 1: a `.src.html` source file; tier 2: a directory overlay copied over the scaffold |
| `project` | tier 2 only: relative path to a Vite project containing `package.json` and `pnpm-lock.yaml` |

- A library name resolves first in the template's `vendor/libraries.json`, then in the skill's. A template-level entry with a built-in's name shadows it for that template only.
- Skeletons contain literal placeholders, each replaced once: `{{header}}`, `{{title}}`, `{{head}}`, `{{chrome}}`, `{{slot:<name>}}` for each declared slot, `{{data}}` (optional), `{{body_end}}`. A skeleton missing any of them except `{{data}}` is invalid. An unknown `{{...}}` left after substitution is exit 2.
- Libraries load in manifest order, with Alpine last.

## Source file format

For a tier-1 template you write `<slug>.src.html`, and `scripts/quirk_html.py build SRC.html` builds it to `.quirk/html/<slug>.html`. The format:

- Line 1 is a header comment holding one JSON object.
- Each slot starts with a line that is exactly `<!-- slot: <name> -->` and runs to the next slot line or end of file.
- Text before the first slot line, other than the header, is an error.

```html
<!-- quirk-src {"template": "report", "title": "Test timings, week 41", "mode": "offline", "libraries": ["chartjs"], "interactions": ["sort the table by column"], "data": "timings.json"} -->
<!-- slot: main -->
<h1>Test timings, week 41</h1>
<p>Median suite time fell from 14 to 9 minutes.</p>
```

Header fields:

- `template` and `title` are required.
- `mode` is `offline` (the default) or `connected`.
- `libraries` must be a subset of the template's `optional_libraries`. The builder adds `kit` and `chartjs` automatically when `q-*` tags appear, so `kit` may not be listed by hand.
- `interactions` lists what the page lets the reader do; it may be empty.
- `data` is an optional JSON or CSV path relative to the source file. Data too large to embed moves to a sidecar file next to the page.
- `tier_reason` is optional; set it when you overrode the tier signals.

Slot names match `^<!-- slot: ([a-z][a-z0-9-]{0,30}) -->$`. A rebuild of an existing artifact reuses the library versions recorded in its header; pass `--upgrade` to use the current pins.

## Tokens and the four-layer merge

A token file has `schema: 1` and the groups `color`, `font`, `size`, `space`, `radius`. Every color is a `["<light>", "<dark>"]` pair; a single string is invalid. Fonts are system stacks only, with no `@font-face` and no `url()` fonts.

```json
{
  "schema": 1,
  "color": { "accent": ["#0b5cad", "#7ab8ff"], "accent-text": ["#ffffff", "#0b1b2e"] },
  "radius": { "md": "8px" }
}
```

Layers merge in this order, and a later layer wins per key:

1. House tokens (`theme/house.tokens.json` in the skill)
2. User `~/.quirk/html-templates/tokens.json`
3. Project `.quirk/html-templates/tokens.json`
4. The template's own `tokens` file

- Layers 2 and 3 are how project branding reaches the built-in templates, the companion included. Put brand tokens there when a whole project should be branded, and in a template's own file only when that template differs.
- A token file only needs the keys it changes.
- Tier-2 builds apply the same four layers: each build rewrites `src/quirk-tokens.css` in the app's source folder, and the scaffold's `theme.css` imports it. Change tokens in a layer file, not in `quirk-tokens.css`.
- Output uses `--q-<group>-<key>` names, with light values on `:root` and dark values under the `prefers-color-scheme` media query and under `[data-theme="dark"]`. Slot content references the variables, per [design reference](design-reference.md). The house tokens include the chart series colors `--q-color-chart-1` to `--q-color-chart-8`.

## `verified.json`

Custom templates (project and user level) need a `verified.json` beside `template.json`. Built-ins do not.

```json
{ "schema": 1, "verified_at": "2026-10-13T12:00:00Z", "browser": true, "hashes": { "template.json": "<sha256>", "skeleton.html": "<sha256>" } }
```

- For tier 1, `hashes` covers `template.json`, the skeleton, tokens, rules, every file under `vendor/`, the example, and the example's `data` file when its header names one inside the template.
- For tier 2 it covers `template.json`, every file under `project/` and every file under the `example/` directory, in each case except `node_modules` and `dist`.
- `browser` is `false` when the example passed static checks but no browser was reachable.
- Do not write it by hand. `templates verify` writes it, and only when the example passes. Editing any covered file afterwards invalidates it, so re-run verify.

## Create flow

Creating a template is guided and ends when the example passes.

1. Choose the level: `project` for a template the repo shares, `user` for one that follows the person.
2. Scaffold it:

   ```
   scripts/quirk_html.py templates new NAME --level project|user [--base TEMPLATE] [--from ARTIFACT.html] [--project-dir DIR]
   ```

   It prints `{"path", "next": [...]}`; do what `next` lists.
   - `--base` copies an existing template as the starting point. The built-in `companion` template is refused: its example is a screen, not a page source.
   - `--from` starts from a built artifact. A quirk-built artifact copies its source template and uses its `.src.html` as the example. Any other HTML becomes a one-slot skeleton (`main` wraps the body) with house tokens, which you then refine.
3. Edit `template.json` (write a real "Use when" description), the skeleton, tokens, rules and the example. Keep the example a real, filled-in page, because verify runs on it.
4. Optionally check the shape: `scripts/quirk_html.py templates validate PATH` prints `{"valid", "errors"}`.
5. Verify it:

   ```
   scripts/quirk_html.py templates verify NAME [--project-dir DIR]
   ```

   It builds the example, runs the static checks and browser verify, and on a pass writes `verified.json`. The result is `{"passed", "browser", "report"}`. Fix what `report` lists and run it again.

The template is usable only once `templates verify` passes. A project template belongs in version control, including `verified.json`.

## Tier-2 custom templates

A tier-2 template sets `"tier": 2` and `"project": "project/"`, and ships its own `project/package.json` and `project/pnpm-lock.yaml`.

- The lockfile is required, and dependencies are exact-pinned. Builds run `pnpm install --frozen-lockfile --ignore-scripts --ignore-pnpmfile`, so a missing or stale lockfile fails the build and no package script or pnpmfile hook runs at install.
- Building a tier-2 template runs its build code (`vite.config.ts` and the build script). Only build project or user tier-2 templates you trust.
- Build with `scripts/quirk_html.py build-app SLUG --title TITLE`. If Node or pnpm is missing, or install or build fails, it exits 3 and you fall back to a tier-1 build, listing every cut in the delivery note.
- Never commit `node_modules/`.

## What makes a template invalid

A template is skipped, with a warning, when:

- `template.json` is missing, unparseable, or fails the schema table above (this includes `name` not matching the directory)
- the skeleton is missing or lacks a required placeholder
- a library does not resolve, or a vendored file's checksum does not match
- the example is missing
- `verified.json` is missing, or any covered file's hash differs (reason `unverified`)

What you see: `templates list` reports it under `warnings` as `{name, level, path, reason}`, and the build result carries the same warning. The build then uses the next valid match in lookup order, often the built-in of the same name.

What you do:

- Tell the user in the delivery note which template was skipped, where it was, and why, and name the template you used instead.
- Offer to repair it. For `unverified`, edit nothing and run `templates verify NAME`; for any other reason, fix the named file first.
- Do not silently build with the fallback and say nothing, and do not edit `verified.json` to clear the warning.
