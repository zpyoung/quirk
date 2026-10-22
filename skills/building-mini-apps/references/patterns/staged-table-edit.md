# staged-table-edit

An editable table where cell edits, new rows and deletions stay pending (tinted) until one commit applies them or one discard throws them away, studied in TablePlus.

## When to use

Use it when a person edits many cells in a sitting and wants to review the batch before it is saved.

- Inventory or gear list: fix quantities and locations on 20 rows, check the diff, save once.
- Budget or expense sheet: adjust categories and amounts, preview what changes, commit at month end.
- Content calendar: retitle posts, change status and dates in bulk.
- Data cleanup tool: normalize names and tags across a local collection before overwriting it.

Do not use it when:

- Each change should apply the moment it is made (a todo list, a single record): use `list-peek` or `expand-in-place`, which save on blur.
- Records are long documents or have rich fields that don't fit a cell: use `doc-collections`.
- The person edits one record at a time in a form: use `inspector`.
- The goal is to switch between table, board and list views of the same data: use `view-switcher`.
- The table is read-only, or edits are rare and cheap to undo: a plain `table` is enough.

## Anatomy

```
┌──────────────────────────────────────────────────────────────┐
│ [x Discard] [eye Preview] [Commit ⌘S]   3 pending      [+ Row] │  toolbar ~10%
├────┬───────────────┬──────────┬───────┬──────────────────────┤
│  # │ name          │ category │ qty   │ location             │  header row
├────┼───────────────┼──────────┼───────┼──────────────────────┤
│  1 │ Tent          │ Camping  │ 2     │ Garage               │
│  2 │ Stove         │ Camping  │ ░ 4 ░ │ Garage               │  ░ changed cell (amber)
│  3 │ Headlamp      │ Light    │ 6     │ ▒ Hall closet ▒      │  ▒ ... same tint
│  4 │▒Rope (new)▒▒▒▒│▒▒▒▒▒▒▒▒▒▒│▒▒▒▒▒▒▒│▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│  new row (green)
│  5 │ ~~Old pump~~  │ ~~Misc~~ │ ~~1~~ │ ~~Shed~~             │  removed row (red)
│  … │               │          │       │                      │  scrolls
├────┴───────────────┴──────────┴───────┴──────────────────────┤
│ 1 of 12 rows selected                    4 changed · 1 new · 1 removed │  footer
└──────────────────────────────────────────────────────────────┘
   Preview opens a popover under the eye button, about 45% of the table width:
   ┌ 3 changes ──────────────────────────┐
   │ Stove      qty       2 → 4          │
   │ Headlamp   location  Garage → Hall  │
   │ Rope       new row                  │
   │ [Discard]  [Commit]                 │
   └─────────────────────────────────────┘
```

- **Toolbar**: Discard, Preview and Commit buttons on the left, dim when nothing is pending; a pending count; an add-row button on the right.
- **Header row**: column names, sticky while the body scrolls.
- **Row-number gutter**: muted, narrow, doubles as the row selection target.
- **Body**: rows about 30 px tall, zebra striping, one cell editable at a time.
- **Tints**: amber for a changed cell, green for a new row, red for a removed row.
- **Footer**: selected-row count at the left, pending breakdown at the right.
- **Preview popover**: one line per pending change, in the order edited, with Discard and Commit in its footer.

## Interaction

Keys act on the focused cell or selected row of the table. Bindings use `useHotkeys` and are ignored while focus is in an input, textarea or contenteditable, except where Notes says otherwise.

| Key | Does | Notes |
|-----|------|-------|
| Double-click, Return or Tab | Edit the selected cell | Return/Tab from S3 shortcut text; double-click from S4 |
| Return (while editing) | Accept the edit; it becomes pending | Fires inside the cell input. Accepting the original value clears the pending mark (our design) |
| Esc (while editing) | Cancel the edit, keep the old value | Our design; the Esc cancel path was not seen. Fires inside the cell input |
| Tab (while editing) | Accept and edit the next cell in the row | Our design |
| Esc (not editing) | Deselect | S3 shortcut text |
| ⌘S | Commit all pending changes | Fires inside the cell input: accepts the open edit first, then commits. Always calls `preventDefault` so the browser save dialog never opens (our design). No-op when nothing is pending |
| ⌘⇧Delete | Discard all pending changes | Asks for confirmation first because nothing can bring the changes back (our design) |
| ⌘⇧P | Toggle the preview popover | S3 shortcut text |
| ⌘I | Add a row below the last and edit its first cell | S3 shortcut text |
| ⌘D | Duplicate the selected row as a new pending row | S3 shortcut text |
| Delete / Backspace | Mark the selected rows removed | Pending until commit. On a new row it removes the row outright (our design) |
| ↑ ↓ ← → | Move the focused cell | Our design |
| ⌘↑ / ⌘↓ | Jump to first / last row | S3 shortcut text |

Right-click on a cell opens a context menu with Edit, Duplicate, Set empty and Delete, each with its shortcut right-aligned in grey (S3 quick-filter frame).

**Focus rules**

- Opening an editor focuses its input with the text selected. Accepting or cancelling returns focus to the same cell, not to the page.
- Adding a row scrolls to it and opens its first editable cell.
- Opening Preview moves focus into the popover. Closing it with Esc or ⌘⇧P returns focus to the last focused cell.
- The discard dialog focuses its Cancel button; after either choice focus returns to the table.
- A removed row cannot be edited. Edit keys on it do nothing.
- While a commit runs, the table is not editable and the toolbar shows progress (our design).

**States**

| State | What it shows |
|-------|---------------|
| Empty | Header row stays visible with a "0 rows" label. `EmptyState` fills the body with an "Add row" action (S2-0080; the action is our design) |
| Loading | `LoadingState` in the body while `status` is `"loading"`. Toolbar buttons stay dim. Skeleton rows instead of a spinner when the column set is known (our design) |
| Error (load) | `ErrorState` with the store error and a retry action |
| Error (commit) | Failed changes stay pending and tinted, a toast names the first failure, and changes that were written are cleared from pending. The server-rejection case was not seen in sources (our design) |
| Nothing pending | Discard, Preview and Commit are dim and disabled; ⌘S does nothing (S2-0080, S4-edit-inline) |
| Pending | Buttons bright; the count and the footer breakdown update on every accepted edit (S3-commit-changes-pending) |
| Selected pending row | Keeps its tint as an inset bar and cell outline, because a solid selection fill hid the tint in the source (S3-commit-changes-pending); our design |
| Long content | Cell text truncates with an ellipsis and shows the full value in a tooltip. The editor shows the whole value in a field that may grow taller than the row (S4-edit-inline). Column widths stay fixed; the table scrolls horizontally |
| Many rows | The body scrolls inside a `ScrollArea` with a sticky header and the footer count. No paging up to a few thousand rows (our design; TablePlus pages at 300, S3-table-paging) |

## Borrow / Leave out

Borrow:

- Edits are staged locally and tinted: amber changed, green new, red removed (S3-commit-changes-pending, S3-table-create, S3-discard-changes-button).
- A Discard / Preview / Commit trio that acts on all pending changes at once, dim when nothing is pending.
- An edit is pending only after it is accepted, not while the editor is open (S4-edit-inline).
- Preview lists one entry per change, in the order edited, with only the changed fields, and keeps Discard and Commit in its footer (S3-code-preview-popover, S4-code-review).
- ⌘S commits, and commit gives no toast on success; the table simply loses its tints (S2-0091).
- Discard cannot be undone.
- New rows append at the bottom in edit mode with a placeholder for unset fields (S3-row-insert).
- Dense rows with a muted row-number gutter and zebra striping (S3-the-interface-overview).
- Shortcuts shown right-aligned in the context menu.

Leave out:

- SQL text in Preview: a local mini app has no SQL, so it lists `field old → new` instead.
- Safe Mode and Alert Mode levels: they guard a remote database; a browser store needs one discard confirmation at most.
- Monospace font and the app's blue/red focus outline: the house style supplies type and focus ring.
- Right sidebar form for the selected row: that is `inspector`.
- Filter bar, Quick Filter submenu and column picker: `view-switcher` owns filtering and sorting.
- Data / Structure / Index segmented control and structure editing: out of scope for one table.
- Multi-cell range select, Paste to Selected Cells and Set Value submenu beyond "Set empty": the cost is high and the use is rare in a small table.
- Paging with Limit and Offset: local data is small enough to scroll.
- Console log pane: the success state is the tints disappearing.

## Block API

Public exports of `index.ts`:

```ts
CONTRACT: type StagedColumn<T> = {
  key: keyof T & string
  label: string
  type?: "text" | "number" | "select"       // default "text"
  options?: string[]                         // required when type is "select"
  width?: number                             // px; default 160
  readOnly?: boolean                         // never editable, e.g. computed fields
  placeholder?: string                       // shown in a new row's unset cells
}

CONTRACT: type PendingChange<T> =
  | { kind: "update"; id: string; patch: Partial<T> }
  | { kind: "add"; item: T }
  | { kind: "remove"; id: string }

CONTRACT: StagedTable<T extends { id: string; title: string }>(props: {
  collection: string                         // useCollection name
  columns: StagedColumn<T>[]
  seed?: T[]
  newItem: (id: string) => T                 // blank row factory for add and duplicate
  rowLabel?: (item: T) => string             // used in preview and tooltips; default item.title
  onCommitted?: (changes: PendingChange<T>[]) => void
  onCommitError?: (error: Error, failed: PendingChange<T>[]) => void
}): JSX.Element

CONTRACT: useStagedEdits<T extends { id: string }>(items: T[]): {
  rows: Array<{ item: T; state: "clean" | "changed" | "new" | "removed"; changedKeys: Set<keyof T> }>
  changes: PendingChange<T>[]                // in the order edited
  setCell(id: string, key: keyof T, value: T[keyof T]): void
  addRow(item: T): void
  removeRow(id: string): void
  discard(): void
  settle(applied: PendingChange<T>[]): void  // drops changes the store has written
}

CONTRACT: PendingPreview<T extends { id: string; title: string }>(props: {
  changes: PendingChange<T>[]
  items: T[]
  columns: StagedColumn<T>[]
  onCommit(): void
  onDiscard(): void
}): JSX.Element
```

- `T` needs `title` so Preview and tooltips can name a row. A blank `title` falls back to the id.
- Commit writes through `useCollection` in edit order: `update(id, patch)`, `add(item)`, `remove(id)`. A rejected write stops the run; written changes are passed to `settle`, the rest stay pending. This ordering is our design.
- `useStagedEdits` is exported so an app can render its own toolbar.

Base pieces used:

- `useCollection<T>(collection, seed)` for items and writes.
- `EmptyState`, `LoadingState`, `ErrorState` from `states.tsx`.
- `useHotkeys` from `react-hotkeys-hook` for the keys table; ⌘S and Esc use `enableOnFormTags`.
- `AppShell` wraps the demo only, not the block.

shadcn components, all from the pre-installed list: table, input, select, button, kbd, tooltip, popover, dialog, context-menu, scroll-area, separator, badge, sonner.

`registry-item.json` declares `"registryDependencies"` for the shadcn names above and no extra npm `dependencies`.

`demo.tsx` default-exports `Demo`: a "camping gear" inventory of about 12 items with columns name (text), category (select), qty (number) and location (text), and one name long enough to truncate. Nothing is pre-staged, so the first view shows the dim toolbar. It wraps `StagedTable` in `AppShell`. The collection name is `"gear"`, and the demo notes where to change it to the app's domain.

## Sources

- [tableplus study note](../apps/tableplus.md): all frames below are `references/media/tableplus/`.
- Pending tint and the Discard / Preview / Commit trio: S3-commit-changes-pending.png, S3-discard-changes-button.png, S2-0090.png.
- Amber changed, green new, red removed: S3-commit-changes-pending.png, S3-table-create.png; red as "removed" is an inference noted in the study note's observations.
- Edit becomes pending only after accept; Return then ⌘S: S4-edit-inline.png.
- Preview contents and footer: S3-code-preview-popover.png, S4-code-review.png.
- Commit gives no toast: S2-0091.png.
- Dim buttons, "0 rows" and header kept on an empty table: S2-0080.png.
- New row at the bottom in edit mode: S3-row-insert.png.
- Context menu shortcuts: S3-filter-quick-filter.png. Set Value options: S3-row-set-value.png.
- Row height, gutter, zebra, density: S3-the-interface-overview.png, S5-home.png.
- Loading progress and fetched rows scrollable: S3-streaming-results-and-async-loading-progress.png.
- Paging at 300 rows: S3-table-paging.png.
- Text-sourced from the study note: ⌘S commit, ⌘⇧Delete discard, ⌘⇧P preview, ⌘I, ⌘D, Delete, Return/Tab, Esc deselect, ⌘↑/⌘↓ (S3 shortcut and commit pages); Discard clears undo history (S3 discard-changes page).
- Our design: Esc cancels an edit, Tab moves between cells, arrow-key navigation, discard confirmation, always-`preventDefault` on ⌘S, commit-failure handling, no-op edit clears its mark, tint kept on selected rows, skeleton loading, no paging, the `PendingChange` ordering, the whole API surface and the demo.
- Unseen in sources (study note): commit failure, in-cell Esc, per-change undo, behavior of pending edits on navigation or quit.
