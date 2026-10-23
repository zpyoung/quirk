# inspector

A navigation tree on the left, a canvas in the middle, and a properties panel on the right whose fields change with the current selection. Studied mainly in Figma's UI3, with side evidence from TablePlus, Linear, Notion and Fantastical.

## When to use

Use it when the user edits the attributes of many typed things and needs to see them in context:

- A slide or poster layout editor: layers in the tree, the artboard in the middle, position, size and text style on the right.
- A form or survey builder: question tree on the left, preview in the middle, per-question settings on the right.
- A game-level or floor-plan tool: objects by room or layer, a map canvas, and per-object properties.
- A design-token or theme editor: token groups on the left, a live sample in the middle, values on the right.

Do not use it when:

- The items have one fixed set of fields and the list is the main thing: use `list-peek`, where the detail opens beside a list.
- Records are rows in a grid edited cell by cell with pending changes: use `staged-table-edit`.
- The user mostly writes prose and the properties are a few tags: use `doc-collections` or `assisted-notes`.
- You need a free arrangement of panes the user can split and tab: use `workspace-panes`. This pattern has fixed docks.

## Anatomy

```
┌───────────────────────────────────────────────────────────────────┐
│ toolbar: dock toggles, "Hide docks" hint                          │
├──────────────┬────────────────────────────────────┬───────────────┤
│ tree  ~18%   │ canvas  ~62%                       │ panel  ~20%   │
│ ▾ Poster     │                                    │ 2 selected    │
│   ▸ Header   │      ┌──────┐   ┌───┐              │ Position      │
│   ● Title    │      │      │   └───┘              │  X [Mixed]    │
│   ■ Photo    │      └──────┘   ← hover outline    │  Y [Mixed]    │
│ ▾ Footer     │                                    │ Layout        │
│   ...        │                                    │  W [120 ]     │
│              │                                    │ + Shadow      │
└──────────────┴────────────────────────────────────┴───────────────┘
```

- **Tree** (left): rows with a type marker, indented children, disclosure chevrons, a scroll area. Fixed width with a drag edge, collapsible.
- **Canvas** (middle): takes the leftover width. Shows the items, a hover outline, and a selection outline with a size label. It is a render slot, so each app draws its own.
- **Panel** (right): a pinned header (type name, or "N selected"), then a scrolling body of titled sections. Fixed width with a drag edge, collapsible.
- **Section**: bold title, grey-filled inputs with the label inside. An empty optional section is one "+ Title" row that expands in place.
- **Page panel**: what the right dock shows with nothing selected.

## Interaction

Tree and canvas keys fire only while focus is inside the tree or canvas, never in an input, textarea or contenteditable. Esc and Enter inside the panel's own fields are plain key handlers on those fields.

| Key | Does | Notes |
|-----|------|-------|
| ↑ / ↓ | Move selection to the previous or next visible tree row | Our design. Tree has focus. |
| ← / → | Collapse or expand the focused row | Our design. |
| Click row or canvas item | Select it | Click commits, hover only previews (S3-0012). |
| ⇧ click / ⌘ or Ctrl click | Range select in the tree / toggle one item | Our design. Multi-select result is from S3-0112. |
| ⌘ or Ctrl + A | Select every item | Our design. |
| Enter | Move focus to the first field of the panel | Our design. Tree has focus (not the canvas). |
| F2, double-click | Rename the row inline | Result seen (S2-0112), trigger is our design. |
| Delete / Backspace | Remove the selected items | Our design (TablePlus lists Delete). The items leave the tree and canvas at once and an undo toast shows for 5 s; `onRemove` is called when it expires, or earlier if the block unmounts. Undo cancels the call and reselects the items. Focus moves to the nearest remaining tree row. |
| Esc | Clear the selection | Tree or canvas has focus. TablePlus Esc deselects (text-sourced). |
| ⌘ or Ctrl click on the canvas | Toggle one item | The demo canvas calls `select(id, "toggle")`; the block does not draw the canvas. |
| ⇧ + \ | Hide both docks. The right dock reappears while something is selected | Text-sourced from Figma S7. |
| Enter (in field) | Commit the value and keep focus | Our design. |
| Esc (in field) | Revert the uncommitted value, return focus to the tree | Our design. |
| ↑ / ↓ (in number field) | Nudge by 1, ⇧ by 10 | Our design. |

Focus rules:

- Selecting by click leaves focus on the tree row or canvas item, so arrow keys keep working. Typing in the panel never moves the selection.
- Enter on the tree moves focus into the panel. Esc in a field reverts and moves focus back to the row that was selected.
- A field commits on Enter or blur. Tab moves to the next field in panel order.
- A detail popover opens beside the panel (S3-0108). Esc closes it and returns focus to its field. Edits inside it apply live. Click-away behavior was not seen, so it is our design.

| State | Shows |
|-------|-------|
| Nothing selected | The page panel: app-level fields and the optional rows (S3-0014, S2-0101). Header and tabs stay in place. |
| One item of type A or B | That type's sections only. The panel shrinks to what the type can do (S3-0104, S3-0105). |
| Several items | Header "N selected". A field shared by all with the same value shows it. Differing values show a "Mixed" placeholder (S3-0112). Typing in a Mixed field sets it on all. Our design: only fields common to all selected types are listed. |
| Selected item deleted | Selection drops the id. If none are left, the page panel shows. |
| Empty collection | Tree shows `EmptyState` "No items". Canvas shows `emptyView` (the app's add action) or a default `EmptyState`. Panel shows the page panel. Figma's own empty tree has no message (S2-0101), so the messages are our design. |
| Loading | Only `LoadingState` filling the block, no toolbar or docks drawn until ready (S3-0050-loading). |
| Error | `ErrorState` with retry, filling the block. A failed write, rename or removal shows a toast and keeps the last good values. |
| Long title | Truncate with an ellipsis in tree rows and the panel header, full title in a tooltip (S1-1016). Rename shows the full text. |
| Many items | Tree scrolls in a `ScrollArea`. The panel body scrolls under its pinned header (S3-0115). |
| Mixed with nothing set | A field unset on every item shows its placeholder, not "Mixed". Our design. |

## Borrow / Leave out

Borrow:

- One panel skeleton: pinned header, then sections in a fixed order, with type blocks swapped in per selection (S2-0111, S2-0105, S2-0121).
- Page panel when nothing is selected (S3-0014).
- "N selected" header with "Mixed" values and a hint on how to replace them (S3-0112).
- Empty optional sections collapsed to one "+" row (S2-0105, S3-0110).
- Hover outline on the canvas that previews without committing (S3-0012).
- Detail editors as popovers beside the panel, not inline (S3-0108).
- Fixed-width docks with the canvas taking the rest, about 17-20% each (S4-annotated-layout, S3-0012).
- Selection color shared across tree, canvas and panel (Fantastical S2-0028).
- Empty values read as muted verbs such as "Add label", with no row borders (Linear S2-t0114).
- Property order kept stable, X/Y before W/H, to protect muscle memory (S6 text).

Leave out:

- Design/Prototype/Dev tabs and Comment/Properties tabs: one panel is enough, `view-switcher` covers tabs.
- Presence avatars, Share, plans banner, plugin rows: no accounts or collaboration locally.
- Components, instances, variants, "Create component": too app-specific for a generic block.
- Icon rail with Agents, Assets, Variables: `workspace-panes` covers multi-dock navigation.
- Tool-specific panels (frame presets, vector editing) and the floating toolbar: they belong to the app's canvas.
- Property labels toggle: our inputs always carry a label.
- View-only read-only mode: no permissions locally.

## Block API

`index.ts` exports `Inspector`, `ItemTree`, `PropertiesPanel`, `sharedValue` and the types `InspectorItem`, `FieldDef`, `SectionDef`, `InspectorSchema` and `InspectorProps`. The block never imports another pattern.

```ts
CONTRACT: type InspectorItem = { id: string; title: string; type: string; parentId?: string | null }
CONTRACT: type FieldDef<T> = {
  key: keyof T & string; label: string;
  kind: "text" | "number" | "select" | "toggle" | "popover";
  options?: { value: string; label: string }[];          // select
  unit?: string; min?: number; max?: number; step?: number; // number
  renderEditor?: (value: unknown, set: (v: unknown) => void) => ReactNode; // popover
}
CONTRACT: type SectionDef<T> = { id: string; title: string; fields: FieldDef<T>[]; optional?: boolean }
CONTRACT: type InspectorSchema<T extends InspectorItem> = Record<T["type"], SectionDef<T>[]>
CONTRACT: type InspectorProps<T extends InspectorItem> = {
  items: T[]; schema: InspectorSchema<T>;
  status?: "loading" | "ready" | "error"; error?: Error; onRetry?: () => void;
  selectedIds?: string[]; onSelectionChange?: (ids: string[]) => void;  // uncontrolled when omitted
  onUpdate: (ids: string[], patch: Partial<T>) => void | Promise<void>;
  onRemove?: (ids: string[]) => void | Promise<void>;
  onRename?: (id: string, title: string) => void | Promise<void>;
  renderCanvas: (ctx: { items: T[]; selectedIds: string[]; hoverId: string | null;
                        select: (id: string, mode: "replace" | "toggle") => void;
                        hover: (id: string | null) => void }) => ReactNode;
  pageView?: ReactNode;                  // right dock when nothing is selected
  emptyView?: ReactNode;                 // canvas content when items is empty
}
CONTRACT: Inspector<T extends InspectorItem>(props: InspectorProps<T>): JSX.Element
CONTRACT: ItemTree<T extends InspectorItem>(props: { items: T[]; selectedIds: string[]; onSelect: (id: string, mode: "replace" | "range" | "toggle") => void; onRename?: (id: string, title: string) => void }): JSX.Element
CONTRACT: PropertiesPanel<T extends InspectorItem>(props: { selected: T[]; schema: InspectorSchema<T>; onChange: (patch: Partial<T>) => void; pageView?: ReactNode }): JSX.Element
CONTRACT: sharedValue<T>(items: T[], key: keyof T): { mixed: boolean; value: T[keyof T] | undefined }
```

- `Inspector` owns selection, hover, dock visibility and the hotkeys. A new section is added through the schema, not by editing the panel.
- Edits, renames and removals show on screen before the app's write lands, and fall back to the app's items if the write rejects.
- Writes go through `onUpdate`. The app passes `useCollection(name, seed)` methods; when `update` rejects, `Inspector` shows a `sonner` toast and keeps the last good values.
- `status` and `error` map straight from `useCollection`. `Inspector` renders `LoadingState`, `ErrorState` and `EmptyState` from the base. It renders no `AppShell`, `Toaster` or `TooltipProvider`: the app's single `AppShell` provides them.
- Hotkeys use `useHotkeys` from `react-hotkeys-hook` with form-tag filtering on, except the in-field Enter and Esc, which are plain `onKeyDown` handlers.
- shadcn components used: `resizable`, `scroll-area`, `input`, `select`, `checkbox`, `popover`, `collapsible`, `tooltip`, `button`, `kbd`. `registry-item.json` declares the npm `dependencies` `lucide-react`, `react-hotkeys-hook` and `sonner`.

`demo.tsx` default-exports `Demo`: a poster layout editor with 14 items stored through `useCollection("inspector-demo", seed)`. It renders no `AppShell`; the app provides it. Types are `frame`, `text` and `shape`, with `parentId` nesting two levels. Fields are x, y, w, h, fill, text and a font-size, plus an optional Shadow section. The canvas draws each item as an absolutely positioned box. One long title is in the seed to show truncation. The demo draws the canvas itself (`renderCanvas`), supplies a `pageView` with item counts and an `emptyView` with an "Add frame" button. A "Preview state" button group (live, empty, loading, error) forces each state, and "Reset sample data" restores the seed.

## Sources

- [figma study note](../apps/figma.md): S1 (components video), S2 (dark UI3 walkthrough), S3 (UI3 for beginners), S4 and S7 (help and blog text), S6 (design rationale).
- Panel skeleton and per-type blocks: S2-0111, S2-0105, S2-0121, S3-0104, S3-0105. Type-shrunk panel is seen.
- Page panel and empty file: S3-0014, S2-0101.
- Multi-select, Mixed, hint text, combined size pill: S3-0112.
- Collapsed "+" optional sections: S2-0105, S3-0110.
- Hover preview versus click commit: S3-0012.
- Popover editors: S3-0108, S3-0110. Click-away and Esc behavior are our design (listed as Unseen in the study note).
- Pinned header and scrolling body: S3-0115. Truncated header: S1-1016. Loading: S3-0050-loading.
- Dock proportions: S4-annotated-layout, S3-0012, S2-0105. Minimize UI shortcut: S7 and S6 text, text-sourced.
- Rename result: S2-0112. Trigger, F2, Enter-to-panel, arrow and tree keys, range select: our design.
- Property order: S6 text. Selection color: Fantastical S2-0028 in the [fantastical note](../apps/fantastical.md).
- Deselect and Delete keys: TablePlus shortcut text in the [tableplus note](../apps/tableplus.md), text-sourced. Empty "No row selected" panel: TablePlus S2-0074.
- Right-dock widths and muted-verb empty values: [linear note](../apps/linear.md) S1-t0150, S2-t0114.
