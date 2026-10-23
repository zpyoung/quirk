# Tech spec: `building-mini-apps` styles

**Status**: Reviewed · Logic spec: [logic.md](logic.md) · Tier gate fired: touches scripts, the gallery, all ten blocks and SKILL.md.

All paths are relative to `skills/building-mini-apps/` (`SKILL_ROOT`) unless they start with `tests/`,
`docs/` or `.gitignore`. `RUN_BASE` is commit `bc049c1` on `zpyoung/mini-app-styles`; line anchors are
at `RUN_BASE`. Stack and pins are unchanged from the
[building-mini-apps tech spec](../2026-10-22-building-mini-apps/tech.md#architecture).

## Architecture

Back-link: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

| Path | Role | New? |
|---|---|---|
| `styles/<slug>.json` | Style source, one per style (7) | new |
| `styles/dist/<slug>.css` | Generated app CSS per style; what an app receives as its tokens file. Committed | new |
| `gallery/src/styles/mini-tokens.css` | Becomes generated: byte-identical to `styles/dist/neutral-house.css`. Still the base item's tokens file | changed |
| `gallery/src/styles/gallery-styles.css` | Generated: every non-default style scoped under `html[data-mini-style="<slug>"]` | new |
| `gallery/src/gallery/style-list.json` | Generated: `[{slug, name}]` in display order, read by the picker | new |
| `gallery/src/gallery/style-picker.tsx` | Gallery top-bar picker | new |
| `scripts/_styles.py` | Shared style library: load and validate sources, render CSS, contrast math, header hash | new |
| `scripts/build_styles.py` | CLI: generate all outputs and run the contrast gate; `--check` for freshness | new |
| `scripts/set_style.py` | CLI: swap an existing app's style | new |
| `scripts/new_app.py` | Gains `--style` and a style step; `tokens_step` also rewires fonts | changed |
| `scripts/_mini.py` | Gains shared steps used by both `new_app.py` and `set_style.py` | changed |
| `scripts/check_docs.py` | Gains the `style` doc kind | changed |
| `references/styles/<slug>.md` | Style reference per style (7) | new |
| `gallery/src/components/mini/app-shell.tsx`, `gallery/src/patterns/**` | Gain `data-mini` hook attributes only | changed |
| `SKILL.md` | Style index, picking and announcing, `set_style.py`, replaced rules | changed |
| `tests/test_building_mini_apps_styles.py` | Tests for `_styles.py`, `build_styles.py`, `set_style.py`, the `new_app.py` style step | new |
| `tests/test_building_mini_apps_skill.py` | Gains style-reference and SKILL.md section checks | changed |

Style slugs, in display order: `neutral-house`, `calm-paper`, `airy-white`, `cool-tool`, `dense-dark`,
`glass-launcher`, `split-tone`. `neutral-house` is the default everywhere a style is optional.

All new Python is stdlib-only (no ColorAide, no tinycss), runs under the repo's Python 3.9+, and
follows `_mini.py`'s conventions: `usage_error` exits 2, `step_failed` exits 1.

## Code references

- `scripts/_mini.py:52` `usage_error`, `:61` `step_failed`, `:68` `run_step`, `:83` `add_step`,
  `:89` `build_step`, `:99` `dev_step`, `:21` `SHADCN`.
- `scripts/new_app.py:51` `tokens_step` (inserts the tokens `@import`), `:75` `main` (step tuple at `:92`).
- `scripts/add_patterns.py:40` step tuple.
- `scripts/check_docs.py:26` `KINDS`, `:46` `check`, `:74` `main`.
- `scripts/build_registry.py:103` `check`, `:118` `build`. `registry/base.registry-item.json:11-13`
  lists `src/styles/mini-tokens.css`.
- `gallery/src/index.css:4` imports `@fontsource-variable/geist`; `:5` imports `./styles/mini-tokens.css`;
  `:10` `--font-heading: var(--font-sans);` and `:11` `--font-sans: 'Geist Variable', sans-serif;` inside `@theme inline`.
- `gallery/src/App.tsx:90` renders `<AppShell ... toolbar={<ThemeToggle />}>`.
- `gallery/src/components/theme-provider.tsx:79` `ThemeProvider` toggles `light`/`dark` on `<html>`.
- `gallery/src/components/mini/app-shell.tsx:65` header, `:66` h1, `:67` toolbar, `:71` aside, `:75` main.
- `gallery/src/patterns/staged-table-edit/staged-table.tsx:72-73` `NEW_TINT` / `REMOVED_TINT` hard-code oklch.
- `tests/test_building_mini_apps_skill.py:28` `REQUIRED_SECTIONS`, `:52` `_load_script`, `:76` `no_subprocess`.

## Contracts & interfaces

The seven slugs live in one place, `CONFIG: _styles.SLUGS` (display order); `check_docs.py`,
`build_styles.py`, `new_app.py` and `set_style.py` import it.

### Hook vocabulary

Back-link: [Conceptual model](logic.md#conceptual-model).

`CONTRACT:` blocks expose exactly one attribute, `data-mini="<role>"`, with these roles. Selection
state stays as it is today (`aria-selected`, `aria-current`, `data-active`), so a style selects a row
with `[data-mini="row"][aria-selected="true"], [data-mini="row"][aria-current="true"], [data-mini="row"][data-active]`.

Paths in this table are under `gallery/src/`: `components/mini/` for the shell, `patterns/<pattern>/` for blocks.

| Role | Put it on |
|---|---|
| `shell-header` | `components/mini/app-shell.tsx:65` header |
| `shell-sidebar` | `components/mini/app-shell.tsx:71` aside |
| `shell-main` | `components/mini/app-shell.tsx:75` main |
| `title` | `components/mini/app-shell.tsx:66` h1; `patterns/doc-collections/record-page.tsx:107`, `patterns/workspace-panes/pane.tsx:57`, `patterns/mini-full/mini-full.tsx:412`, `patterns/view-switcher/record-panel.tsx:165` |
| `row` | `patterns/list-peek/list-peek.tsx:377`, `patterns/expand-in-place/expand-list.tsx:47`, `patterns/action-palette/action-palette.tsx:419`, `patterns/doc-collections/collection-block.tsx:144`, `patterns/workspace-panes/item-list.tsx:74` (the `<li>`), `patterns/staged-table-edit/staged-table.tsx:659`, `patterns/mini-full/upcoming-list.tsx:168`, view-switcher row props built in `patterns/view-switcher/layout-shared.ts:28`, `patterns/assisted-notes/note-rows.tsx:45`, `patterns/inspector/item-tree.tsx:154` |
| `cell` | `patterns/doc-collections/collection-block.tsx:152,155,178`, `patterns/staged-table-edit/staged-table.tsx:775`, `patterns/view-switcher/table-layout.tsx:58` |
| `group-header` | `patterns/list-peek/list-peek.tsx:424`, `patterns/action-palette/action-palette.tsx:263`, `patterns/doc-collections/collection-block.tsx:98`, `patterns/staged-table-edit/staged-table.tsx:416`, `patterns/mini-full/upcoming-list.tsx:146`, `patterns/view-switcher/board-layout.tsx:35`, `patterns/inspector/properties-panel.tsx:301` |
| `panel` | `patterns/list-peek/list-peek.tsx:465`, `patterns/mini-full/mini-full.tsx:389`, `patterns/view-switcher/record-panel.tsx:148`, `patterns/inspector/inspector.tsx:419` |
| `surface` | `patterns/expand-in-place/expand-card.tsx:104`, `patterns/action-palette/action-panel.tsx:133`, `patterns/mini-full/quick-add.tsx:195`, `patterns/assisted-notes/source-popover.tsx:68` |

Line numbers are pointers at `RUN_BASE`; place the attribute on the element that plays the role.
Because `extra_css` selectors may not contain commas, each selection state is its own `extra_css` entry.
Adding the attribute must not change classes, structure, ARIA or behavior.

### Token set

Back-link: [Key decisions & rationale](logic.md#key-decisions--rationale).

`SCHEMA:` every style defines every key below in both `light` and `dark`, as an `oklch(L C H)` or
`oklch(L C H / A%)` string (L 0–1, C ≥ 0, H 0–360, A 0–100):

```
SCHEMA: shadcn keys: background foreground card card-foreground popover popover-foreground primary
primary-foreground secondary secondary-foreground muted muted-foreground accent accent-foreground
destructive border input ring chart-1 chart-2 chart-3 chart-4 chart-5 sidebar sidebar-foreground
sidebar-primary sidebar-primary-foreground sidebar-accent sidebar-accent-foreground sidebar-border
sidebar-ring
mini keys: mini-accent mini-accent-soft mini-pending mini-added mini-removed
```

`mini-added` and `mini-removed` are new and replace the literals in `staged-table.tsx:72-73`.
`--mini-row-height: 2rem` and `--mini-gap: 0.5rem` are emitted by the generator as constants, not
per style (density is deferred).

### Style source

Back-link: [Conceptual model](logic.md#conceptual-model).

`SCHEMA:` `styles/<slug>.json`

```
SCHEMA: {
  "slug": str,                     # equals the file stem; one of the seven slugs
  "name": str,                     # display name, e.g. "Calm Paper"
  "studied_from": [str],           # app slugs from check_docs.APPS; [] for neutral-house
  "radius": str,                   # CSS length, e.g. "0.75rem"
  "fonts": {"sans": str, "heading": str, "data": str},   # CSS font-family stacks
  "font_packages": [str],          # npm packages to install and @import, e.g. "@fontsource-variable/source-serif-4"; [] for most
  "light": {<token key>: str},     # exactly the token set
  "dark":  {<token key>: str},
  "extra_css": [ {"selector": str, "mode": "both"|"light"|"dark", "declarations": {prop: value}} ]
}
```

Validation (`_styles.load_style` raises `StyleError` naming the file and field):

- Unknown or missing top-level keys, a token key missing or extra in either mode, or an unparsable
  oklch string.
- `--background` with an alpha below 100%.
- `font_packages` entries not matching `REGEX: ^@fontsource(-variable)?/[a-z0-9-]+$` (offline OFL
  fonts only; no URL, no remote `@import`).
- Any font stack naming `SF Pro`, `SF Compact`, `SF Mono` or `New York`.
- `extra_css`: every `selector` must contain `[data-mini=` and may also use only attribute selectors,
  `:hover`, `:focus-visible`, `::before`/`::after` and the descendant combinator; every property must be
  in the allowlist below. Values must not contain `url(`, `@import` or `!important`.

`CONFIG:` extra_css property allowlist: `background`, `background-color`, `background-image`, `color`,
`border-color`, `border-left-color`, `border-bottom-color`, `border-left-width`, `border-radius`,
`box-shadow`, `backdrop-filter`, `-webkit-backdrop-filter`, `font-family`, `font-weight`,
`letter-spacing`, `opacity`, `outline-color`.

### Fonts per style

Back-link: [Key decisions & rationale](logic.md#key-decisions--rationale) ("System fonts first").

`CONFIG:` the font stacks each source must use (`SYS` = `system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`;
`MONO` = `ui-monospace, Menlo, Consolas, 'DejaVu Sans Mono', monospace`; `GEIST` = `'Geist Variable', sans-serif`):

| Style | sans | heading | data | font_packages |
|---|---|---|---|---|
| neutral-house | GEIST | GEIST | GEIST | `[]` (Geist is already imported by `index.css` in the gallery and in scaffolded apps) |
| calm-paper | SYS | `'Source Serif 4 Variable', 'Iowan Old Style', Georgia, serif` | SYS | `["@fontsource-variable/source-serif-4"]` (SIL OFL 1.1) |
| airy-white | SYS | SYS | SYS | `[]` |
| cool-tool | SYS | SYS | SYS | `[]` |
| dense-dark | SYS | SYS | MONO | `[]` |
| glass-launcher | SYS | SYS | SYS | `[]` |
| split-tone | SYS | SYS | SYS | `[]` |

Weight and tracking differences (Airy White's heavy titles, Cool Tool's semibold) go in `extra_css`
on `[data-mini="title"]`. Confirm the Source Serif 4 package's license field reads `OFL-1.1` before
adding it.

### Generated CSS

Back-link: [Data flow](logic.md#data-flow).

`CONTRACT:` `_styles.render_app_css(style) -> str` produces, in order:

1. Header line, exactly `/* mini-style: <slug> sha256=<hex> */` where `<hex>` is the SHA-256 of the
   UTF-8 bytes of everything after the header's trailing newline.
2. One `@import "<pkg>";` per `font_packages` entry.
3. `html:root { ... }` with `font-size: 15px` (a generator constant, same for every style, as today),
   every light token, `--radius`, `--mini-row-height`, `--mini-gap`, `--mini-font-sans`,
   `--mini-font-heading`, `--mini-font-data`; then `html.dark { ... }` with every dark token.
   (`html:root` / `html.dark` outrank shadcn's unlayered `:root` / `.dark`; keep that.)
4. The fixed hook rules every style gets: `[data-mini="title"] { font-family: var(--mini-font-heading) }`
   and `[data-mini="cell"] { font-family: var(--mini-font-data) }`.
5. `extra_css` rules: `mode: "both"` emits the selector as written, `"light"` prefixes it with
   `html:not(.dark) `, `"dark"` with `html.dark `.

Output is deterministic (stable key order, `\n` line endings, trailing newline) so `--check` can
compare bytes.

`CONTRACT:` `_styles.render_gallery_css(styles) -> str` emits, for every style except `neutral-house`,
the same content scoped with `X = html[data-mini-style="<slug>"]`:

| App CSS | Gallery CSS |
|---|---|
| `html:root { … }` | `X:root { … }` |
| `html.dark { … }` | `X.dark { … }` |
| hook rule or `mode: "both"` rule `S` | `X S` |
| `mode: "light"` rule `S` | `X:not(.dark) S` |
| `mode: "dark"` rule `S` | `X.dark S` |

Font `@import`s are collected and deduplicated at the top. No header line. `neutral-house` must have
an empty `extra_css` (validation error otherwise), because its app CSS is `mini-tokens.css`, which the
gallery loads unscoped under every style.

`CONTRACT:` `_styles.parse_header(text) -> (slug, ok)`: `slug` is `None` when the first line is not a
valid header; `ok` is True only when the recorded hash matches the rest of the file.

### Contrast gate

Back-link: [SC-7](logic.md#behavior--scenarios).

`CONTRACT:` `_styles.contrast_failures(style) -> list[Failure]`, empty when the style passes.
`Failure` carries `slug`, `mode`, `fg`, `bg`, `ratio` (2 decimals), `needed`. Pairs checked in each mode:

| Foreground | Background | Needed |
|---|---|---|
| foreground, muted-foreground, primary, destructive | background | 4.5 |
| card-foreground, muted-foreground | card | 4.5 |
| popover-foreground | popover | 4.5 |
| primary-foreground | primary | 4.5 |
| secondary-foreground | secondary | 4.5 |
| muted-foreground | muted | 4.5 |
| accent-foreground | accent | 4.5 |
| sidebar-foreground | sidebar | 4.5 |
| sidebar-primary-foreground | sidebar-primary | 4.5 |
| sidebar-accent-foreground | sidebar-accent | 4.5 |
| ring | background | 3.0 |
| sidebar-ring | sidebar | 3.0 |

Borders and input outlines are not checked ([SC-7](logic.md#behavior--scenarios), amended 2026-10-23).

Colour math: oklch → oklab → linear sRGB (the CSS Color 4 matrices). A colour with alpha is
composited in linear sRGB over the background it is checked against, and a background with alpha
over `--background`. Out-of-gamut colours are mapped by reducing chroma at fixed L and H (binary
search to 1e-4) until all channels are in [0, 1]. Ratio is WCAG 2.x relative luminance
`(L1 + 0.05) / (L2 + 0.05)`.

### `build_styles.py`

`CONTRACT:` `build_styles.py [--check]`

- No flag: load all seven sources, run validation and the contrast gate, then write
  `styles/dist/<slug>.css` for each, `gallery/src/styles/mini-tokens.css` (= neutral-house app CSS),
  `gallery/src/styles/gallery-styles.css` and `gallery/src/gallery/style-list.json`. Any validation
  error or contrast failure: print each to stderr as `<slug> <mode>: <fg> on <bg> <ratio>:1 < <needed>:1`
  (or the `StyleError`), write nothing, exit 1. Success prints `styles built: <n>` and exits 0.
- `--check`: no writes. Exit 1 naming every output whose bytes differ from what would be generated,
  and on any validation or contrast failure; else print `styles are fresh` and exit 0.
- `--check-file <css>`: parse an app tokens file (the `html:root` and `html.dark` blocks written by
  `render_app_css`, possibly hand-edited), run the contrast gate on its token values, print failures as
  above, exit 1 on any failure or on a missing token, else print `<path>: passes AA` and exit 0. No
  writes. This is the command SKILL.md names for SC-3's hand-tuned accent.
- Missing `styles/` directory or a source whose slug is not one of the seven: exit 2.
- `main(argv: list[str] | None = None, skill_root: Path | None = None) -> int`: every path is derived
  from `skill_root` (default `SKILL_ROOT`), so tests run it in-process against a copied skill.

### Scaffold and swap

Back-link: [SC-1](logic.md#behavior--scenarios), [SC-4 to SC-6](logic.md#behavior--scenarios).

`CONTRACT:` `new_app.py <target_dir> [--patterns p1,p2] [--style <slug>]`. `--style` defaults to
`neutral-house`. An unknown slug exits 2 before any subprocess, listing the seven slugs. Steps run
`init, add, style, tokens, build, dev`. The final report gains a `style: <slug>` line.

`CONTRACT:` `set_style.py <app_dir> <slug> [--force]`. Exit 2, before any subprocess, when: no
`components.json` in `app_dir`; unknown slug (list the seven); `src/styles/mini-tokens.css` missing;
or the tokens file is hand-edited (`parse_header` gives `slug None` or `ok False`) and `--force` is
absent. The hand-edit message names the file and says rerunning with `--force` discards the edits.
Otherwise steps `style, tokens, build, dev`, then prints `app: <path>` and `style: <slug>`.

`CONTRACT:` `_mini.style_step(app: Path, slug: str) -> int`: writes `styles/dist/<slug>.css` bytes to
`<app>/src/styles/mini-tokens.css` (creating `src/styles/` if needed), then, for each
`font_packages` entry absent from `<app>/package.json` dependencies, runs `pnpm add <pkgs...>` via
`run_step("style", ...)`. Never removes packages.

`CONTRACT:` `new_app.tokens_step` (move to `_mini.tokens_step`, re-export from `new_app` so existing
imports keep working) stays idempotent and additionally rewrites, inside the first `@theme inline`
block of `src/index.css`, the `--font-sans:` line to `--font-sans: var(--mini-font-sans);` and the
`--font-heading:` line to `--font-heading: var(--mini-font-heading);`, adding either line when absent.
No `@theme inline` block: `step_failed("tokens", ...)`.

### Gallery picker

Back-link: [SC-8](logic.md#behavior--scenarios).

`CONTRACT:` `StylePicker` renders a native `<select>` (or the shadcn `Select` already in
`components/ui`) labelled "Style", options from `style-list.json`, placed in the AppShell toolbar
before `ThemeToggle`. Choosing a slug sets `document.documentElement.dataset.miniStyle`, or removes
the attribute for `neutral-house`. The choice persists in `localStorage["mini-style"]` with every
read/write in try/catch; an unknown stored value falls back to `neutral-house`. `gallery/src/index.css`
imports `./styles/gallery-styles.css` immediately after `./styles/mini-tokens.css`, and its font lines
are rewired as in `tokens_step`.

### Style references and docs check

`check_docs.py`'s usage docstring lists `style` beside `study|pattern`.

Back-link: [Conceptual model](logic.md#conceptual-model).

`CONTRACT:` `check_docs.py style <slug>` with `KINDS["style"] = (references/styles/, the seven slugs,
["Character", "When it fits", "Studied from", "Leaves out"])`, same order/non-empty rules as the other
kinds. `neutral-house`'s "Studied from" says it was not studied from an app. "Leaves out" names the
brand traits not carried: craft's sky-blue wallpaper; notion's emoji covers; linear's indigo and glyphs;
obsidian's graph view and purple; raycast's red-lit gradient; tableplus's green status pill;
fantastical's red tab and weather glyphs; things' star glyph; granola's chartreuse; figma's azure and
multicolor brand. Evidence comes from `references/apps/<app>.md` and the local frames; cite frame paths
the same way study notes do.

### SKILL.md

Back-link: [SC-1 to SC-3](logic.md#behavior--scenarios).

- A new section `## Style index` right after `## Pattern index`: a table of slug, character, and
  "Studied from", plus one line linking each `references/styles/<slug>.md`.
- `## Building a new app` step 2 also names one style with one line on why and lists the other names
  ("Say the word to switch"); step 3's command gains `--style <slug>`; step 7 reports the style.
  When the user names a studied app, map it through the Studied from column and say the style keeps
  the feel, not the app's exact look. When the user asks for a variation (SC-3), use the nearest style,
  then hand-tune the tokens file, run `build_styles.py --check-file <app>/src/styles/mini-tokens.css`,
  and tell the user the app no longer matches a shipped style.
- A new section `## Changing an app's style` after `## Adding a pattern`, documenting `set_style.py`
  and `--force`.
- `## Rules`: replace "One neutral house style" with "One style per app" (all blocks use the app's
  tokens file; change the look by switching style or editing that file, never by styling one block
  apart), and replace "No brand assets from studied apps" with: no logos, icons, illustrations, copy,
  exact brand colors or proprietary fonts; a style carries an app's character only.
- `tests/test_building_mini_apps_skill.py:28` `REQUIRED_SECTIONS` gains `Style index` (after `Pattern
  index`) and `Changing an app's style` (after `Adding a pattern`).

## Data models / schemas

Covered inline above: style source, token set, generated CSS header, `style-list.json`
(`SCHEMA: [{"slug": str, "name": str}]`, display order), `Failure`.

## DO-NOT-CHANGE fences

- **Block behavior, ARIA, classes and structure** in `gallery/src/patterns/**` and
  `components/mini/**`: the hooks task adds `data-mini` attributes and swaps the two staged-table tint
  literals for `var(--mini-added)` / `var(--mini-removed)` only. Why: the ten blocks just passed four
  adversarial review rounds; behavior is out of scope ([Scope & non-goals](logic.md#scope--non-goals)).
- **`registry/r/*.json` by hand**: regenerate only with `python3 scripts/build_registry.py`. Why: its
  `--check` compares bytes with the sources.
- **`styles/dist/*`, `gallery/src/styles/mini-tokens.css`, `gallery-styles.css`, `style-list.json` by
  hand**: regenerate with `build_styles.py`. Why: freshness check.
- **`components/theme-provider.tsx` and `app-shell.tsx`'s `useSystemTheme`**: light/dark ownership
  stays as is; styles ride on the existing `.dark` class. Why: it went through review for ownership races.
- **Neutral House's look**: token values copied exactly from `mini-tokens.css` at `RUN_BASE`, plus
  `mini-added`/`mini-removed` equal to the old staged-table light/dark literals; `font-size: 15px`;
  fonts all GEIST; `font_packages` and `extra_css` empty. Why: the default look must not move.

## Always / Ask / Never

Back-link: [Decisions Locked](logic.md#decisions-locked).

- **Always**: stdlib-only Python; deterministic generated output; regenerate the registry after any
  change under `gallery/src/` that ships in an item; keep `neutral-house` the default.
- **Ask** (NEEDS_CONTEXT): adding any npm dependency other than `@fontsource*` font packages; adding a
  hook role outside the vocabulary; any change that alters a block's layout.
- **Never**: name a studied app in a style's `name`, generated style CSS or `style-list.json`; ship a
  remote or proprietary font; bind new keys.

## Cross-cutting

Back-link: [Scope & non-goals](logic.md#scope--non-goals).

- **Offline**: fonts come from npm `@fontsource*` packages only, resolved at build.
- **Existing apps**: an app scaffolded before this change has a tokens file without a header, so
  `set_style.py` treats it as hand-edited and needs `--force`. Its `index.css` font lines are rewired by
  the tokens step on first `set_style` run.
- **Rollback**: `set_style.py <app> neutral-house --force` restores the default look.

## Testing strategy

Back-link: [Key decisions & rationale](logic.md#key-decisions--rationale) ("Done means it passes AA").

- `tests/test_building_mini_apps_styles.py`, no network and no subprocess (use the `no_subprocess`
  pattern from the skill test file; call `build_styles.main(argv, skill_root=<copy>)` in-process rather
  than running the script):
  - colour math: white on black is 21:1; `#767676` on white is 4.54:1 (as oklch); an out-of-gamut
    colour maps in gamut; a 50%-alpha foreground composites over its background.
  - validation: each `StyleError` rule rejects a crafted bad source (missing token, alpha background,
    remote font, SF Pro, a selector without `[data-mini=`, a disallowed property, `url(`).
  - every real source passes validation and the contrast gate; `build_styles.py --check` passes on the
    real tree and fails after a one-byte edit to a copied dist file (copy the skill like
    `_copy_skill`).
  - `render_app_css` header round-trips through `parse_header`; an edited body makes `ok` False.
  - `new_app.py --style nope` and `set_style.py` usage errors (no components.json, unknown slug,
    missing tokens file, hand-edited without `--force`) exit 2 with no subprocess.
  - `tokens_step` on a fixture copied from `gallery/src/index.css` rewires both font lines, is
    idempotent, and fails without `@theme inline`.
  - no studied app's display name appears in generated style output: case-sensitive whole-word match
    of `Linear`, `Things`, `Raycast`, `Craft`, `Obsidian`, `TablePlus`, `Fantastical`, `Notion`,
    `Granola`, `Figma` over `styles/dist/*.css`, `gallery-styles.css`, `style-list.json` and every
    source's `name` (so `linear-gradient` does not trip it).
  - `--check-file` passes on each `styles/dist/*.css` and fails on a copy with muted text set too light.
- `tests/test_building_mini_apps_skill.py`: parametrized `check_docs.py style <slug>` passes for all
  seven; `REQUIRED_SECTIONS` updated.
- Gallery: `pnpm build` and `pnpm exec eslint src` clean.

`COMMAND:` the per-wave gate, from the worktree root:

```
COMMAND: python3 -m pytest -q tests/test_building_mini_apps_skill.py tests/test_building_mini_apps_styles.py && python3 skills/building-mini-apps/scripts/build_registry.py --check && python3 skills/building-mini-apps/scripts/build_styles.py --check && (cd skills/building-mini-apps/gallery && pnpm build)
```

Before the first wave creates `tests/test_building_mini_apps_styles.py` and `build_styles.py`, the gate
drops those two parts.

The locked gallery pass (each style on all ten blocks, light and dark) is run once after the last
wave: screenshots go to `references/media/styles/<slug>/<pattern>-<mode>.png` (gitignored with the rest
of `references/media/`) and are inspected for broken or unreadable blocks.

## Non-goals

Density tokens or options, a runtime style switcher in generated apps, APCA gating, removing font
packages on a style switch, migrating existing apps automatically, and any change to the hosted
registry story. See [Scope & non-goals](logic.md#scope--non-goals).
