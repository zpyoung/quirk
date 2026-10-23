# Raycast study note

Captured 2026-10-22 from public videos and public docs pages only (no login, no account).

## Sources

| ID | URL | Kind | Date | Shows |
|----|-----|------|------|-------|
| S1 | https://www.youtube.com/watch?v=G7_7F_FBqQE | official | 2026-09-04 | "102 Things You Can Do With Raycast 2.0": dark macOS and Windows builds, root search, action panel, list with preview, forms, store detail |
| S2 | https://www.youtube.com/watch?v=C0oOsjmXduY | official | 2026-10-09 | "Shortcuts in Raycast": action panel on apps, files and commands, with shortcut keycaps, filter-as-you-type, and the Configure Command sub-menu; Mac and Windows side by side |
| S3 | https://www.youtube.com/watch?v=kHxgxgNHQR4 | third-party | 2025-05-30 | Stephen Sergio review, older light-theme macOS build: list with preview pane, compact mode, store search, menu-item search, fallback results |
| S4 | https://manual.raycast.com/action-panel | official | read 2026-10-22 | Action Panel manual page (text plus screenshot `S4-action-panel.png`) |
| S5 | https://manual.raycast.com/search-bar | official | read 2026-10-22 | Search Bar manual page: ranking, keys, compact mode (text plus `S5-search-bar.png`) |
| S6 | https://www.raycast.com/blog/a-fresh-look-and-feel | official | 2022 (page date) | Redesign post: bigger search bar, bottom action bar, compact mode (full-page capture `S6-fresh-look.png`, too tall to read; the text is the source) |
| S7 | https://developers.raycast.com/api-reference/user-interface/action-panel | official | read 2026-10-22 | Extension API for ActionPanel: sections, submenus, default primary and secondary keys (`S7-api-action-panel.png`) |

Frame filenames below are relative to `references/media/raycast/`. The videos were scene-sampled, so frames carry no timestamps.

## Observations

- S1 `references/media/raycast/S1-0001.png`: the root window is a single rounded panel about 1.6:1 (roughly 875 x 555 px in a 1280 px frame). From the top: a search row (about 70 px) with a "Quick AI" hint and a Tab/⇥ key at the right, then a list under small gray section headings ("Suggestions", "Commands"), then a floating footer pill at the bottom right. → feeds: action-palette
- S1 `references/media/raycast/S1-0001.png`: a row has a 24 px icon, a white title, a dimmer subtitle (the extension name), and a right-aligned muted type label ("Command", "Application"). Rows sit about 44 px apart, so about 8 fit before the footer. The selected row is a slightly lighter rounded rectangle inset from the window edge, with no border or accent color. → feeds: action-palette, list-peek
- S1 `references/media/raycast/S1-0001.png`: the footer pill reads "Open Command ↵ | Actions ⌘K". It names what ↵ will do for the selected row, and the last list row ("Create Snippet") fades out underneath the pill instead of ending above a solid bar. → feeds: action-palette
- S1 `references/media/raycast/S1-0004.png`: the Windows build shows the same layout, but the footer is a full-width bar with a top rule, and the hint is "Actions Ctrl K" with "Tab" spelled out. Only the modifier glyphs change per platform. → feeds: action-palette
- S2 `references/media/raycast/S2-0006.png`: Mac (left, "⌘ K") and Windows (right, "Ctrl K") captures of the same root screen, typing "clipboard h". The list shows a Command match first, then a Files section, then a "Use "clipboard h" with..." fallback section. → feeds: action-palette
- S1 `references/media/raycast/S1-0051.png`: pressing ⌘K opens the action panel as a floating card anchored to the bottom-right, just above the footer. It is about 390 px wide (about 45% of the window) and covers the right half of the lower list. The list underneath stays visible but is not dimmed. → feeds: action-palette
- S1 `references/media/raycast/S1-0051.png`: panel anatomy top to bottom: a title with the selected item's name ("GarageBand"), the first action highlighted ("Open Application" with a ↵ keycap), further actions with their chords, a thin separator, then "Add to Favorites ⇧⌘F", then a "Search for actions..." input at the bottom edge. The filter field is at the bottom, not the top. The manual (S4) says top. → feeds: action-palette
- S1 `references/media/raycast/S1-0048.png`: close-up of the same panel on "Xcode". Action rows are about 42 px apart, with a 20 px outline icon, a title, and the shortcut right-aligned. Each key of a chord gets its own rounded keycap (⇧ ⌘ I, ⌥ ⌘ I). The first row's ↵ keycap is a single glyph. → feeds: action-palette
- S2 `references/media/raycast/S2-0019.png`: file panel for "Contrat de bail.pdf": Open ↵, Show in Finder ⌘↵, Show Details in File Search ⌥↵, Quick Look ⌘Y, Open With… ⌘O, Share… (no shortcut). The second action holds ⌘↵ (the secondary-action slot) and the third holds ⌥↵. Rows without a shortcut simply have an empty right side. The highlight sits on "Quick Look", not the first row. → feeds: action-palette
- S2 `references/media/raycast/S2-0015.png`: panel for an app ("Notion Calendar") with "co" typed into the bottom field. The rows left are Copy Path ⌥⌘C, Copy Name ⌃⌘C, Copy Bundle Identifier ⇧⌘C, Configure Command… ⇧⌘, , Configure Extension ⌥⌘, , Show Package Contents ⌥⌘I. "Open Application" is gone, so filtering is a substring match ("Package Contents" contains "co"). The list is cut off at the panel's bottom edge, so it scrolls. → feeds: action-palette
- S2 `references/media/raycast/S2-0021.png`: choosing "Configure Command…" swaps the panel's contents for a sub-menu in the same card. The title becomes "Configure Command", and the rows are Open Command Settings, a separator, Set Hotkey…, and Set Alias…. The input placeholder shortens to "Search...". Rows ending in "…" are the ones that lead to another view. → feeds: action-palette
- S4 (text; `references/media/raycast/S4-action-panel.png`): ⌘K / Ctrl K opens the panel, ↵ runs the first (primary) action without opening it, and Esc closes the panel or backs out of a sub-menu. While searching, matches show as one flat list regardless of sections. Destructive actions render red. The page lists "⌘F" for Add to Favorites in one place and "⇧⌘F" in another, and the frames (S1-0051) show ⇧⌘F. → feeds: action-palette
- S7 (text; `references/media/raycast/S7-api-action-panel.png`): the first action in a panel is primary and the second is secondary. In List, Grid and Detail they get ↵ and ⌘↵. In a Form they get ⌘↵ and ⌘⇧↵. Sections carry an optional title, and a Submenu replaces the current panel with its children. → feeds: action-palette
- S5 (text; `references/media/raycast/S5-search-bar.png`): list keys are ↑/↓ to move, ⌘↑/⌘↓ to jump a section, ⌥↑/⌥↓ to jump a page, ↵ for primary, ⌘↵ for secondary. Esc clears the query first and closes the window only when the query is already empty. Backspace on an empty query goes back one level. → feeds: action-palette, list-peek
- S5 (text): ranking is exact alias, then alias prefix, then fuzzy title score, then subtitle and keyword matches, then frecency. "Reset Ranking" is an action in the panel. Favorites show above everything when the query is empty. → feeds: action-palette
- S3 `references/media/raycast/S3-0004.png`: Clipboard History is a two-pane view. A back arrow sits at the left of the search field, a type dropdown ("All Types") at the right, and the list is grouped under date headings ("Today"). The list takes about 38% of the width and the preview about 62%. Under the preview is an "Information" block with label/value rows (Source, Content type). → feeds: list-peek, inspector
- S3 `references/media/raycast/S3-0005.png`: typing "re" filters the list live and the preview switches to monospaced text for a shell script. The Information block stays in place under it. The preview adapts to the item type (image for a video or image, mono text for text). → feeds: list-peek, inspector
- S1 `references/media/raycast/S1-0089.png`: the same view in the 2026 dark build, with "Today / This Week / This Year" groups and thumbnails on image rows. The footer reads "Paste to CleanShot X ↵ | Actions ⌘K", so the primary label names the destination app, and the left footer slot shows the command name "Clipboard History". → feeds: list-peek, action-palette
- S3 `references/media/raycast/S3-0001.png`: a detail view (Now Playing) reverses the split: about 65% content on the left and about 35% label/value metadata on the right. Footer: command name at the left, "Play ↵ | Actions ⌘K" at the right. → feeds: inspector, action-palette
- S1 `references/media/raycast/S1-0072.png`: an extension detail page has only a back chevron at the top left, a large title, a screenshot carousel, a two-column "Description / README / Last update" block, and the footer "Install Extension ↵ | Actions ⌘K". There is no search field on pages that have nothing to filter. → feeds: inspector
- S1 `references/media/raycast/S1-0082.png`: the primary action can use a custom key. The footer shows "Restart Practice ⌘R | Actions ⌘K" instead of ↵. The ⌘K Actions chip stays in the same slot. → feeds: action-palette
- S1 `references/media/raycast/S1-0075.png`: a typed color value ("#966A5E") produces an inline preview card (value, arrow, swatch) above the fallback list. The footer shows only "Copy Color as... ↵" and no Actions chip, so the hint disappears when the selection has no panel. → feeds: action-palette
- S1 `references/media/raycast/S1-0073.png`: with an empty query, a "Calendar Events" section sits above "Suggestions", with the next event selected ("Starts in 9 minutes", attendee count at the right). Footer: "Open in Calendar ↵ | Actions ⌘K". The footer label changes with the item type under the cursor. → feeds: action-palette
- S1 `references/media/raycast/S1-0022.png`: when the query matches nothing ("how many hearts does an octop"), the list does not go empty. A 'Use "…" with…' header (with a gear icon) is followed by fallback commands: Search Files, Google Search, AI Chat, Define Word, Translate. The first one is selected. → feeds: action-palette
- S1 `references/media/raycast/S1-0060.png`: loading state: after picking a preset the footer's left slot shows a spinner and "Switching Display Settings...". This replaces the command name, and the list stays interactive. Sections here are "Presets" and "Config" ("New Display Preset", "Help"), and the placeholder is "Filter Presets...". → feeds: action-palette
- S1 `references/media/raycast/S1-0052.png`: success feedback after a destructive action is a small pill HUD at the screen center ("Uninstalled GarageBand") with a faint green edge, shown after the window has closed. S6 says in-window toasts live in the bottom bar's left slot. → feeds: action-palette
- S1 `references/media/raycast/S1-0021.png`: a form view has a back arrow and a help link at the top. Its fields sit in two columns (a text area at the left, name/org/keyword/tags at the right). The footer shows the command name at the left and "Save Snippet Ctrl ↵" at the right, with no Actions chip. This matches S7: ⌘↵ submits a form. → feeds: action-palette, staged-table-edit
- S3 `references/media/raycast/S3-0027.png`: compact mode is a search row (about 996 x 75 px in a 1280 px frame) plus a thin bar with a "Show More ↓" button at the right. Typing or ⌘K expands it to the full list. S5 and S6 say the window collapses again on blur. → feeds: mini-full, action-palette
- S3 `references/media/raycast/S3-0020.png`: "Search Menu Items" is a list-only view: a "Filter by menu item title..." field, a header "Photoshop 2025 · 29 Menu Items", plain text rows as "Menu → Item" paths with no icons, and an item's own app shortcut shown dim at the right. Footer: "Choose Item ↵ | Actions ⌘K". → feeds: list-peek, action-palette
- S3 `references/media/raycast/S3-0037.png`: Store search uses taller two-line rows (title plus a one-line description) with install-count and author badges at the right. "Show Details ↵" is the primary action. The leftover space below two results is just blank list area, with no empty-state message. → feeds: list-peek
- S3 `references/media/raycast/S3-0045.png`: in the older light build the search hint reads "Ask AI Tab" (later builds say "Quick AI"). Sections run Results then 'Use "parcel" with…'. The footer left slot is the Raycast mark. This build uses a full-width footer with a rule above it, like the Windows build. → feeds: action-palette
- S6 (text; `references/media/raycast/S6-fresh-look.png`): the stated reason for the bottom action bar is that ⌘K was hidden behind a small button. The left side of the bar holds the active command's title and any toast. The right side holds the current actions with their shortcuts. The search bar was also made larger, along with the row icons. → feeds: action-palette

## Unseen

- Arrow-key movement inside the open panel, and which row is selected when it opens. The stills show a non-first row highlighted in S2-0019 and S2-0021, but not how it got there.
- The open and close animation of the panel, and what happens to list focus.
- The inline "Set Hotkey" key recorder view. S4 describes it in text, but no source showed it.
- A panel with an empty filter result (nothing matches what was typed in the actions field).
- Destructive actions in red. S4 says so, but no frame shows one.
- Mouse hover on rows and on the footer's Actions chip, and clicking the footer chip to open the panel.
- Error toasts or failed actions. Only success and in-progress feedback was seen.
- Panel behavior for very long action lists (S2-0015 hints at scrolling but no scroll bar or fade was visible).
- What ⌘↵ does on the root search when the first action has no secondary. Only file items were seen with a ⌘↵ action.

## Patterns fed

- action-palette: the main source. It gives the ⌘K card anchored bottom-right above a footer hint, the title-plus-rows-plus-bottom-filter layout, per-key keycaps, the ↵ primary and ⌘↵ secondary slots, flat filtering, sub-menus that replace the panel, and Esc to back out.
- list-peek: the Clipboard History two-pane layout (list about 38%, preview about 62%) with grouped date headings, a live filter, and a type dropdown.
- inspector: the "Information" label/value block under the preview, and the detail views (Now Playing, extension page) with a metadata column.
- mini-full: compact mode (search row only, "Show More ↓" to expand) as the small state of the same window.
- staged-table-edit: only the form footer convention (command name left, "Save X ⌘↵" right) from the snippet form.
- view-switcher: only a weak contribution, the "All Types" dropdown that filters a list in place.
