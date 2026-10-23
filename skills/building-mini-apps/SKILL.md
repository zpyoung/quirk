---
name: building-mini-apps
description: Use when the user asks to "build me a mini app", "a little app to track…", or "a local tool with saved data" - a small React app they will keep and run on their own machine, built from proven interaction patterns (list-peek, action-palette, view-switcher and others) instead of a generic dashboard, in one of seven looks. Not for single-file HTML pages, reports or dashboards; those go to writing-html-artifacts.
---

# Building mini apps

Scaffold a small local web app (React, Vite, Tailwind v4, shadcn/ui, data in the browser) from a shared base plus two or three interaction patterns, then adapt it to the user's domain. The patterns copy how well-known apps behave, not how they look. The styles carry an app's character, never its exact look.

`SKILL_DIR` is the directory holding this `SKILL.md`, which the host shows when the skill loads. Every command below is run as `python3 "$SKILL_DIR/scripts/<script>.py" ...`. Do not build paths from a plugin-root environment variable: not every host sets one. Installs read the local registry in `$SKILL_DIR/registry/r/`, and block sources live in `$SKILL_DIR/gallery/src/patterns/<pattern>/`.

## When to use

Use it when the user wants an app they will keep and run: several views or records, edits that persist, keyboard use. Typical asks: "build me a mini app to track books", "a little app to log my gear", "a local tool with saved data".

- **Not for a single HTML file.** A page, report, dashboard or one-off tool that opens from disk belongs to `writing-html-artifacts`. Its tier 2 also builds React, but bundles to one file with no project folder.
- **Not for editing an existing app's components**, hosted deployments, or native desktop and mobile builds.
- The gallery (`gallery/`, run with `pnpm dev` there) shows every pattern running next to its reference, if the user wants to browse first.

## Pattern index

A pattern is one named interaction. A mini app usually combines two or three. Read the linked reference before choosing: it holds the layout, keys, states and what is deliberately left out.

| Slug | What it does | Studied from | Reference |
|---|---|---|---|
| list-peek | Dense list; j/k move, Space previews the item in a side panel | Linear | [list-peek](references/patterns/list-peek.md) |
| expand-in-place | A row opens into an editable card; optional fields stay hidden until asked for | Things 3 | [expand-in-place](references/patterns/expand-in-place.md) |
| action-palette | Search, select, then ⌘K lists the actions for that one item | Raycast | [action-palette](references/patterns/action-palette.md) |
| doc-collections | A document with record tables embedded in it, each record with a free-text body | Craft | [doc-collections](references/patterns/doc-collections.md) |
| workspace-panes | Tabs and split panes over file-like records, with a structured view and a raw view | Obsidian | [workspace-panes](references/patterns/workspace-panes.md) |
| staged-table-edit | Inline cell edits stay pending until one commit or discard | TablePlus | [staged-table-edit](references/patterns/staged-table-edit.md) |
| mini-full | Quick-add with natural-language parsing that opens into a full view | Fantastical | [mini-full](references/patterns/mini-full.md) |
| view-switcher | Table, board or calendar over the same records; a record opens in a side panel | Notion | [view-switcher](references/patterns/view-switcher.md) |
| assisted-notes | The user's notes stay primary; generated additions are styled apart and cite their source | Granola | [assisted-notes](references/patterns/assisted-notes.md) |
| inspector | Navigation tree, canvas, and a properties panel for the selection | Figma | [inspector](references/patterns/inspector.md) |

Each app has a study note in `references/apps/<app>.md` if a reference points to evidence you need.

## Style index

A style is the look of one app: colors (light and dark), radius, fonts, border and shadow weight, and a few rules on named hooks. It never changes layout, spacing or components. Each app gets exactly one, written to `src/styles/mini-tokens.css`. Read the linked reference before recommending one: it holds the character, when it fits, and what it leaves out.

| Slug | Character | Studied from |
|---|---|---|
| neutral-house | Calm cool greys, white cards, one slate-teal accent; the default | Not studied from an app |
| calm-paper | Warm paper, serif titles, ink-black actions | Granola, Craft |
| airy-white | Stark white, bold titles, one soft blue accent, small radius, faint shadow | Notion, Things 3 |
| cool-tool | Cool-grey hairlines, small radius, one blue-violet for selection and focus | Linear, Figma |
| dense-dark | Flat charcoal, steel-blue solid selection, monospace data cells | TablePlus, Obsidian |
| glass-launcher | Translucent blurred panels, large radius, warm orange accent | Raycast |
| split-tone | Dark sidebar on a light canvas, rose accent, edge-striped selection | Fantastical |

References: [neutral-house](references/styles/neutral-house.md), [calm-paper](references/styles/calm-paper.md), [airy-white](references/styles/airy-white.md), [cool-tool](references/styles/cool-tool.md), [dense-dark](references/styles/dense-dark.md), [glass-launcher](references/styles/glass-launcher.md), [split-tone](references/styles/split-tone.md).

## Building a new app

1. **Read the matching references.** Pick the patterns from the index by what the user does with the records, then read each chosen `references/patterns/<p>.md` in full, including its When to use and what it leaves out.
2. **Name the patterns and why**, in your reply, before building: one line per pattern tying it to the user's request. Two or three is normal; one is fine; more than three usually means the request is two apps. Then pick the style:
   - **No look named.** Name one style with one line on why it fits, list the other six names, and say "Say the word to switch." Scaffold with the one you named; do not wait for an answer.
   - **A studied app named** ("make it look like Linear"). Map it through the Studied from column of the Style index and use that style. Say the style keeps the feel of the app, not its exact look.
   - **A variation** ("like Things 3 but green"). Use the nearest style, then tune the accent in `src/styles/mini-tokens.css` after the scaffold. Run `python3 "$SKILL_DIR/scripts/build_styles.py" --check-file <app>/src/styles/mini-tokens.css` and fix any contrast failure it reports. Tell the user the app no longer matches a shipped style, so a later style switch needs `--force`.
3. **Scaffold.** The target must not exist and its parent must:

   ```
   python3 "$SKILL_DIR/scripts/new_app.py" <target_dir> --patterns <p1,p2> --style <slug>
   ```

   `--style` defaults to `neutral-house`. The script runs shadcn init, installs the base and the patterns from the local registry, writes the style's tokens file, runs `pnpm build`, and checks that `pnpm dev` reaches `Local:`. Exit 2 means bad arguments (unknown pattern or style, existing target); exit 1 names the failed step. Fix the cause and rerun against a fresh target; do not hand-patch around a failed scaffold. It needs the network for npm.
4. **Compose in `src/App.tsx`.** Demos and blocks never render `<AppShell>` themselves. Render the block demos inside the app's own `<AppShell>` in `src/App.tsx`, passing `title`, and `sidebar` or `toolbar` as the layout needs.
5. **Adapt each `src/patterns/<p>/demo.tsx`** to the user's domain: rename the generic item to the real thing (a book with title, author, status, notes), change the collection names and sample data, and trim fields and actions the user won't use. The demo is a worked example to edit, not to ship as is.
6. **Verify.** In the app folder, run `pnpm build` and then `pnpm dev`; the app is run with `pnpm dev`. Confirm both before you report.
7. **Report** the app path, the patterns used, the style, and the build and dev result. If either failed, say so and what you tried.

## When no pattern fits

If the request matches none of the ten well (a waveform audio editor, a 3D scene tool), say so. Do not stretch a pattern into a shape it wasn't built for.

- Offer the base alone: `new_app.py <target_dir>` with no `--patterns` gives the shell, the style tokens, keyboard layer, browser store with JSON export and import, and empty, loading and error states.
- List the two or three nearest patterns, each with why it falls short, using the pattern's own When to use.
- Build only after the user picks. Do not invent a new pattern during the build.

## Adding a pattern

To add a pattern to an app that already has the base:

```
python3 "$SKILL_DIR/scripts/add_patterns.py" <app_dir> --patterns <p1,...>
```

It installs only the new block; existing files, including the base, are skipped, then it rebuilds and checks `pnpm dev`. Exit 2 means no `components.json` in the app or an unknown pattern.

Then wire the block in by hand: read the app's existing store and keyboard bindings first, point the new block at the existing collection (`useCollection` by name) instead of its demo's sample data, and resolve key clashes with the patterns already installed. Render it from `src/App.tsx` inside the existing `<AppShell>`. Rebuild and report as in step 7 above.

## Changing an app's style

To switch an existing app to another style:

```
python3 "$SKILL_DIR/scripts/set_style.py" <app_dir> <slug> [--force]
```

It overwrites `src/styles/mini-tokens.css` with the style's tokens, adds any font packages the style needs, rebuilds, and checks `pnpm dev`. Exit 2 means no `components.json` in the app, an unknown style, or a missing tokens file.

Exit 2 also means the tokens file was edited by hand (a variation, or any manual tweak) and `--force` was not given. The message names the file. Rerunning with `--force` discards those edits, so tell the user first and only force after they agree. Report as in step 7 above.

## Rules

- **One style per app.** All blocks use the app's tokens file, `src/styles/mini-tokens.css`. Change the look by switching style or editing that file, never by styling one block apart.
- **No brand assets from studied apps.** No logos, icons, illustrations, copy, exact brand colors or proprietary fonts. A style carries an app's character only.
- **Data in the browser by default** (IndexedDB through the base `useCollection`, with JSON export and import). Add a small local server only when the user's need clearly calls for it, such as reading real files.
- **Never bind keys the browser reserves:** ⌘N, ⌘T, ⌘W, ⌘L. Keep the base rule that bindings do not fire while focus is in an input unless the pattern says so.
- **Never make one pattern import another.** Share through the base: the store, the state components, the keyboard layer.
- **Ask before adding dependencies** beyond the base and the installed shadcn components.
- **Done means it runs:** `pnpm build` passes and `pnpm dev` starts. Never report a scaffold as working without both.
