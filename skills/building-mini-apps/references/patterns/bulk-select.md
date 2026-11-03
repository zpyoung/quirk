# bulk-select

A dense table of multi-line rows where ticking any row checkbox turns the column header into an action bar in place, with the count of selected rows, caller-supplied actions that can disable themselves with a stated reason, and an indeterminate select-all box. It was studied in Sentry.

## When to use

Use it when the user scans many similar records, picks some of them and applies one action to the whole pick:

- A photo library: tick a run of shots, then move, tag or delete them together.
- A mail or message inbox: tick threads, then archive, mark done or assign them.
- A task backlog or reading queue: pick the stale ones and snooze or close them in one go.
- A file or download folder: pick several files and move or remove them, with "Delete" disabled and explained when a file is locked.
- A list where each row also carries a small trend, a count and an owner, so the table has real columns (a second table in the same app is fine, such as a list of recorded sessions).

Do not use it when:

- Each record is a single short line that you peek at rather than act on in bulk: use `list-peek`.
- The detail should open under the row, not apply an action to it: use `expand-in-place`.
- Actions are found by typing and apply to one item or a whole list: use `action-palette`. It can sit beside this table and take the selection this block exposes.
- The cells are edited and saved as a batch: use `staged-table-edit`.
- The same records need a table, a board and a calendar: use `view-switcher`.
- The filter row above the table needs `key:value` chips: use `query-tokens` for that row and keep this block for the table.
- The row's main job is a status change with deferred versions ("resolve in the next release"): use `conditional-status` for the split button and keep this block for the table.

## Anatomy

```
+--------------------------------------------------------------------------------+
| [-] [Mark done v] [Archive] [Merge] [...]   2 selected          <- header ~40px |
+--------------------------------------------------------------------------------+
| [x] Refund for a duplicate charge on o...   2min ago  7mo  ||||||||  21K   (MS) |
|     No charge was taken the second time    ........      ||||| 1K              |  row ~84px
|     Billing  T-101  Attachment  Mira S.     Ongoing                             |
+--------------------------------------------------------------------------------+
| [ ] Cannot reset password after email...   10min ago  1yr  |||||||||   785  (  ) |
|     ...                                                                         |
+--------------------------------------------------------------------------------+
  ~3%   ~44% (flexible)                       ~8%     ~6%    ~12%       ~6%   ~8%
```

With nothing selected the same 40px band shows the column headers (Thread, Last activity, Age, Trend, Messages, People, Assignee) and a select-all box in the first column.

- **Header band:** a fixed 40px row above the scrolling rows. With no selection it holds the column headers. With one or more rows selected it becomes the action bar in place: same height, same first column, no layout shift.
- **Select-all box:** the first cell of the band in both modes. Empty when none of the visible rows is selected, a dash when some are, a check when all are.
- **Action bar:** the select-all box, then the caller's actions as small buttons in order, an optional overflow ("...") menu, and a live count ("2 selected") after them. An action with a disabled reason stays in place, dimmed, and shows the reason as a tooltip.
- **Rows:** about 84px tall by default (the caller can set another height; the second table in the demo uses 60px). Each row is a grid: a checkbox column about 44px wide, then the caller's columns. The first column is flexible and usually holds three lines (a bold truncating title, a one-line message, a meta line); numbers are right-aligned and abbreviated.
- **Row states:** a hovered row gets a light tint. The highlighted row (the keyboard cursor) gets a tint and a thin bar on its left edge. Selected rows get the accent tint and keep their layout.
- **Trend cell:** a bar histogram of about 14 to 29 small bars in an inline SVG with a dashed line at the peak, the peak value at the top right, and a one-word state under it ("Ongoing", "New").
- **Assignee cell:** a round avatar button with a caret (an outline when unassigned, initials when assigned). It opens a popover with a header ("Assignee" and a Clear link), an auto-focused search box, and grouped lists (Members, Teams).
- **Empty, loading and error:** the empty card and the error message replace the whole table including the header band. Loading keeps the band and turns every row into placeholder blocks at the final row height.

## Interaction

| Key | Does | Notes |
|-----|------|-------|
| j or ArrowDown | Moves the row highlight down | With nothing highlighted, highlights the first row. Stops at the last row, no wrap. (our design) |
| k or ArrowUp | Moves the row highlight up | With nothing highlighted, highlights the last row. Stops at the first row. (our design) |
| x | Toggles selection of the highlighted row | Does nothing with no highlight. Sets the anchor for Shift-click. (our design) |
| Enter | Calls `onOpen(item)` for the highlighted row | Fires only while focus is on the table or the page body, so Enter on a button inside a row still presses that button. (our design) |
| Esc | Clears the selection | With nothing selected, clears the highlight instead. One step per press. An open popover or menu takes Esc first. (our design) |
| Click (row checkbox) | Toggles that row and highlights it | Sets the anchor. |
| Shift-click (row checkbox) | Gives every row between the anchor and the clicked row the clicked row's new state | With no anchor it acts as a plain click. Optional. (our design) |
| Click (select-all box) | None or some selected: selects every visible row. All selected: clears the selection | The box shows none, some or all of the visible rows. (our design) |
| Click (elsewhere in a row) | Highlights the row | Clicks on a button, link or input inside a cell do nothing to the row. |
| Double-click (row) | Highlights the row and calls `onOpen(item)`, the same as Enter | (our design) |
| Tab | Moves from the table to the controls inside it | The select-all box, the action buttons and each row's assignee button are tab stops. Row checkboxes are not, because x covers the keyboard. |

Keys act only when focus is on the page body or inside the block, and never while typing in an input, a textarea or a contenteditable (the base `useHotkeys` default). That includes the assignee search box. The block binds no ⌘N, ⌘T, ⌘W or ⌘L.

**Focus rules.**

- Focus stays on the table for the whole session; the highlighted row is exposed with `aria-activedescendant`, so j and k never move focus.
- Clicking a row or a checkbox puts focus on the table, so the keys work straight after a click.
- Esc in the assignee popover closes it and returns focus to the button that opened it. The selection is untouched.
- Choosing an assignee closes the popover and leaves the highlight where it was.

**Selection rules.**

- The selection is a list of ids in row order. The block holds it unless the caller passes `selectedIds`; either way `onSelectedIdsChange` reports every change, so a host can hand the selection to another pattern (for example an `action-palette` target) without importing one.
- Only rows the table is showing can be selected. When rows leave `items` (removed, or filtered out by the host), their ids drop out of the selection and the callback reports it.
- Actions receive the selected ids in row order and decide what they do. After an action removes rows, the pruning above empties the selection and the bar returns to the column header.
- Merge-style actions that depend on the selection set `disabledReason` from the selection the host already holds.
- The count is announced politely each time it changes.

| State | Shows |
|-------|-------|
| Empty (no items) | `EmptyState` in place of the table with the caller's title, description and optional action. No header band. |
| Empty (filter matches nothing) | The same card, with the caller's wording that names the cause and a "Clear" action. The host owns the filter, so the block does not tell the two apart. |
| Loading | The header band stays; each row becomes placeholder blocks at the row height. Keys do nothing and no action bar shows. |
| Error | `ErrorState` with the error message and a Retry button when `onRetry` is given. |
| Nothing selected | Column headers in the band; no action bar. |
| Action disabled | The button stays in place and dimmed, stays focusable, and a tooltip gives the reason. Activating it does nothing. |
| Very long title | The caller's cell truncates with an ellipsis; the block never wraps the row to a taller height. |
| Many rows | The rows scroll under a pinned band and the highlighted row is kept in view (`block: "nearest"`). Not virtualized; fine to a few hundred rows. |
| Narrow container | The table scrolls sideways inside its container instead of dropping columns. |

## Borrow / Leave out

Borrow:

- The header band that turns into the action bar in place, at the same height, with the select-all box staying put.
- The select-all box with three states (none, some, all), shown as a dash when some rows are selected.
- A bar of split-style actions with an overflow ("...") menu; disabled actions explain themselves in a sub-line (the overflow menu) or a tooltip (the bar).
- Rows about 84px tall with a three-line first cell, right-aligned abbreviated numbers and relative times.
- The trend cell: a mini bar histogram with its peak value in the top right and a state word under it.
- The assignee cell: an avatar button with a caret, a popover with a header and Clear link, an auto-focused search, and grouped lists.
- The loading rows as placeholder blocks at the final row height, with the header kept.
- The empty card that replaces the table and says why nothing matches.
- A second use of the same table for a list of recorded sessions (select, name and meta, device, duration, errors, a segmented activity bar).

Leave out:

- The look of the studied app (colors, severity bars, brand icons). The block uses the app's theme tokens.
- Its copy and domain: the demo uses invented threads and recordings, never issues or real people.
- Resolve and archive menus with deferred conditions: that is `conditional-status`. Here an action is a button the caller defines.
- Priority and status pills, the project badge and the replay-count chip: the caller renders any of these in a cell.
- "Invite member" in the assignee popover: it needs a real backend.
- Sorting, paging and the filter row: the host owns them.
- The Most Dead Clicks and Most Rage Clicks cards above the replay list.
- The boot splash on first load.

## Block API

Files in `gallery/src/patterns/bulk-select/`: `registry-item.json`, `index.ts`, `types.ts`, `selection.ts`, `trend.ts`, `assignees.ts`, `indeterminate-checkbox.tsx`, `action-bar.tsx`, `trend-cell.tsx`, `assignee-cell.tsx`, `bulk-select.tsx`, `demo-data.ts`, `demo.tsx`.

```
CONTRACT: type BulkSelectRow = { id: string }

CONTRACT: type BulkSelectColumn<T> = {
  id: string
  header?: ReactNode                 // text in the header band; omit for a blank header
  width?: string                     // CSS grid track, default "minmax(0, 1fr)"; use rem or fr, e.g. "6rem"
  align?: "start" | "end"            // default "start"
  cell: (item: T) => ReactNode
}

CONTRACT: type BulkSelectAction = {
  id: string
  label: string
  icon?: ReactNode
  onSelect: (ids: string[]) => void  // selected ids in row order
  disabledReason?: string            // set: the action is disabled and this is shown as its tooltip
  overflow?: boolean                 // list it in the "..." menu instead of as a button
}

CONTRACT: BulkSelect<T extends BulkSelectRow>(props: BulkSelectProps<T>): JSX.Element

CONTRACT: type BulkSelectProps<T extends BulkSelectRow> = {
  items: T[]                         // the visible rows; the host filters and sorts
  columns: BulkSelectColumn<T>[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  actions?: BulkSelectAction[]
  selectedIds?: string[]             // controlled; omit for internal state
  onSelectedIdsChange?: (ids: string[]) => void
  highlightedId?: string | null      // controlled; omit for internal state
  onHighlightedIdChange?: (id: string | null) => void
  onOpen?: (item: T) => void         // Enter or double-click; the host decides what opening means
  rowHeight?: number                 // px, default 84
  minWidth?: string                  // below this the table scrolls sideways, default "44rem"
  rowLabel?: (item: T) => string     // accessible name of a row checkbox, default the row id
  selectionNoun?: string             // "thread" gives "2 threads selected"; default "row"
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}

CONTRACT: IndeterminateCheckbox(props: { checked: boolean | "mixed"; onToggle: (event: { shiftKey: boolean }) => void; label: string; tabIndex?: number; disabled?: boolean; className?: string }): JSX.Element
CONTRACT: ActionBar(props: { actions: BulkSelectAction[]; selectedIds: string[]; selectionState: SelectionState; noun: string; onToggleAll: () => void }): JSX.Element
CONTRACT: TrendCell(props: { values: number[]; caption?: string; label?: string }): JSX.Element
CONTRACT: type AssigneeOption = { id: string; name: string; hint?: string }
CONTRACT: type AssigneeGroup = { id: string; label: string; options: AssigneeOption[] }
CONTRACT: AssigneeCell(props: { value: string | null; groups: AssigneeGroup[]; onChange: (id: string | null) => void; label?: string }): JSX.Element
CONTRACT: type SelectionState = "none" | "some" | "all"
CONTRACT: selectionState(selectedCount: number, rowCount: number): SelectionState
CONTRACT: toggleId(order: string[], selected: string[], id: string): string[]
CONTRACT: setRange(order: string[], selected: string[], anchorId: string, targetId: string, on: boolean): string[]
CONTRACT: pruneSelection(order: string[], selected: string[]): string[]
CONTRACT: nextHighlight(order: string[], current: string | null, direction: "next" | "previous"): string | null
CONTRACT: neighbourAfterRemoval(previousOrder: string[], order: string[], id: string): string | null
CONTRACT: trendBars(values: number[]): { peak: number; bars: Array<{ x: number; width: number; height: number }> }
CONTRACT: formatCount(value: number): string
CONTRACT: filterAssigneeGroups(groups: AssigneeGroup[], query: string): AssigneeGroup[]
```

`index.ts` exports `BulkSelect`, `IndeterminateCheckbox`, `ActionBar`, `TrendCell`, `AssigneeCell`, the functions `selectionState`, `toggleId`, `setRange`, `pruneSelection`, `nextHighlight`, `neighbourAfterRemoval`, `trendBars`, `formatCount` and `filterAssigneeGroups`, and the types `BulkSelectProps`, `BulkSelectRow`, `BulkSelectColumn`, `BulkSelectAction`, `AssigneeOption`, `AssigneeGroup` and `SelectionState`. `demo.tsx` default-exports `Demo`. The block never imports another pattern.

Uses from the base:

- `useCollection` in the demo only; `BulkSelect` takes `items` and `status` as props and does not read the store.
- `EmptyState`, `LoadingState`, `ErrorState` from `src/components/mini/states.tsx` for the empty, loading and error states. The loading state keeps the header band and draws its own placeholder rows at the row height, with `LoadingState` giving the polite status text for assistive tech.
- `useHotkeys` from `react-hotkeys-hook` for every key.
- shadcn components, all pre-installed: `button`, `tooltip`, `dropdown-menu`, `popover`, `command` and `skeleton` in the block; `badge` and `input` in the demo. The tooltip host comes from the app's one `AppShell`. No new dependencies.

`demo.tsx` renders neither `AppShell` nor a toaster. It shows a shared inbox of 12 threads stored with `useCollection("bulk-select-demo", seed)`: subject (one deliberately very long), preview, sender, mailbox (Billing, Support, Sales), a 14-day message count, messages, people, assignee, last activity and age. The table has Thread, Last activity, Age, Trend, Messages, People and Assignee columns. Actions are "Mark done" and "Archive" (they remove the rows), "Merge" (disabled with a reason when the selection spans mailboxes or holds fewer than two threads), and an overflow menu with "Mark unread" and "Delete" (disabled with the reason "You do not have permission to delete threads"). A search box and mailbox buttons filter the table, so an empty filter result shows the cause card. The selected ids are shown in a line above the table to show what a host receives. A "Table" control switches to a second table of 8 recordings (60px rows: name and meta, device, length, bookmarks, a segmented activity bar) built on the same block. A "State preview (demo only)" control (live, empty, loading, error) forces each state; the empty state offers "Restore sample threads", and Retry in the error state returns to live. A plain-text footer lists the key and click hints.

## Sources

[sentry study note](../apps/sentry.md). The key map, the selection rules, the pruning behavior and everything marked "our design" are not from a source.

- **Header band becomes the action bar, select-all with a dash, Resolve, Archive, Merge, Set Priority and overflow buttons, selected rows keep their layout:** `S13-bulk-select.png`.
- **Merge dimmed with two issues from different projects selected (not confirmed by hover):** `S13-bulk-select.png`. The block makes the reason explicit.
- **Disabled overflow item that explains itself in a sub-line:** `S13-more-actions-menu.png`.
- **Bar with nothing selected, buttons greyed above the first row:** `S2-t0030.png`.
- **Select-all box in the first column beside the "Issue" header:** `S8-unsaved-changes.png`, `S3-t1220.png`.
- **Table columns, right-aligned abbreviated numbers, relative times, 84px rows under a 40px sticky header, three-line first cell:** `S13-issue-stream.png`.
- **Trend cell with a 29-bar histogram, the peak in the top right and a state word under it:** `S13-issue-stream.png`.
- **Hover lightens the whole row, nothing else changes:** `S13-row-hover.png`.
- **Assignee avatar button with a caret, outline when unassigned:** `S2-t0030.png`.
- **Assignee popover with a header and Clear link, auto-focused search, grouped Members and Teams lists, Esc closes without assigning:** `S13-assign-menu.png`. The Invite button is left out.
- **Loading rows as placeholder blocks at the final row height with the header kept:** `S13-issue-stream-skeleton.png`.
- **Empty card replacing the table, column headers gone, cause named:** `S13-issue-stream-empty-filter.png`.
- **Second use of the table for a list of sessions (select box, user and meta, duration, errors, segmented activity bar, rows about 59px):** `S13-replay-list.png`.
- **No row-level keys advertised, Tab order starts in the header:** `S13-tab-focus.png`. The row keys are our design.
- **Our design:** j and k and the arrow keys, x, Enter and double-click calling `onOpen`, Esc clearing the selection and then the highlight, Shift-click range selection, the select-all click rules, the live count in the bar, the highlight bar on the left edge, controlled and uncontrolled selection with `onSelectedIdsChange`, pruning ids that leave `items`, `disabledReason` shown as a tooltip on the bar buttons, the row checkbox tab-stop rule, the sideways scroll on narrow containers, and the demo's inbox, recordings and filter.
