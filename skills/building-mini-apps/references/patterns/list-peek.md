# list-peek

A dense one-line-per-row list where j/k (and the arrow keys) move a highlight and Space previews the highlighted item in a side panel without leaving the list. It was studied in Linear.

## When to use

Use it when the user scans many similar records and needs a closer look at one before deciding anything:

- A reading list: skim titles and statuses, peek for the author, notes and dates.
- A bug or task triage list: step through items quickly, peek for the description and history.
- A saved-snippets or bookmarks list: peek renders the full text or link preview.
- A contacts or inventory list where each row is a few fields and the detail is a short card.

Do not use it when:

- Each record is one short row and the detail is a few more lines: use `expand-in-place` so nothing moves to a side panel.
- The user edits the record while looking at it, or wants a permanent detail pane: use `workspace-panes` (or `inspector` for a property sidebar on a selected object).
- The main task is acting on rows (move, tag, delete): use `action-palette` and treat peek as optional.
- The data is a wide, editable grid: use `staged-table-edit`.

## Anatomy

```
+--------------------------------------------------------------+
| Toolbar: [ filter input (/) ]                      12 items   |  ~44px
+---------------------------------------+----------------------+
| TO READ  4                            | 3 / 12   [^] [v]  [x]|  group band ~36px
| ------------------------------------- | -------------------- |
| BK-04  Title of the first item   Meta | Title (wraps, max 3) |
|>BK-05  Highlighted row ......... Meta | status . added . id  |  rows ~40px
| BK-06  A very long title that tru... M| -------------------- |
| READING  2                            | Body: scrolls inside |
| BK-01  Another group row ....... Meta | a ScrollArea.        |
|                                       |                      |
+---------------------------------------+----------------------+
|              list ~58%                |     peek ~42%        |
+--------------------------------------------------------------+
```

- **Toolbar:** filter input and an item count. The input is the only focusable control outside the list and the panel.
- **List:** a scrolling listbox. Optional group bands (name and count) sit between rows. Each row has a fixed-width leading column (the ID), the title, and right-aligned metadata.
- **Highlight:** a faint full-width tint on the highlighted row; no checkbox or border. A hovered row gets a lighter tint than a highlighted one.
- **Peek panel:** appears only while peek is open and pushes the list narrower; the list stays interactive. Header holds an "n / total" counter, previous/next buttons and a close button. The body is caller-rendered and scrolls independently.
- **Narrow windows (under 720px):** the panel covers the list instead of splitting it; Esc returns to the list.

## Interaction

| Key | Does | Notes |
|-----|------|-------|
| j or ArrowDown | Highlights the next row | Skips group bands. With nothing highlighted, highlights the first row. While peek is open, the panel follows. |
| k or ArrowUp | Highlights the previous row | With nothing highlighted, highlights the last row. Stops at the ends, no wrap. |
| Space (tap) | Opens peek for the highlighted row; a second tap closes it | With no highlight, uses the row under the pointer. Does nothing if neither exists. |
| Space (hold) | Peek shows only while the key is down | A press held longer than 250ms closes peek on release. |
| Enter | Calls `onOpen(item)` | No-op when `onOpen` is not given. |
| Esc | Closes peek; if closed, clears the highlight; if the filter has text, clears that first | One step per press. |
| / | Focuses the filter input | |
| Home / End | Highlights first / last row | |

List keys act only when focus is on the page body or inside the block, and never while typing in the filter input, a textarea or a contenteditable (the base `useHotkeys` default). Keys do nothing while focus is inside the open panel, except Esc, which closes it. The filter input has two keys of its own: Esc clears the text, then blurs the input; ArrowDown moves focus to the list and highlights the first row.

**Focus rules.**

- Focus stays on the list container for the whole session; the highlighted row is exposed with `aria-activedescendant`, so opening and closing peek never moves focus.
- Tab moves from the list into the panel (so links and buttons inside it are reachable). Esc inside the panel closes it and returns focus to the list.
- Clicking a row highlights it; if peek is open the panel retargets. Clicking does not open peek.
- If the peeked item is removed, peek closes and the highlight moves to the next row, or the previous one at the end.

| State | Shows |
|-------|-------|
| Empty (no items) | `EmptyState` filling the list area with a one-line hint and an optional `emptyAction` button. No panel. |
| Empty (filter matches nothing) | `EmptyState` naming the filter text and a "Clear filter" action. Peek closes. |
| Loading | `LoadingState` in the list area; keys do nothing. Toolbar stays visible. |
| Error | `ErrorState` with the error message and a Retry button when `onRetry` is given. |
| Very long title | Row title truncates with an ellipsis and metadata truncates first; full title is in the `title` attribute. In the panel the title wraps to at most 3 lines. |
| Long panel content | The panel body scrolls inside its own `ScrollArea`; the header stays pinned. |
| Many items | The list scrolls and the highlighted row is kept in view (`block: "nearest"`). Not virtualized; fine to a few hundred rows. |

## Borrow / Leave out

Borrow:

- Dense single-line rows about 40px tall with a fixed ID column so titles line up.
- Right-aligned metadata that truncates before the title does.
- Thin group bands with name and count, slightly tinted; hairline row separators.
- j/k and arrows move a highlight; nothing is highlighted when the list first loads.
- Space toggles peek on a tap and peeks only while held on a long press.
- Space works on the hovered row when nothing is highlighted.
- "n / total" with previous/next buttons in the detail header.
- Empty states that say why the list is empty and offer the control that undoes it.
- Low-contrast structure: faint highlight tint, hairlines, no heavy borders.

Leave out:

- X to select, Shift to extend, and bulk actions: peek is read-only here; bulk work belongs to `action-palette`.
- Priority, status and avatar icons, and label pills: they are Linear's brand vocabulary; the caller supplies plain text metadata.
- Inline create buttons on group bands: creation is the app's concern, not the pattern's.
- Cmd+K, Shift+V display options and the filter popover: other patterns own them.
- Board layout and Cmd+B list/board toggle: that is `view-switcher`.
- Illustrated empty states: base `EmptyState` is text only.

## Block API

Files in `gallery/src/patterns/list-peek/`: `registry-item.json`, `index.ts`, `list-peek.tsx`, `demo.tsx`.

```
CONTRACT: type ListPeekItem = { id: string; title: string }

CONTRACT: ListPeek<T extends ListPeekItem>(props: ListPeekProps<T>): JSX.Element

CONTRACT: type ListPeekProps<T extends ListPeekItem> = {
  items: T[]
  status?: "loading" | "ready" | "error"            // default "ready"; pass useCollection's status
  error?: Error
  onRetry?: () => void
  renderPeek: (item: T) => ReactNode                // panel body
  renderLead?: (item: T) => ReactNode               // fixed-width leading column, e.g. an ID
  renderMeta?: (item: T) => ReactNode               // right-aligned, truncates first
  groupBy?: (item: T) => string                     // group band per distinct value, in first-seen order
  filterText?: (item: T) => string                  // text the filter input matches; default is the title
  onOpen?: (item: T) => void                        // Enter
  highlightedId?: string | null                     // controlled; omit for internal state
  onHighlightedIdChange?: (id: string | null) => void
  peekOpen?: boolean                                // controlled; omit for internal state
  onPeekOpenChange?: (open: boolean) => void
  holdThresholdMs?: number                          // default 250
  emptyTitle?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}
```

`index.ts` exports `ListPeek`, `ListPeekItem` and `ListPeekProps`. `demo.tsx` default-exports `Demo`.

Uses from the base:

- `useCollection` in the demo only; `ListPeek` takes `items` and `status` as props and does not read the store.
- `EmptyState`, `LoadingState`, `ErrorState` from `src/components/mini/states.tsx` for all list-area states.
- `useHotkeys` from `react-hotkeys-hook` for all keys. Hold detection uses its `keydown` and `keyup` options, ignores `event.repeat`, and clears on window blur.
- shadcn components, all pre-installed: `scroll-area`, `input`, `button` in the block; `badge` and `kbd` in the demo. No new dependencies.

`demo.tsx` renders neither `AppShell` nor a toaster; the app wraps everything in one `AppShell`. It shows a reading list of 14 books stored with `useCollection("list-peek-demo", seed)`. Fields: `id` ("BK-01"), `title`, `author`, `status` ("To read", "Reading", "Done"), `added` date, `notes`. Grouped by status; one title is deliberately very long; one group has a single item. `renderLead` shows the ID, `renderMeta` the author, `renderPeek` the title, a badge row, notes and dates. A line under the list reports the item Enter opened, and a footer lists the keys with `kbd`. A "State preview (demo only)" button group (live, empty, loading, error) forces each state; the empty state offers "Restore sample books", and Retry in the error state returns to live.

## Sources

[linear study note](../apps/linear.md). Peek-panel layout, the keyboard hold timing, hover rules and everything marked "our design" are not from a source.

- **J/K, arrows, Esc, nothing highlighted by default:** S4 text (`S4-select-issues.png`) and S7 text. Behavior of the highlight against hover and Esc priority were not shown (study note, Unseen): our design.
- **Space toggles peek, hold peeks while held:** S5 text, a user decision to build from docs text. Hold threshold 250ms is our design.
- **Space on a hovered row:** S6 text.
- **Row density, fixed ID column, metadata truncating before the title:** `S1-t0066.png`, `S1-t0072.png`, `S1-t0042.png` (two-line variant, not used).
- **Group bands with counts and tint:** `S1-t0066.png`, `S1-t0138.png`.
- **Faint full-width highlight, no checkbox:** `S2-t0096.png`.
- **"n / total" with previous/next:** `S3-t1050.png`, moved from Linear's full issue page into the peek header (our design).
- **Empty state that names the cause and offers the undo:** `S1-t0111.png`.
- **Low-contrast structure:** S8 text.
- **Side-by-side list and preview proportions:** [raycast study note](../apps/raycast.md), S3-0004 (list about 38%, preview about 62%); [notion study note](../apps/notion.md), S4 (side peek keeps the view interactive). The 58/42 split is our design.
- **Esc clears the query before closing:** [raycast study note](../apps/raycast.md), S5 text. Applied to the filter input.
- **Hover tint lighter than selected:** [fantastical study note](../apps/fantastical.md), S2-0031.
- **Text-sourced (no frame shows it):** the peek panel's behavior, J/K highlighting, and peek on a hovered row come from docs text only. The panel's layout is designed in the neutral house style.
- **Our design:** peek panel layout, push versus overlay, 720px breakpoint, Home/End, `/` to focus the filter, Enter calling `onOpen`, panel following the highlight, focus rules, removal behavior, narrow-window cover, and the panel header buttons.
