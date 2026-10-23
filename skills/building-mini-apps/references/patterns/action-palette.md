# action-palette

A searchable list where one row is selected and ⌘K opens a small panel of actions for that row, studied in Raycast's root search, file and app lists.

## When to use

Use it when every item can have several different things done to it and the keyboard is the main input.

- A bookmark manager: Open, Copy URL, Edit, Move to folder…, Delete.
- A snippet or clipboard library: Paste, Copy, Pin, Delete.
- A reading list: Open, Mark read, Archive, Copy link.
- A local "do anything" launcher over a small set of saved commands or files.

Do not use it when:

- The item only needs one action, or a view and an edit. Use `list-peek` (a preview beside the list) or `expand-in-place`.
- The user edits many fields or rows before committing. Use `staged-table-edit`.
- Items are documents the user reads and writes in the app. Use `doc-collections`.
- The user needs details on screen beside the list, not a menu of verbs. Use `inspector`.

## Anatomy

Proportions are approximate, from S1-0001 and S1-0051 (list window about 1.6:1; panel about 45% of window width).

```
┌──────────────────────────────────────────────────────┐
│ ⌕  Search…                                  (hint)   │  search row, ~70px
├──────────────────────────────────────────────────────┤
│  SECTION                                             │
│ ▌Row title            subtitle              type     │  rows ~44px, 8 visible
│  Row title            subtitle              type     │
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
- **Footer bar:** left slot for the app or view name, replaced by a spinner and message while an action runs, or a toast. Right slot names what ↵ does for the selected row, then an "Actions ⌘K" chip.
- **Action panel:** a card with the selected item's title, action rows (icon-free in our house style, shortcut keycaps at the right), thin separators between groups, and a filter input at the bottom edge. The list underneath stays visible and is not dimmed.

## Interaction

| Key | Does | Notes |
|---|---|---|
| Type | Filters the list; selection resets to the first match | Substring match on title plus any extra search text; title prefix matches rank first (our design) |
| ↑ / ↓ | Moves the selection | Works while the search input has focus. Stops at the ends |
| ⌘K (Ctrl K) | Opens the panel for the selected row; closes it if open | Fires even while typing in the search input. Does nothing when no row is selected or the row has no actions |
| ↵ | Runs the primary action of the selected row | With the panel open, runs the highlighted action instead. A primary action that has `children` opens the panel on its sub-menu instead of running |
| ⌘↵ (Ctrl ↵) | Runs the secondary action | Only when the row has a second action; otherwise ignored. Inside an open sub-menu it does nothing |
| Action chord, such as ⇧⌘F | Runs that action on the selected row | Works with the panel open or closed, including while typing in the search or panel input. Sub-menu actions can carry chords too. Chords are ignored while focus is in a text field outside the block |
| Esc | Backs out one level: sub-menu, then panel, then a non-empty query | With an empty query and no panel it does nothing. Works while typing in the search or panel input |
| / | Focuses the search input | Our design; only when focus is not in a text field |

**Focus rules**

- The search input has focus at all times when the panel is closed. The list never takes focus; the selection moves through `aria-activedescendant`.
- Opening the panel moves focus to its filter input and highlights the first action (S1-0051). Typing narrows actions to one flat list, ignoring sections (S4).
- Choosing a row that ends in "…" and has children replaces the panel's contents in the same card. The title becomes that action's name and the placeholder shortens (S2-0021). Esc returns to the parent list with its filter cleared.
- Closing the panel by Esc, by running an action or by clicking outside returns focus to the search input. The query and the selected row are kept.
- Esc with a non-empty query clears it (S5). Our design adds nothing further, since a web page has no window to close.

**States**

| State | Shows |
|---|---|
| Empty collection | `EmptyState` in the list area with a one-line prompt to add the first item. Footer shows no Actions chip |
| No matches | Message with the query, "No results for “…”". If `onCreate` is given, a first row "Create “…”" is selected; this is our design, adapted from the fallback rows in S1-0022 |
| Loading | `LoadingState` in the list area. The search input stays enabled and ⌘K does nothing |
| Error | `ErrorState` with a retry button when `onRetry` is given |
| Action running | Footer left slot shows a spinner and the action's `pending` label; the list stays usable (S1-0060) |
| Action done or failed | Success shows a `sonner` toast when `successMessage` is set; a rejected `run` shows an error toast with the error message and keeps the panel closed. Failure feedback is our design (S2 and S1 showed only success) |
| Long titles | Rows and the panel header truncate to one line with an ellipsis; the full title is in the `title` attribute. Action titles truncate the same way |
| Many items | The list scrolls inside `ScrollArea`; only the first 200 matches render, with a final row "Showing 200 of N. Keep typing to narrow". Our design |
| Many actions | Panel body scrolls, about 8 rows tall (S2-0015); the filter input stays pinned at the bottom. Destructive actions sort last, below a separator |
| No matching action | One muted row "No actions match" in the panel; ↵ does nothing. Not seen in sources, our design |
| Item has no actions | The footer shows only the primary label if any, and no Actions chip (S1-0075) |

## Borrow / Leave out

**Borrow**

- Panel as a floating card over the list's lower right, list still visible (S1-0051).
- Panel anatomy: item title, action rows with keycap shortcuts, separators, filter input at the bottom (S1-0051, S1-0048).
- First action is primary (↵), second is secondary (⌘↵) (S7, S2-0019).
- Footer that names the primary action for the current row and shows the ⌘K chip, hidden when the row has no panel (S1-0001, S1-0073, S1-0075).
- One keycap per key of a chord, modifier glyphs that change by platform (S1-0048, S1-0004).
- Filtering the panel as a flat substring match (S2-0015, S4).
- Sub-menus that replace the panel contents, and "…" on rows that lead to another view (S2-0021).
- Esc backs out one level; the first Esc clears the query (S4, S5).
- Spinner and message in the footer while an action runs (S1-0060).
- Destructive actions drawn in red (S4, text only).

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

## Block API

Files in `src/patterns/action-palette/`: `index.ts` re-exports `ActionPalette`, `ActionPanel`, `ShortcutKeys`, `formatShortcut` and the types `PaletteItem`, `PaletteAction`, `ActionPaletteProps` and `ActionPanelProps`; `demo.tsx` default-exports `Demo`. `registry-item.json` declares `dependencies` `react-hotkeys-hook` and `sonner`.

```ts
// CONTRACT: item and action types
type PaletteItem = { id: string; title: string };

type PaletteAction<T extends PaletteItem> = {
  id: string;
  title: string;                       // end with "…" when `children` is set
  run?: (item: T) => void | Promise<void>;
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
  getActions: (item: T) => PaletteAction<T>[];  // first = primary, second = secondary
  getSubtitle?: (item: T) => string | undefined;
  getMeta?: (item: T) => string | undefined;    // right-aligned type label
  getSearchText?: (item: T) => string;          // extra words matched besides title
  getSection?: (item: T) => string | undefined; // row group headings, shown while the query is empty
  onCreate?: (query: string) => void;           // enables the "Create “…”" row
  placeholder?: string;
  footerLabel?: string;                         // left footer slot, default none
  emptyState?: { title: string; description?: string; action?: ReactNode };
};

// CONTRACT: type ActionPanelProps<T extends PaletteItem> = { item: T; actions: PaletteAction<T>[]; onClose: () => void; onRun: (action: PaletteAction<T>) => void }
// CONTRACT: <ActionPanel<T extends PaletteItem> {...ActionPanelProps<T>} />   the card ActionPalette renders; usable on its own
// CONTRACT: <ShortcutKeys shortcut={string} />       renders one keycap per key, glyphs by platform
// CONTRACT: formatShortcut(shortcut: string): string[]   e.g. ["⌘", "⇧", "F"] on macOS, ["Ctrl", "Shift", "F"] elsewhere
```

Uses these base pieces:

- `useHotkeys` from `react-hotkeys-hook`: `mod+k` with `enableOnFormTags: true` (the one binding allowed to fire inside an input); `enter` and `mod+enter` also with `enableOnFormTags` but scoped to the search input; action chords with default form-tag blocking.
- `EmptyState`, `LoadingState`, `ErrorState` from `states.tsx`.
- `useCollection` is called by `demo.tsx`, not by the block: the block takes `items` and `status`, so any source can feed it.

shadcn components, all from the pre-installed list:

- `input` for search.
- `command` (cmdk) for the panel's filtered list and bottom input.
- `kbd` for keycaps.
- `scroll-area`, `separator`, `badge` (type label).
- `sonner` for toasts; the app's single `AppShell` mounts the `Toaster`.
- `tooltip` for the footer chip; `AppShell` also mounts the `TooltipProvider`.
- `toggle-group` in the demo only, for the state preview.

Neither the block nor the demo renders `AppShell`, `Toaster` or `TooltipProvider`.

`demo.tsx` shows a "saved links" app with 12 seed items stored through `useCollection("action-palette-demo", seed)`. Each has a title, a domain subtitle, a "Link" or "Note" type label, and sits under a "Pinned" or "Saved" heading. Actions are Open (primary), Copy URL (secondary), Pin or Unpin (⇧⌘P), "Move to…" (sub-menu of three folders), and Delete (⌘⌫, destructive, with a short pending state). Typing a title with no match offers "Create …", which adds a link. Two titles are very long to show truncation. A "Preview state" toggle group above the demo (live, empty, loading, error) switches the block to each state.

## Sources

- [raycast study note](../apps/raycast.md), main source for every row below unless another note is named.
- Panel layout, anchor and filter at the bottom: S1-0051, S1-0048, S2-0019. The manual (S4) says the filter is at the top; we follow the frames.
- Footer hint with primary label and Actions chip, hidden when no panel: S1-0001, S1-0073, S1-0075, S1-0082 (custom primary key, left out). Full-width footer bar with a rule: S1-0004, S3-0045.
- Keys and levels: S4 (↵ primary, Esc backs out), S5 (Esc clears the query first), S7 (primary ↵, secondary ⌘↵).
- Sub-menu: S2-0021. Panel filtering and scroll: S2-0015.
- Loading footer: S1-0060. Success feedback: S1-0052 (screen-center HUD; our design uses a toast instead). Compact mode: S3-0027, left out.
- Fallback when nothing matches: S1-0022.
- Other apps: Linear [study note](../apps/linear.md) (S3-t1126, S1-t0129: command menu names its target item in a chip; we name it in the panel title); Obsidian [study note](../apps/obsidian.md) (S3-0004: first row preselected, key-hint footer).
- Text-sourced only: destructive actions in red (S4), flat results while filtering (S4), Esc clearing the query (S5).
- Our design, not seen in any source: ⌘K firing while the search input has focus, `aria-activedescendant` focus model, focus return to the search input, title-prefix ranking, 200-row render cap, `/` to focus search, `onCreate` row, "No actions match" row, error toast on a rejected action, chords running with the panel open, and the demo data.
- Unseen in Raycast sources (see its Unseen section): arrow movement inside the open panel, the panel's open and close animation, mouse hover and clicking the footer chip. We use the library defaults for these.
