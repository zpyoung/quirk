# workspace-panes

Tabs and split panes over records that live as files the user can see in a sidebar list, where a structured view and the raw file are two views of the same record; studied mainly in Obsidian.

## When to use

Use it when the user keeps many small records, opens several at once, and sometimes wants to see the underlying text:

- A snippet or prompt library: one record per snippet, form view plus raw text, a second snippet open beside the first for comparison.
- A recipe or meal-plan notebook: structured fields (ingredients, steps) next to the raw Markdown it is stored as.
- A config or fixture editor: each JSON or YAML file is a record, with a form view and the raw file side by side.
- A research-notes scratchpad where two notes stay open while a third is written.

Do not use it when:

- Records are opened one at a time from a list: use `list-peek` (or `expand-in-place` to open a row inline).
- The data is one table of rows edited as a grid: use `staged-table-edit`.
- The same records need several layouts (table, cards, board): use `view-switcher`.
- The user mostly browses and files documents into folders and does not keep several open: use `doc-collections`.
- A single selected record needs a side panel of fields: use `inspector`.

## Anatomy

```
+----+-------------+-----------------------------+--------------------------+
|    | Sidebar     | Group A                     | Group B                  |
|    |             | [Tab 1][Tab 2 x][+]      v  | [Tab 3 x][+]          v  |
|    | [filter   ] |-----------------------------|--------------------------|
|    | Welcome     | <  >   Record title   S|R ⋮ | <  >  Record title S|R ⋮ |
|    | Cookie ...  |-----------------------------|--------------------------|
|    | Notes [JSON]|                             |                          |
|    | ...         |     content column          |      content column      |
|    |             |     (max ~560 px)           |                          |
|    | 5 items     |                             |                          |
+----+-------------+-----------------------------+--------------------------+
 3%       ~20%               ~44%                         ~33%
```

The ribbon column is not built (see Leave out); the 3% is shown only to match the source. Our block starts at the sidebar.

- **Sidebar**: filter field, one plain-text row per record (no icons), a small right-aligned badge for the file type, a count footer. The open record's row has a light fill. Collapsible.
- **Tab groups**: one or two groups side by side. Each has its own tab strip (about 38 px tall) with a "+" button and a chevron that lists every tab.
- **Tabs**: about 155 px wide, title truncated with an ellipsis. Inactive titles are muted and only the active tab shows a close ×.
- **Pane header**: back and forward buttons, centered record title, a Structured | Raw toggle (`S|R` above), and a "⋮" menu.
- **Pane body**: either the structured view or the raw file, in a content column of about 560 px centered in the pane.
- **Empty pane**: four plain text links with their shortcuts (see Interaction).
- **Status bar** (optional, bottom right of the window): word and character count of the active record.

## Interaction

Keys. Obsidian's ⌘T, ⌘W and ⌃Tab cannot be intercepted by a web page (the browser owns them), so our block uses Alt chords instead. All bindings go through `useHotkeys` and are ignored while focus is in an input, textarea or contenteditable, except where Notes says otherwise.

| Key | Does | Notes |
|---|---|---|
| Alt+T | New tab in the active group, showing the empty pane | Obsidian ⌘T (S2-0049, S5); key is our design |
| Alt+W | Close the active tab | Obsidian ⌘W (S2-0050) |
| Alt+Shift+T | Reopen the last closed tab | Obsidian ⌘⇧T (S5); keeps a stack of the last 10 (our design) |
| Alt+] / Alt+[ | Next / previous tab in the group | Obsidian ⌃Tab / ⌃⇧Tab (S5) |
| Alt+1 to Alt+8, Alt+9 | Jump to tab 1 to 8, and to the last tab | Obsidian ⌘1 to ⌘9 (S5) |
| Alt+\ | Split the active tab into a new group on the right | Obsidian uses ⌘⌥-click or a right-click menu (S5); no key there, so ours |
| Alt+E | Toggle the active tab between Structured and Raw | Our design |
| Alt+B | Show or hide the sidebar | Our design; Granola and Figma also toggle a sidebar by key |
| Alt+O | Focus the sidebar filter ("Go to item") | Our design |
| Alt+N | Create a new record and open it in the active tab | Obsidian ⌘N (S2-0016 link label); only when `onCreate` is given |
| (tab and view chords above) | Alt+T, Alt+W, Alt+E, Alt+[ and Alt+] also fire while focus is in the raw textarea | Alt chords insert no text there, so these opt in to form tags; verify on macOS, where Option+letter types a character |
| Click a sidebar row | Opens the record in the active tab, replacing what it showed | Obsidian: a link click navigates the active tab (S5); same for rows is our design |
| Mod-click a row | Opens in a new tab | S5 (⌘-click) |
| Mod+Alt-click a row | Opens in a new group (split) | S5 (⌘⌥-click) |
| Right-click a tab | Menu: Split right, Close, Close others | S5 text lists Split right, Split down, Pin; our menu drops Down and Pin |

Focus rules (S2-0049 and S2-0050 do not show where focus lands after close, so these are our design except the first):

- A new tab receives focus (S2-0049), on its first empty-pane link.
- Opening a record from the sidebar moves focus to the pane body: the raw textarea in Raw view, otherwise the pane container.
- Closing a tab focuses its right neighbor, or the left one if it was last. Closing the last tab in a group removes that group when another exists and focuses the other group's active tab; otherwise the group shows the empty pane.
- Esc in the raw textarea blurs it to the pane container so the hotkeys work again. Esc closes any open menu and returns focus to its trigger. Esc never closes a tab.
- Hovering a sidebar row shows an outlined box and, after a short delay, a tooltip with created and modified times (S1-0018). Hover is separate from the filled row of the open record.

| State | What shows |
|---|---|
| Empty, no records | Sidebar: `EmptyState` "No items yet" with a New item action. Pane area: the empty pane with the "Create new item" link only |
| Empty, records but no tab open | Empty pane: "Create new item (Alt+N)", "Go to item (Alt+O)", "See recent items", "Close" as plain text links (S2-0016); no illustration |
| Loading | Sidebar: five `Skeleton` rows. Pane area: `LoadingState`. Tab strip hidden. Layout restore waits for items |
| Error | `ErrorState` with Retry in place of the sidebar list and the pane. A layout restore failure alone falls back to one group with one empty tab, no error |
| Raw text does not parse | Inline message under the textarea naming the problem; text stays as typed, the record is not changed, Structured view shows the last good record (our design) |
| Record deleted while a tab shows it | Tab title becomes "Deleted" in muted text; pane shows `EmptyState` with Close tab (our design; S1 gives no deleted-file case) |
| Very long title | Tab and sidebar row truncate with an ellipsis (S1-0016); full title in a `title` tooltip. Pane header title truncates, never wraps |
| Many tabs | Strip scrolls horizontally with the active tab kept in view; the chevron lists all tabs (S1-0014) |
| Many records | Sidebar scrolls inside `ScrollArea`; the filter narrows the list and the footer shows "n of m" |
| Long content | The pane body scrolls; the content column stays about 560 px (S1-0019); Raw view uses the full pane width with monospace text |
| Same record in two tabs | Allowed, with no de-duplication (S1-0017); this is how Structured and Raw sit side by side |
| Narrow window | Below about 720 px the second group is not offered; Alt+\ opens a tab instead (our design) |

## Borrow / Leave out

Borrow:

- Sidebar of plain rows listing real records, with a type badge and a filled row for the open one (S1-0019, S1-0016).
- A tab strip per group, with truncated titles, close × only on the active tab, "+" and a tab-list chevron (S1-0014, S1-0016).
- Tabs are views, not documents: the same record can be open twice (S1-0017).
- Splitting into side-by-side groups from a modifier-click or a tab menu, with draggable group edges (S5).
- The empty pane with four text links that carry their shortcuts (S2-0016).
- The shortcut set for new, close, switch and reopen (S5).
- One record, two views: the file listing is the data (S1-0020), and a record's raw form and its rendered form show the same text (S1-0019, S3-0012).
- The open layout (tabs, groups, active record) persists across reloads (S5, S6).
- A bottom-right status line with counts (S1-0019).

Leave out:

- Ribbon icon column: it holds Obsidian plugin shortcuts we do not have.
- Graph view, backlinks, outline and the right sidebar: they belong to `inspector`, not to this pattern.
- Live-preview editing, where the cursor line reveals its Markdown marker (S1-0019): that is `assisted-notes`; here Structured and Raw are separate views.
- Drag-to-move into folders and tab drag-and-drop (S2-0041, S5): the drop zones were never shown, and files are flat in a mini app. Reorder tabs with the tab menu only if needed.
- Pinned tabs, tab stacks, linked views, saved Workspaces layouts, and new-window clicks (S5): rarely needed with one or two groups.
- Vault launcher, sync icon, and plugin settings (S1-0005, S2-0065): there is one local store, no vaults.
- Bases-style filters and cards: that is `view-switcher`.

## Block API

Folder `gallery/src/patterns/workspace-panes/`. `index.ts` exports the names below. The block uses `useCollection` from `src/lib/mini/store.ts` only for its own layout (collection `workspace-panes-layout`, one record with id `"layout"`); the records come in through props so the host app owns its data. It uses `EmptyState`, `LoadingState` and `ErrorState` from `states.tsx`, `AppShell` only in `demo.tsx`, and `useHotkeys` from `react-hotkeys-hook`.

shadcn components: resizable, scroll-area, button, input, textarea, badge, separator, tooltip, kbd, skeleton, dropdown-menu, context-menu, toggle-group.

```ts
// CONTRACT: the minimum shape of a record
type WorkspaceItem = { id: string; title: string };

// CONTRACT: how a record is shown
type PaneMode = "structured" | "raw";

// CONTRACT: persisted layout; stored through useCollection
type WorkspaceTab = { tabId: string; itemId: string | null; mode: PaneMode }; // itemId null = empty pane
type TabGroup = { groupId: string; tabs: WorkspaceTab[]; activeTabId: string };
type WorkspaceLayout = { id: "layout"; groups: TabGroup[]; activeGroupId: string; sidebarOpen: boolean; recent: string[] }; // groups.length is 1 or 2

// CONTRACT: WorkspacePanes<T extends WorkspaceItem>(props: {
//   items: T[];
//   status: "loading" | "ready" | "error";
//   error?: Error;
//   onRetry?: () => void;
//   renderStructured: (item: T, api: { update: (patch: Partial<T>) => Promise<void> }) => ReactNode;
//   toRaw: (item: T) => string;                          // the file text for a record
//   parseRaw: (raw: string, item: T) => T;               // throws Error with a readable message when invalid
//   onChange: (next: T) => Promise<void>;                // called with a parsed, valid record
//   onCreate?: () => Promise<string | void>;             // returns the new item id to open; hides New item links if absent
//   badge?: (item: T) => string | undefined;             // sidebar type badge, e.g. "JSON"
//   tooltip?: (item: T) => string | undefined;           // sidebar hover text, e.g. created and modified times
//   storeName?: string;                                  // layout collection name, default "workspace-panes-layout"
//   maxContentWidth?: number;                            // structured column width in px, default 560
// }): JSX.Element

// CONTRACT: pieces, exported for apps that rearrange the layout
// ItemList<T extends WorkspaceItem>(props: { items: T[]; activeId?: string; onOpen: (id: string, how: "here" | "tab" | "split") => void; badge?; tooltip? })
// TabStrip(props: { group: TabGroup; titleOf: (itemId: string | null) => string; onSelect; onClose; onNew })
// RawEditor(props: { value: string; onCommit: (raw: string) => void; error?: string })
// useWorkspaceLayout(storeName?: string): { layout: WorkspaceLayout; status; openItem(id, how); closeTab(tabId); reopenTab(); newTab(); split(); setMode(tabId, mode); toggleSidebar() }
```

Behavior the block guarantees:

- `parseRaw` runs when the raw textarea loses focus or after 600 ms idle (our design). On success `onChange` is called and Structured view updates; on a throw the message shows inline and nothing is written.
- Structured edits call `update`, which calls `onChange`; the Raw view of any other open tab on the same record re-renders from `toRaw`.
- A tab whose `itemId` no longer exists in `items` shows the deleted state.
- A rejected `onChange` or `update` keeps the last good record and surfaces the error through `sonner` in the host app; the block only rethrows.

`demo.tsx` default-exports `Demo`: a recipe notebook with about 12 recipes (title, servings, ingredient list, steps). Structured view is a small form plus lists; raw view is the same recipe as a Markdown file with a front-matter block. `toRaw` and `parseRaw` convert between them, and one recipe has deliberately long title text. The demo opens with two groups, the second showing a recipe in Raw view, and uses `useCollection("recipes", seed)`. It also shows the empty, loading and error states through a small control row.

## Sources

- [obsidian study note](../apps/obsidian.md): main source. Observation IDs and frames below.
- Anatomy proportions (sidebar, two groups, per-group tab strip and header row): S1-0014 (`S1-0014.png`), S6 text for the component list. The 3% ribbon figure is S1-0014 only.
- Sidebar rows, filled open row, badges, status bar, 560 px column: S1-0019, S1-0016, S1-0020.
- Hover outline and created and modified tooltip: S1-0018.
- Tabs: width, truncation, close × on the active tab only: S1-0016. Same record in two tabs: S1-0017. New tab focus: S2-0049 (the close case, S2-0050, shows only the moment of the keypress). Chevron tab list: S1-0014.
- Empty pane with four text links: S2-0016.
- Split by modifier-click or tab menu, shortcut list, layout persistence: S5, text-sourced, with `S5-tabs.png`. Component list: S6, text-sourced.
- Records as visible files, structured and raw as two surfaces of one record: S1-0020, S1-0019, S3-0012, S3-0027.
- Other apps: [fantastical](../apps/fantastical.md) (`S2-0002.png`, sidebar plus content plus optional right column), [figma](../apps/figma.md) (`S3-0012.png`, `S7`, fixed-width collapsible panels), [granola](../apps/granola.md) (`S1-0020.png`, sidebar toggle by key), [craft](../apps/craft.md) (`S2-0008.png`, tab strip of open pages).
- Our design (no source): Alt chord bindings and why, Alt+E, Alt+B, Alt+O, click-replaces-active-tab, close-focus rules, Esc behavior, reopen stack, parse timing and error display, deleted-record state, narrow-window rule, loading and error states, the layout record shape.
