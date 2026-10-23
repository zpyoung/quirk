# action-palette

A searchable list where one row is selected and ⌘K opens a small panel of actions for that row, studied in Raycast's root search, file and app lists. Rows can also be checked, and then the panel runs each action on all of them and its header names the count. That multi-item target was studied in Sentry's issue table and command palette. It was studied in Sentry.

## When to use

Use it when every item can have several different things done to it and the keyboard is the main input.

- A bookmark manager: Open, Copy URL, Edit, Move to folder…, Delete.
- A snippet or clipboard library: Paste, Copy, Pin, Delete.
- A reading list: Open, Mark read, Archive, Copy link.
- A local "do anything" launcher over a small set of saved commands or files.
- Any of the above when the user ticks several rows first: Pin, Move to… or Delete then apply to all of the ticked rows at once, with the count shown in the panel.

Do not use it when:

- The item only needs one action, or a view and an edit. Use `list-peek` (a preview beside the list) or `expand-in-place`.
- The user edits many fields or rows before committing. Use `staged-table-edit`.
- Items are documents the user reads and writes in the app. Use `doc-collections`.
- The user needs details on screen beside the list, not a menu of verbs. Use `inspector`.
- The main job is ticking rows in a table and pressing one of a few fixed bulk buttons in a bar. Use `bulk-select`. The multi-item target here is for a palette list whose actions are many, filterable and keyboard-first.

## Anatomy

Proportions are approximate, from S1-0001 and S1-0051 (list window about 1.6:1; panel about 45% of window width).

```
┌──────────────────────────────────────────────────────┐
│ ⌕  Search…                                  (hint)   │  search row, ~70px
├──────────────────────────────────────────────────────┤
│  SECTION                                             │
│ ▌Row title            subtitle           type  …  │  rows ~44px, 8 visible
│  Row title            subtitle           type     │
│  Row title            ┌──────────────────────────┐   │
│  Row title            │ Selected item title      │   │  panel ~45% wide,
│  Row title            │▌Primary action        ↵  │   │  anchored bottom-right
│                       │ Secondary action    ⌘ ↵  │   │  above the footer
│                       │ Other action        ⌘ E  │   │
│                       │ ──────────────────────── │   │
│                       │ Delete (red)      ⌘ ⌫    │   │
│                       │ Search actions…          │   │
├───────────────────────┴──────────────────────────┴───┤
│ status / app name        Open ↵ │ Actions ⌘K         │  footer bar, ~40px
└──────────────────────────────────────────────────────┘
```

- **Search row:** one input that filters the list as you type.
- **List:** optional section headings, rows with title, dimmer subtitle and a right-aligned muted type label. The selected row is a lighter rounded rectangle with no accent color.
- **Row actions button:** a ghost `…` icon button at the right end of every row that has actions, named "Actions for <item title>". Always visible on the selected row; other rows show it on hover or when focus is inside the row. Our design.
- **Row checkbox (multi-item target only):** a 16px checkbox before each row, shown only when `selectedIds` or `onSelectedIdsChange` is passed (S13-bulk-select shows a checked box at the left edge of each row and the row layout unchanged). Checked rows get the accent-soft fill; the highlighted row keeps its own fill, so a row can be both. The checkbox is not a tab stop (our design).
- **Footer bar:** left slot for the app or view name, replaced by a spinner and message while an action runs, or a toast. Right slot names what ↵ does for the selected row, then an "Actions ⌘K" button with a visible border and hover state, the same 28px height as any other footer control (our design).
- **Action panel:** a card with the selected item's title, action rows (icon-free in our house style, shortcut keycaps at the right), thin separators between groups, and a filter input at the bottom edge. The list underneath stays visible and is not dimmed.
- **Count chip (multi-item target only):** when the target holds two or more items, the panel header shows a `secondary` badge reading "3 selected" in place of the item title, and inside a sub-menu the chip stays beside the sub-menu's name. The chip is borrowed from the grey target chip in Linear's command menu (S3-t1126 in the Linear study note), with our wording; S13-bulk-select shows no count label in its bar.
- **Selection summary (multi-item target only):** while rows are checked, the footer's left side adds "3 selected" and a small "Clear" button next to the status slot.

Multi-item layout, drawn the same way. Only the differences from the single-item picture are shown:

```
│ ☑ Row title            subtitle           type  …  │  checked row: accent-soft fill, `…` shown
│ ☐ Row title            subtitle           type     │  unchecked: no `…` while rows are checked
│ ☑ Row title            ┌──────────────────────────┐   │
│                        │ [3 selected]             │   │  chip replaces the item title
│                        │▌Copy URLs             ↵  │   │
├────────────────────────┴──────────────────────────┴───┤
│ Saved links   3 selected [Clear]   Copy URLs ↵ │ Actions ⌘K │
```

## Interaction

| Key | Does | Notes |
|---|---|---|
| Type | Filters the list; selection resets to the first match | Substring match on title plus any extra search text; title prefix matches rank first (our design) |
| ↑ / ↓ | Moves the selection | Works while the search input has focus. Stops at the ends |
| ⌘K (Ctrl K) | Opens the panel for the selected row; closes it if open | Fires even while typing in the search input. Does nothing when no row is selected or the row has no actions |
| Click a row | Selects it | Only selects; never opens the panel or runs an action |
| Click a row's `…` button | Selects that row and opens its panel, anchored bottom-right like ⌘K's; closes the panel if it is already open for that row | Our design. Clicking another row's `…` while a panel is open switches the panel to that row. Focus moves to the panel's filter input, and returns to the search input on close |
| Click the footer "Actions ⌘K" button | Opens the panel for the selected row; closes it if open | Same as ⌘K, for when no row is hovered. Our design |
| Tab | Moves focus from the search input to the selected row's `…` button, then to the footer button | Our design. Only the selected row's button is a tab stop; the list keeps one tab stop. Enter or Space on the focused button works as a click |
| ↵ | Runs the primary action of the selected row | With the panel open, runs the highlighted action instead. A primary action that has `children` opens the panel on its sub-menu instead of running |
| ⌘↵ (Ctrl ↵) | Runs the secondary action | Only when the row has a second action; otherwise ignored. Inside an open sub-menu it does nothing |
| Action chord, such as ⇧⌘F | Runs that action on the selected row | Works with the panel open or closed, including while typing in the search or panel input. Sub-menu actions can carry chords too. Chords are ignored while focus is in a text field outside the block |
| Esc | Backs out one level: sub-menu, then panel, then a non-empty query, then the checked rows | With an empty query, no panel and no checked rows it does nothing. Works while typing in the search or panel input |
| / | Focuses the search input | Our design; only when focus is not in a text field |
| ⇧⌘X (Shift Ctrl X) | Checks or unchecks the highlighted row | Multi-item target only. Works while typing in the search input. Our design: the blueprint's table binds `x` where focus is not in a field, but this list keeps focus in its input, so the chord needs a modifier |
| ⇧↑ / ⇧↓ | Checks the highlighted row and the row it moves to | Multi-item target only. Works while typing in the search input. Only ever adds; ⇧⌘X unchecks. Our design |
| Click a row's checkbox | Toggles that row and highlights it | Multi-item target only. Never opens the panel or runs an action |
| Shift-click a row's checkbox | Checks every visible row from the last row you toggled to this one | Multi-item target only. Our design |

With rows checked, ⌘K, ↵, ⌘↵, action chords and the row `…` buttons act on the checked rows. See "Multi-item target" below.

**Focus rules**

- The search input has focus at all times when the panel is closed. The list never takes focus; the selection moves through `aria-activedescendant`.
- Opening the panel moves focus to its filter input and highlights the first action (S1-0051). Typing narrows actions to one flat list, ignoring sections (S4).
- Choosing a row that ends in "…" and has children replaces the panel's contents in the same card. The title becomes that action's name and the placeholder shortens (S2-0021). Esc returns to the parent list with its filter cleared.
- Closing the panel by Esc, by running an action or by clicking outside returns focus to the search input. The query and the selected row are kept.
- Esc with a non-empty query clears it (S5). Our design adds nothing further, since a web page has no window to close.

**Multi-item target**

The target is the checked rows when any are checked, otherwise the highlighted row, exactly as before. Multi-item mode is on only when `selectedIds` or `onSelectedIdsChange` is passed.

- Checked ids that are not in `items` are ignored. Checked rows hidden by the search stay in the target, which is why the footer always shows the count.
- The action list comes from `getActions(firstCheckedItem, checkedItems)`. The host decides which actions make sense for several rows by reading the second argument, and omits the rest. Without that, the same list as for one row is used.
- An action runs on a multi-item target by calling `runMany(items)` once when it has one. Otherwise `run(item)` is called for each row in order, one after another, and the first rejection stops the rest and shows the error toast. A single row still calls `run(item)`.
- Sub-menu actions and chords follow the same rule. The primary and secondary actions are the first two of the list the host returned for the checked rows.
- While rows are checked, only checked rows render a `…` button, and its label reads "Actions for 3 selected" (our design). A click on an unchecked row's `…` is therefore not possible, so the panel never opens for a different target than the footer states.
- Changing the checked set while the panel is open closes it.
- Esc after the query is empty calls `onSelectedIdsChange([])`. The host owns what happens to the checked ids after an action. The block never clears them itself, so a bulk delete should clear them in its `runMany`.
- `ActionPanel` on its own takes `items` as the target. With two or more it shows the count chip and calls `onRun(action)`; running the action is the host's job there.

**States**

| State | Shows |
|---|---|
| Empty collection | `EmptyState` in the list area with a one-line prompt to add the first item. Footer shows no Actions button |
| No matches | Message with the query, "No results for “…”". If `onCreate` is given, a first row "Create “…”" is selected; this is our design, adapted from the fallback rows in S1-0022 |
| Loading | `LoadingState` in the list area. The search input stays enabled and ⌘K does nothing |
| Error | `ErrorState` with a retry button when `onRetry` is given |
| Action running | Footer left slot shows a spinner and the action's `pending` label; the list stays usable (S1-0060) |
| Action done or failed | Success shows a `sonner` toast when `successMessage` is set; a rejected `run` shows an error toast with the error message and keeps the panel closed. Failure feedback is our design (S2 and S1 showed only success) |
| Long titles | Rows and the panel header truncate to one line with an ellipsis; the full title is in the `title` attribute. Action titles truncate the same way |
| Many items | The list scrolls inside `ScrollArea`; only the first 200 matches render, with a final row "Showing 200 of N. Keep typing to narrow". Our design |
| Many actions | Panel body scrolls, about 8 rows tall (S2-0015); the filter input stays pinned at the bottom. Destructive actions sort last, below a separator |
| No matching action | One muted row "No actions match" in the panel; ↵ does nothing. Not seen in sources, our design |
| Item has no actions | The footer shows only the primary label if any, and no Actions button (S1-0075). The row renders no `…` button |
| Checked rows hidden by the filter | Still counted in the chip and the footer, and still the target. "Clear" or Esc with an empty query removes them. Our design |
| Checked row removed by an action | It drops out of the target on the next render; the host should clear stale ids in its handler. When the last checked row goes, the target falls back to the highlighted row |
| Mixed rows | The host builds titles from the second argument to `getActions`, for example "Unpin" only when every checked row is pinned |
| Loading or error | Checked rows are ignored while `status` is not "ready" |
| Row `…` button | Rendered for every row with actions, in the DOM at all times. Visible (opacity 1) on the selected row and while the panel is open for its row; on other rows it appears on hover or `focus-within`. Its `aria-expanded` mirrors the panel. Not rendered on the "Create “…”" row. Our design |

## Borrow / Leave out

**Borrow**

- Panel as a floating card over the list's lower right, list still visible (S1-0051).
- Panel anatomy: item title, action rows with keycap shortcuts, separators, filter input at the bottom (S1-0051, S1-0048).
- First action is primary (↵), second is secondary (⌘↵) (S7, S2-0019).
- Footer that names the primary action for the current row and shows the ⌘K button, hidden when the row has no panel (S1-0001, S1-0073, S1-0075).
- One keycap per key of a chord, modifier glyphs that change by platform (S1-0048, S1-0004).
- Filtering the panel as a flat substring match (S2-0015, S4).
- Sub-menus that replace the panel contents, and "…" on rows that lead to another view (S2-0021).
- Esc backs out one level; the first Esc clears the query (S4, S5).
- Spinner and message in the footer while an action runs (S1-0060).
- Destructive actions drawn in red (S4, text only).
- Checked rows that keep their layout and are acted on together, with the actions reaching every checked row (S13-bulk-select, S13-command-palette).
- A chip at the top of the panel that names what the actions will hit (S3-t1126 and S1-t0129 in the Linear study note), here carrying the count.

**Leave out**

- Root-level multi-source search (apps, files, web) and fallback "Use … with" commands: a mini app has one data set.
- Frecency, aliases and "Reset Ranking": too little data to matter locally.
- Hotkey and alias recorders in Configure Command: no per-user command config in a local app.
- Compact mode ("Show More"): that is `mini-full`.
- AI hint ("Quick AI", Tab key): no assistant in this pattern.
- Custom primary key such as ⌘R (S1-0082): ↵ always runs the primary action, so the footer stays predictable.
- Section jumps (⌘↑/⌘↓) and page jumps (⌥↑/⌥↓): lists here are short.
- Backspace-to-go-back (S5): there is no view stack, only the panel levels.
- Centered full-width command modal (Linear, Obsidian): a different layout. We anchor to the selected list, as Raycast does.
- Raycast's colors, icons, logo and wording. The block uses neutral tokens and text-only action rows.
- Sentry's bulk action bar in the table header (Resolve and Archive split buttons, Merge, Set Priority, the indeterminate select-all box): that is `bulk-select`. Here the palette is the only action surface.
- Disabling actions for mixed selections (the dimmed Merge in S13-bulk-select, never confirmed as disabled): the host returns only the actions that make sense through `getActions`.
- Sentry's "Go to…" navigation group and the centered modal (S13-command-palette): this pattern only lists actions for rows.

## Block API

Files in `src/patterns/action-palette/`: `index.ts` re-exports `ActionPalette`, `ActionPanel`, `ShortcutKeys`, `formatShortcut` and the types `PaletteItem`, `PaletteAction`, `ActionPaletteProps` and `ActionPanelProps`; `selection.ts` holds the pure checked-row logic (`toggleId`, `selectRange`, `resolveTargets`, `selectionLabel`) and is not exported; `demo.tsx` default-exports `Demo`. `registry-item.json` declares `dependencies` `react-hotkeys-hook` and `sonner`.

The multi-item target is additive: every new prop and field is optional, and with none of them passed the block renders and behaves exactly as before.

Mouse path, no new props: the row `…` buttons and the footer button are rendered by `ActionPalette` itself, and `getActions` decides which rows get one (a row whose `getActions` returns an empty array has none). There is no prop to hide them. Each row is a `role="none"` wrapper holding the `role="option"` element and the button as siblings, so no interactive element sits inside an option. Every row's button is in the DOM, but only the selected row's has `tabIndex` 0, which keeps the list at one tab stop. All of these buttons carry `data-action-palette-toggle`, which `ActionPanel`'s outside-click handler ignores, so a click toggles the panel instead of closing and reopening it.

```ts
// CONTRACT: item and action types
type PaletteItem = { id: string; title: string };

type PaletteAction<T extends PaletteItem> = {
  id: string;
  title: string;                       // end with "…" when `children` is set
  run?: (item: T) => void | Promise<void>;
  runMany?: (items: T[]) => void | Promise<void>;   // once on a multi-item target; without it, `run` is called per item in order
  children?: PaletteAction<T>[];       // opens a sub-menu; `run` is ignored
  shortcut?: string;                   // react-hotkeys-hook form, e.g. "mod+shift+f"
  destructive?: boolean;               // red; separated from the other actions
  section?: string;                    // groups rows under a separator while unfiltered
  pending?: string;                    // footer text while `run` is in flight
  successMessage?: string;             // toast on success; omit for none
};

// CONTRACT: <ActionPalette<T extends PaletteItem> {...props} />
type ActionPaletteProps<T extends PaletteItem> = {
  items: T[];
  status?: "loading" | "ready" | "error";   // default "ready"
  error?: Error;
  onRetry?: () => void;
  getActions: (item: T, selection: T[]) => PaletteAction<T>[];  // first = primary, second = secondary; `selection` is the whole target, [item] when nothing is checked
  getSubtitle?: (item: T) => string | undefined;
  getMeta?: (item: T) => string | undefined;    // right-aligned type label
  getSearchText?: (item: T) => string;          // extra words matched besides title
  getSection?: (item: T) => string | undefined; // row group headings, shown while the query is empty
  onCreate?: (query: string) => void;           // enables the "Create “…”" row
  placeholder?: string;
  footerLabel?: string;                         // left footer slot, default none
  emptyState?: { title: string; description?: string; action?: ReactNode };
  selectedIds?: string[];                       // checked ids; passing this or onSelectedIdsChange turns on the multi-item target
  onSelectedIdsChange?: (ids: string[]) => void; // called with the next checked ids; omit selectedIds to let the block keep them
};

// CONTRACT: type ActionPanelProps<T extends PaletteItem> = { item: T; items?: T[]; actions: PaletteAction<T>[]; initialPath?: PaletteAction<T>[]; onClose: () => void; onRun: (action: PaletteAction<T>) => void }
// CONTRACT: <ActionPanel<T extends PaletteItem> {...ActionPanelProps<T>} />   the card ActionPalette renders; usable on its own
// CONTRACT: ActionPanel `items`: the multi-item target. With two or more entries the header shows a "N selected" chip in place of `item.title` (`item` is then only the anchor), and `onRun` still receives the action; the host runs it on `items`. A host app can open the panel for rows checked in another pattern's table
// CONTRACT: <ShortcutKeys shortcut={string} />       renders one keycap per key, glyphs by platform
// CONTRACT: formatShortcut(shortcut: string): string[]   e.g. ["⌘", "⇧", "F"] on macOS, ["Ctrl", "Shift", "F"] elsewhere
```

Uses these base pieces:

- `useHotkeys` from `react-hotkeys-hook`: `mod+k` with `enableOnFormTags: true` (the one binding allowed to fire inside an input); `enter` and `mod+enter` also with `enableOnFormTags` but scoped to the search input; action chords with default form-tag blocking. With the multi-item target on, `shift+up`, `shift+down` and `mod+shift+x` are added the same way, enabled only then and ignored unless focus is in the search input, so single-item use keeps ⇧↑ and ⇧↓ for text selection.
- `EmptyState`, `LoadingState`, `ErrorState` from `states.tsx`.
- `useCollection` is called by `demo.tsx`, not by the block: the block takes `items` and `status`, so any source can feed it.

shadcn components, all from the pre-installed list:

- `input` for search.
- `command` (cmdk) for the panel's filtered list and bottom input.
- `kbd` for keycaps.
- `scroll-area`, `separator`, `badge` (type label and the count chip).
- `checkbox` for the row checkboxes, rendered only in multi-item mode.
- `sonner` for toasts; the app's single `AppShell` mounts the `Toaster`.
- `tooltip` for the footer button; `AppShell` also mounts the `TooltipProvider`.
- `button` for the row `…` button (ghost, icon) and the footer button (outline, small).
- `toggle-group` in the demo only, for the state preview.

Neither the block nor the demo renders `AppShell`, `Toaster` or `TooltipProvider`.

`demo.tsx` shows a "saved links" app with 12 seed items stored through `useCollection("action-palette-demo", seed)`. Each has a title, a domain subtitle, a "Link" or "Note" type label, and sits under a "Pinned" or "Saved" heading. Actions are Open (primary), Copy URL (secondary), Pin or Unpin (⇧⌘P), "Move to…" (sub-menu of three folders), and Delete (⌘⌫, destructive, with a short pending state). Typing a title with no match offers "Create …", which adds a link. Two titles are very long to show truncation. A "Preview state" toggle group above the demo (live, empty, loading, error) switches the block to each state.

The demo also turns on the multi-item target with a controlled `selectedIds`. With rows checked, `getActions` reads its second argument: Open is dropped (it is single-item only), Copy URL becomes "Copy URLs" and copies one newline-joined list through `runMany`, Pin or Unpin reads "Unpin" only when every checked row is pinned, Move to… uses each folder's per-row `run` (the per-item fallback), and Delete becomes "Delete 3" and clears the checked ids in its `runMany`. A plain-text footer under the demo lists the keys.

## Sources

- [raycast study note](../apps/raycast.md), main source for every row below unless another note is named.
- [sentry study note](../apps/sentry.md), source of the multi-item target rows below (S13-bulk-select.png, S13-command-palette.png).
- Panel layout, anchor and filter at the bottom: S1-0051, S1-0048, S2-0019. The manual (S4) says the filter is at the top; we follow the frames.
- Footer hint with primary label and Actions chip, hidden when no panel: S1-0001, S1-0073, S1-0075, S1-0082 (custom primary key, left out). Full-width footer bar with a rule: S1-0004, S3-0045.
- Keys and levels: S4 (↵ primary, Esc backs out), S5 (Esc clears the query first), S7 (primary ↵, secondary ⌘↵).
- Sub-menu: S2-0021. Panel filtering and scroll: S2-0015.
- Loading footer: S1-0060. Success feedback: S1-0052 (screen-center HUD; our design uses a toast instead). Compact mode: S3-0027, left out.
- Fallback when nothing matches: S1-0022.
- Other apps: Linear [study note](../apps/linear.md) (S3-t1126, S1-t0129: command menu names its target item in a chip; we name it in the panel title); Obsidian [study note](../apps/obsidian.md) (S3-0004: first row preselected, key-hint footer).
- Multi-item target. Rows ticked through a checkbox at the left edge, ticked rows keeping their layout, and the toolbar acting on them: S13-bulk-select. A palette whose first group holds page-level actions such as "Mark all issues as" and whose footer lists Move, Select and the toggle key: S13-command-palette. The chip naming the target is Linear's (S3-t1126, S1-t0129 in the Linear study note); S13-bulk-select shows no count label, so the "N selected" wording is ours. The blueprint's key map says ⌘K acts on the selection when rows are selected.
- Text-sourced only: destructive actions in red (S4), flat results while filtering (S4), Esc clearing the query (S5).
- Our design, not seen in any source: ⌘K firing while the search input has focus, `aria-activedescendant` focus model, focus return to the search input, title-prefix ranking, the row `…` actions button with its hover, focus and tab-stop rules, the bordered footer Actions button, 200-row render cap, `/` to focus search, `onCreate` row, "No actions match" row, error toast on a rejected action, chords running with the panel open, and the demo data. For the multi-item target: the `selectedIds` and `onSelectedIdsChange` props, `runMany` with its per-item fallback, the second argument to `getActions`, ⇧⌘X, ⇧↑ and ⇧↓, shift-click range, Esc clearing the checked rows last, the footer count and Clear button, the rule that only checked rows show `…` while rows are checked, and the count chip's wording and placement.
- Unseen in Raycast sources (see its Unseen section): arrow movement inside the open panel, the panel's open and close animation, mouse hover and clicking the footer button. We use the library defaults for these.
