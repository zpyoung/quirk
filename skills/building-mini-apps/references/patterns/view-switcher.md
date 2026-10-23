# view-switcher

One set of records shown through named view tabs (table, board, list, calendar), each tab keeping its own filter and sort, with a record opening in a docked side panel; studied mainly in Notion databases. Optionally the views are saved slices: a view keeps its query, sort and filters together, and changes not yet saved show a dot on its tab with Save, Save as new view and Reset. It was studied in Notion and Sentry.

## When to use

Use it when the same records are worth seeing in more than one shape, and the user returns to the same slices often:

- A task or project tracker: a table to scan everything, a board by status, a calendar by due date.
- A content or event planner: a calendar for publish dates plus a "drafts only" list.
- A small CRM or reading list: a table for sorting, a board by stage, saved filters like "this month".
- A recipe or inventory log where records carry a status and a date.
- A support queue, order list or reading backlog where people tune a search, sort and filters, then keep the result as a named view or discard it (turn on `trackUnsaved`).

Do not use it when:

- There is one natural shape and no saved slices. A single list that opens a record in place is `list-peek`.
- Records are free-form documents, not rows with fields. Use `doc-collections`.
- The user edits many cells at once and reviews changes before saving. Use `staged-table-edit`.
- The "views" are different tools or panes of one workspace, not one data set seen differently. Use `workspace-panes`.
- The panel is the main thing (a long property form or detail editor). Use `inspector`.
- The query is the main control and needs `key:value` tokens with suggestions. Use `query-tokens`; saved views here keep only a plain search string.
- Views are shared with other people or have permissions. Neither exists here.

## Anatomy

```
+--------------------------------------------------------------+------------------+
| Title                                                         |                  |
| [Table] [Board] [Calendar] [Drafts] [+]     (F) (S) Search ( ) |  Record panel    |
| Status: any of Idea, Drafting x   + Add filter                 |  (about 35%)     |
|----------------------------------------------------------------|  Title (wraps)   |
|                                                                |  Status   Idea   |
|   active layout: table / board / list / calendar               |  Host     Empty  |
|   (fills remaining height, scrolls on its own)                 |  Date     12 Nov |
|                                                                |                  |
|----------------------------------------------------------------|  [Delete]   [x]  |
| Count 11   (calendar: No date 2)                  + New        |                  |
+--------------------------------------------------------------+------------------+
 content area: 100% when the panel is closed, about 65% when open
```

With `trackUnsaved` on and the active view changed, the strip row gains a dot and a split button:

```
| [Table] [Board o] [Calendar] [+] [Save|v]         (F) (S) Search ( ) |
```

- **Unsaved dot**: a small filled dot at the right edge of a tab, in the accent color, on any view whose query, sort or filters differ from the saved copy. It also appears on the active tab, so the marker stays visible while you work. Screen readers hear "unsaved changes" after the name.
- **Save group**: a split button after the "+", shown only while the active view is unsaved. The main button overwrites the view; the chevron opens a menu with Reset and Save as new view. Sentry puts this group in the toolbar beside the sort control; here it sits in the strip row so the new view can be renamed from the strip at once.

- **Tab strip**: left-aligned under the title. One tab per view: layout icon plus name, the active tab a filled pill. A trailing "+" opens the layout picker. Scrolls horizontally when tabs overflow.
- **Toolbar**: right-aligned on the same row as the tabs. Filter, sort and search controls, plus one layout setting (board "Group by", calendar "Date field").
- **Chip row**: appears only when the active view has filters. One chip per rule with an x, then "+ Add filter".
- **Content area**: the active layout. Table and list rows are 32 px and 26 px tall; board columns are about 260 px wide; the calendar is a month grid.
- **Footer bar**: record count on the left, hidden-record count when the layout cannot draw some records, "+ New" on the right.
- **Record panel**: docked on the right, not modal, so the view stays interactive. Header has the close button; body is a property list (label left, value right, gray "Empty" when unset) under a wrapping title.

## Interaction

Key bindings come from `useHotkeys` and do not fire while focus is in an input, textarea or contenteditable, or while a dialog, menu or listbox is open, except Esc. Up, Down, Left, Right and Enter act only when focus is on the page body, the content area, a record or the panel title. All keys are our design; none of the sources show keyboard use inside a view. The saved-views actions add no keys.

| Key | Does | Notes |
|-----|------|-------|
| `1` to `9` | Switch to the nth view tab | Numbered switching follows Fantastical's day/week/month numbering |
| `[` / `]` | Previous / next view | Wraps around |
| Up / Down | Move the active record in the content area | Board: within a column. Calendar: through records in date order |
| Left / Right | Board: move between columns | Table and list: ignored. On a focused tab: previous / next tab |
| Enter | Open the active record in the panel | If the panel is open it swaps to that record |
| Esc | Closes the topmost thing: open popover or dialog, then the panel, then clears the active record | Works while typing in an input (closes the popover or clears search) |
| `f` | Open the filter popover | Linear uses a one-letter filter key |
| `s` | Open the sort popover | |
| `/` | Focus the search field | Only when search is shown (3 or more records) |
| `n` | New record | Gets defaults from the active column or day. Needs `onCreate` |
| `t` | Calendar: jump to the current month | |
| Shift+Left / Shift+Right | Calendar: previous / next month | |

With `trackUnsaved` on, these actions appear while the active view is unsaved (click or Tab and Enter, no keys):

| Action | Does | Notes |
|--------|------|-------|
| Save | Writes the active view's query, sort and filters to the stored view and clears the dot | Layout, group and date field already save at once. If the write fails, a toast shows and the changes stay unsaved |
| Reset (chevron menu) | Drops the unsaved changes and restores the saved query, sort and filters | No confirm; the changes were never saved |
| Save as new view (chevron menu) | Creates a view named "<name> copy" holding what is on screen, switches to it and opens its name field | The original view goes back to its saved state |

Focus rules:

- Clicking a record or pressing Enter opens the panel and moves focus to the panel title (`tabIndex={-1}`, so it is announced). The row or card that opened it is remembered.
- Esc or the close button closes the panel and returns focus to the remembered row or card. If it is gone (deleted, filtered out), focus goes to the content area.
- Opening a record never changes the active tab. Switching tabs keeps the panel open if the record still exists in the new view, and closes it otherwise.
- The tab strip is a `tablist`: one tab stop, Left/Right move between tabs, Enter or Space activates.
- A new view takes focus on its name field so it can be renamed at once. This includes a view made by Save as new view.
- With `trackUnsaved` on, unsaved changes belong to their view: switching tabs keeps them, and the dot stays on the tab you left. They are held in memory, so a reload drops them.
- The Save group is reached by Tab after the "+" and is a plain button plus a menu button; the menu follows the dropdown menu keys (Up, Down, Enter, Esc). When Save, Reset or Save as new view removes the group, focus moves to the active tab.

| State | Shows |
|-------|-------|
| Loading | Tab strip and toolbar rendered but disabled; the content area shows `LoadingState`. No panel. |
| Error | `ErrorState` with a retry button in the content area; the tab strip stays so views remain reachable. A failed write shows a toast and keeps the last good records. |
| Empty (no records) | `EmptyState` in place of any layout, with a "New record" action. Tab strip stays. |
| Filtered to nothing | "No records match", then "N hidden by filters" with a "Clear filters" button. Never a blank area. |
| Records a layout cannot show | Calendar footer "No date (2)", clicking it lists them. Board adds a "No status" column only when it has records. Empty board columns still show with count 0. |
| Very long title | One line with an ellipsis in table, list and calendar cards; two lines in board cards; wraps in the panel. The full title is in the `title` attribute. Metadata truncates before the title does. |
| Many records | Table and list scroll inside the content area with a sticky header. Board columns scroll independently. A calendar day shows 3 cards, then "+N more" opening a popover. No pagination. |
| Many views | Tab strip scrolls horizontally and keeps the active tab in view. Below 640 px it collapses to one select naming the current view. |
| Narrow window | Below 768 px the panel covers the content instead of sharing the row. |
| Unsaved changes | Dot on the tab and the Save group. Below 640 px the select names the view with "(unsaved)" and the Save group stays. Undoing every change by hand removes the marker. |
| Saved query | A view saved with a search string applies it on open and fills the search field. The field stays visible while a query is set, even with fewer than 3 records. |

## Borrow / Leave out

Borrow:

- Tab strip directly under the title, tabs left and toolbar right on one row; active tab as a filled pill, hairline below the strip.
- "+" at the end of the strip with a "Add a new view" tooltip, opening a grid of layout tiles; the new tab appears at once and starts with the full record set.
- Each view keeps its own layout, filter, sort and grouping; changing one does not touch the others.
- Tab menu: rename, duplicate, delete, with a centered confirm dialog before delete.
- Filter chips between the strip and the content; the toolbar icon turns to the accent color while a filter or sort is on; results update live with no Apply button.
- Select-type fields sort by their option order, not alphabetically.
- Search shown only from 3 records up, matching title and text fields as you type.
- Record opens in a docked side panel (the default for table, board and list); property list with gray "Empty".
- Count footer, "+ New" row, "OPEN" pill on row hover, today marked on the calendar, dimmed out-of-month days, shaded weekends, "Today" control.
- A hidden-record count for records a layout cannot draw ("No date (2)").
- Empty states that say what is hidden and how to undo it (Linear).
- With `trackUnsaved`: a small dot beside a saved view's name when its live query, sort and filters differ from the saved definition (Sentry).
- A split Save button: the main part overwrites the current view, the chevron holds Reset (revert to the saved definition) and Save as new view (Sentry).
- A view stores its query, sort and filters together, so a named view is a saved search (Sentry).

Leave out:

- Gallery, timeline, feed, map, chart and form layouts: each needs images, geometry or libraries beyond four layouts.
- Right-docked Layout settings panel: it would compete with the record panel for the same edge.
- Nested AND/OR filter groups: one flat list of AND rules is enough for a local app.
- Multi-key sort and drag-to-reorder sorts: one sort key.
- Drag-and-drop (reorder tabs, move cards between columns, reschedule on the calendar): no drag library in the dependency list. The panel's select changes status or date instead.
- "Save for everyone" and per-person tab display: single user. Sharing and permissions are not built.
- Unsaved-change tracking by default: without `trackUnsaved`, filter and sort edits still save to the view at once, as before.
- Sentry's All Views browse page (search, sort, "Created by Me" and "Created by Others" tables with creator, last viewed and star columns), star toggle and Starred Views nav group: they need accounts and a second screen.
- Sentry's project, environment and time-range selectors, Seer button and in-place title rename: not part of the mechanic.
- Center peek and full-page open modes: one panel mode. Use `list-peek` or `expand-in-place` for those.
- Databases as containers, linked databases, relations and sidebar nesting: they belong to `doc-collections`.
- Property visibility per view, frozen columns, calculate footers: toolbar room; every field shows.
- Notion's brand colors, icons, cover images, comments, Share and star: not part of the mechanic.

## Block API

Files: `gallery/src/patterns/view-switcher/index.ts`, `view-switcher.tsx` (plus internal layout files), `view-draft.ts` (pure unsaved-change logic), `use-views.ts` and `tab-strip.tsx` (stored views, the drafts hook, the dot and Save group), `demo.tsx`. `index.ts` exports `ViewSwitcher`, `ViewSwitcherProps`, `applyView` and the types `Layout`, `FieldType`, `FieldDef`, `FilterOp`, `FilterRule`, `SortRule` and `ViewConfig`.

```ts
CONTRACT: type Layout = "table" | "board" | "list" | "calendar"
CONTRACT: type FieldType = "text" | "select" | "date" | "number"   // date values are "YYYY-MM-DD"
CONTRACT: interface FieldDef<T> { key: Extract<keyof T, string>; label: string; type: FieldType; options?: string[] }   // options required for select; its order is the sort and column order
CONTRACT: type FilterOp = "contains" | "is" | "isNot" | "anyOf" | "onOrBefore" | "onOrAfter" | "gte" | "lte"
CONTRACT: interface FilterRule { field: string; op: FilterOp; value: string | string[] }
CONTRACT: interface SortRule { field: string; dir: "asc" | "desc" }
CONTRACT: interface ViewConfig { id: string; name: string; layout: Layout; filters: FilterRule[]; sort?: SortRule; groupBy?: string; dateField?: string; query?: string }   // query is read and saved only when trackUnsaved is on
CONTRACT: interface ViewSwitcherProps<T extends { id: string; title: string }> {
  items: T[]
  fields: FieldDef<T>[]                               // beyond id and title, which are always shown
  storageKey: string                                  // views persist via useCollection<ViewConfig>(`${storageKey}-views`, defaultViews)
  defaultViews?: ViewConfig[]                         // default: one table view named "All"
  noun?: string                                       // singular, default "record"; used in "New task", empty states
  status?: "loading" | "ready" | "error"              // of items; default "ready"
  error?: Error
  onRetry?: () => void
  onCreate?: (defaults: Partial<T>) => void           // defaults carry the column's group value or the day's date
  onUpdate?: (id: string, patch: Partial<T>) => void  // panel edits; omit to make the panel read-only
  onDelete?: (id: string) => void                     // shows a Delete button with a confirm dialog
  renderPanel?: (item: T, ctx: { close: () => void }) => ReactNode   // replaces the default property list
  activeViewId?: string                               // controlled mode
  onActiveViewChange?: (id: string) => void
  trackUnsaved?: boolean                              // default false; on: query, sort and filters become a per-view draft with the unsaved dot and Save, Save as new view, Reset
  onViewSaved?: (view: ViewConfig, how: "save" | "save-as-new") => void   // after a successful write; only with trackUnsaved
}
CONTRACT: ViewSwitcher<T extends { id: string; title: string }>(props: ViewSwitcherProps<T>): JSX.Element
CONTRACT: applyView<T extends { id: string; title: string }>(items: T[], view: ViewConfig, fields: FieldDef<T>[], query?: string): T[]   // pure filter + search + sort, exported for tests and reuse
```

Behavior the signature does not show:

- `ViewSwitcher` owns tabs, toolbar, chips, layouts and the panel; the host owns the records and passes `items` from its own `useCollection`.
- Uncontrolled, the active view id is kept in `localStorage` under `${storageKey}-active` (read and written inside try/catch) so a reload reopens the same tab, falling back to the first view when the id is gone.
- Search text is shared by all views and is not saved, unless `trackUnsaved` is on: then it is part of the view (`ViewConfig.query`), each view keeps its own, and it is saved with Save.
- `trackUnsaved` leaves `layout`, `groupBy`, `dateField` and `name` writing straight to the view. Only `query`, `sort` and `filters` become a draft, held in component state by view id (`view-draft.ts`). A view is unsaved when its draft differs from the stored copy; `applyView` runs on the draft merged over the stored view.
- Save writes the draft with one `update`; the draft is dropped only when that write succeeds and nothing was edited meanwhile. Save as new view adds a copy of the merged view, drops the original's draft and switches to the copy.
- Duplicate copies the stored view, not the draft. Deleting a view drops its draft.
- Board needs `groupBy` naming a select field and calendar needs `dateField` naming a date field; the layout picker preselects the first matching field, and the toolbar select changes it. If no field of that type exists, the tile is disabled with a tooltip saying why.
- Deleting the only remaining view is not allowed.
- View writes that reject show a `sonner` toast; the tab strip keeps the last good views.

Base pieces used: `useCollection` (views), `EmptyState`, `LoadingState`, `ErrorState`, and `useHotkeys` from `react-hotkeys-hook` for every key above. Neither the block nor the demo renders `AppShell`, `Toaster` or `TooltipProvider`; the app's single `AppShell` provides them.

shadcn components (all from the pre-installed list): `tabs`, `button`, `input`, `badge`, `popover`, `select`, `checkbox`, `dropdown-menu`, `dialog`, `table`, `tooltip`, `kbd`. `registry-item.json` declares the npm `dependencies` `react-hotkeys-hook` and `sonner`; no others.

`demo.tsx` shows a "Workshop planner" with 14 records on `useCollection("view-switcher-demo", seed)` (the views are stored under `view-switcher-demo-views`): fields Title, Stage (Idea, Planned, Confirmed, Done), Host (three names), Date (spread over the current month, built from today's date), Seats (number). Two records have no date, one has no host, and one has a title of about 100 characters. A "Preview state" button group (live, empty, loading, error) in the header forces each state. Seeded views: "All" (table), "Calendar" (by Date), "By stage" (board by Stage), "Upcoming" (list, Stage any of Planned and Confirmed, sorted by Date). It passes `trackUnsaved`, so editing a filter, the sort or the search on any view shows the dot and the Save group, and Save, Save as new view and Reset all work. It wires `onCreate` (new records start at stage Idea), `onUpdate` and `onDelete` to the store, and reports a rejected write as a toast.

## Sources

- [notion study note](../apps/notion.md), the main source. Decisions and their evidence:
  - Tab strip, pill, toolbar on one row, icon plus name: S4-group158, S3-0036, S1-0013.
  - "+" with tooltip and layout-tile popover, immediate new tab: S3-0002, S3-0036, S2-0023, S1-0017 (new view starts with all records).
  - Per-view settings, tab menu actions, overflow behavior: S4 text, S3-0026 (scrolling strip, delete confirm dialog), S2-0013 and S2-0019 ("N more..." exists in Notion; we scroll instead, our design).
  - Narrow-window select: S4 text (described, never shown).
  - Filter chips, colored toolbar icon: S2-0015, S3-0013, S1-0013.
  - Search from 3 records, select sort by option order: S4 text.
  - Table row affordances, count footer, "+ New" row: S2-0009, S1-0023, S1-0013, S1-0022.
  - List density: S2-0011. Calendar month grid, truncation, dimmed days, Today control: S1-0015, S3-0036, S2-0013.
  - Board columns, counts, hidden/empty groups: S2-0017, S2-0019, S3-0034.
  - Hidden-record count: S3-0024.
  - Side panel as default open mode for table, board and list: S4 text. Side peek was never shown in a frame (note "Unseen"), so the panel's look is borrowed from the center peek: S1-0018, S3-0003 (property list, gray "Empty").
  - Loading as a blank panel with no skeleton: S1-0014; we use `LoadingState` instead, our design.
- [linear study note](../apps/linear.md): one-letter filter key and keycaps in tooltips (S1-t0066, S1-t0102), empty state naming hidden counts (S1-t0111), metadata truncating before title (S1-t0072), view-tab strip above toolbar (S2-t0096).
- [obsidian study note](../apps/obsidian.md): filters apply live with no Apply button (S3-0032), several named views per base (S8).
- [craft study note](../apps/craft.md): view tabs as saved filter/group/sort and immediate new tab (S1-0012, S1-0032); its unsaved-changes Save (S4-collections_blog_1) is only matched by the optional `trackUnsaved`, modeled on Sentry.
- [sentry study note](../apps/sentry.md), source of the optional saved-views revision:
  - Dot on a modified saved view, signalling the live state differs from the saved definition: S8-unsaved-changes.png (shown at the right edge of the row in the starred-views list; we put it on the tab).
  - Split Save button, main part overwrites the view, chevron menu with Reset and Save as new view: S8-save-button.png.
  - A view as a saved query and filters, with its definition scannable as chips: S8-all-views.png. The browse page itself is left out.
- [fantastical study note](../apps/fantastical.md): numbered view shortcuts (S4-calendar-views), sidebar unchanged across views (S2-0015).
- Our design (no source shows it): the Save group in the strip row instead of the toolbar, the "<name> copy" naming and immediate rename after Save as new view, drafts kept per view in memory, no keys for the saved-views actions, the `query` field on `ViewConfig`, the `trackUnsaved` switch and `onViewSaved`, every key in the keys table, the focus rules, the filter/sort popover keys, the flat filter operators, "+N more" in calendar cells, the 640 px and 768 px breakpoints, the `onCreate` defaults, `applyView`, and persisting the active view in `localStorage`.
