# Sentry blueprint

The build plan for a close clone of an error tracker studied from Sentry. Evidence is in the [Sentry study note](../apps/sentry.md). The clone matches the screens, layout, navigation, keys and states below and uses one of the skill's styles (Ink Panel by default). Its UI never says "Sentry" and uses no Sentry copy, logos or illustrations.

## Core jobs

| ID | Job | State |
|---|---|---|
| J1 | Triage the issue stream: scan unresolved issues, filter and sort them by frequency, users affected and age | covered |
| J2 | Investigate one issue: read its stack trace, breadcrumbs, tags and event context | covered |
| J3 | Act on issues: assign, resolve, ignore or merge, one at a time or in bulk | covered |
| J7 | Follow a trace across services: the trace explorer and its span waterfall | covered |
| J8 | Watch a session replay around an error | covered |

## Screens

- **App shell**: a narrow icon rail (about 4.5% of the window) beside a section nav (about 11.5%) listing the issue streams and saved views, with the content area taking the rest. Serves J1, J2, J3, J7, J8.
- **Issue stream**: page title with saved-view actions, a filter row (joined project / environment / time-range buttons, a token search box taking about 57% of the row, a sort dropdown), then a table of three-line issue rows about 84px tall with Last Seen, Age, Trend sparkline, Events, Users, Priority and Assignee columns. Serves J1, J3.
- **Issue stream, empty filter**: one bordered card replacing the table, saying no issues match and listing what to check. Serves J1.
- **Issue stream, loading**: the chrome, filter row and table header stay; each row becomes placeholder blocks at the final row height. Serves J1.
- **Issue stream, bulk selection**: ticking row checkboxes turns the table header into an action bar in place (Resolve, Archive, Set Priority, Merge, overflow), with an indeterminate select-all box. Serves J3.
- **Status menus**: Resolve's chevron offers "resolved in" the next release, the current release, another release or a commit; Archive's offers until escalating, forever, for a duration, or until it occurs or affects more users. Serves J3.
- **Assignee picker**: a popover with an auto-focused search, Members and Teams groups, and a Clear link. Serves J3.
- **Command palette**: a centred modal with page actions ("Mark all issues as", "Sort by", "Save as new view") above navigation. Serves J1, J3.
- **Saved views**: an All Views table (star, name, query as chips, last viewed, stars) and an unsaved-changes dot with Save, Save as new view and Reset. Serves J1.
- **Issue detail**: breadcrumb and copy, a large title with level bar, message and status tags, totals at the right; a workflow row (Resolve and Archive split buttons, priority, assignee); an event filter row; an events chart with a tag-distribution card; event navigation (First, Latest, Recommended, previous and next); then collapsible sections (Highlights, Stack Trace, Replay, Breadcrumbs, Logs, Trace Preview, Tags, Contexts) beside a right rail (first and last seen with releases, ownership, activity). Serves J2, J3.
- **Stack trace**: Most Relevant / Full toggle and order control; the crashing in-app frame expanded with an 11-line source excerpt and the failing line highlighted; runs of library frames folded into "Show N more frames". Serves J2.
- **Breadcrumbs**: a vertical, newest-first timeline of icon, category, level, message and timestamp, with search, type filter and order controls. Serves J2.
- **Trace explorer**: a left rail of Visualize, Group By and Sort By controls (about 36% of content), a chart, and Samples / Aggregates tabs over a table whose rows carry a duration bar. Serves J7.
- **Trace waterfall**: a header with stats and vital pills, a search-in-trace row, then a tree of span rows (indent guides, child-count pills, op and description) beside a time axis with duration bars coloured by operation; time-compressed gaps; error badges. Serves J7.
- **Span panel**: clicking a span outlines it and opens a panel (about 40% of the waterfall) that squeezes the timeline; clicking another span swaps it in place; Close restores the full width. Serves J7.
- **Replay list**: two summary cards (most dead clicks, most rage clicks) above a replay table. Serves J8.
- **Replay player**: header with user and click/error counters, a URL bar, the playback area, and a control bar (rewind 10s, play/pause, skip to next event, a marker lane over a seek slider, speed), beside tabs (Activity, Console, Network, Errors, Trace, Tags) whose lists follow the playhead. Serves J8.
- **Replay tab, empty**: the filter row and table header stay; the body says there is nothing to show. Serves J8.
- **Replay summary, error**: a failed-to-load message with Retry. Serves J8.

## Coverage

| Row | Mark | Pattern | Evidence |
|---|---|---|---|
| J1 Triage the issue stream | matched | query-tokens, view-switcher (saved views as tabs), bulk-select (the issue table) | S13-issue-stream.png, S13-sort-menu.png, S2-t0030.png, S8-save-button.png |
| J2 Investigate one issue | matched | inspector (right rail), stack-trace, event-timeline, facet-bars | S13-issue-detail.png, S13-issue-detail-stacktrace.png, S13-issue-detail-breadcrumbs.png, S9-img-issue-details-breakdown-MAZU5VNB.png |
| J3 Act on issues | approximated | bulk-select, conditional-status, action-palette; merge and the action confirmations are left as our design because no public source showed them | S13-bulk-select.png, S13-resolve-menu.png, S13-archive-menu.png, S13-assign-menu.png |
| J7 Follow a trace across services | matched | aggregate-builder, span-waterfall | S13-traces-explorer.png, S13-trace-waterfall.png, S13-span-panel.png, S11-trace-view.png |
| J8 Watch a session replay | matched | replay-player, event-timeline | S13-replay-player.png, S13-replay-scrub-seek.png, S12-replay-details.png, S13-replay-network-tab.png |
| Screen: app shell | matched | base AppShell with sidebar; workspace-panes not needed | S13-issue-stream.png, S8-all-views.png |
| Screen: issue stream | matched | bulk-select with query-tokens above it | S13-issue-stream.png, S3-t1220.png |
| Screen: issue stream, empty filter | matched | base EmptyState naming the cause and the undo | S13-issue-stream-empty-filter.png |
| Screen: issue stream, loading | approximated | base LoadingState as row-height placeholders; the full-page boot splash is left out | S13-issue-stream-skeleton.png |
| Screen: issue stream, bulk selection | matched | bulk-select | S13-bulk-select.png |
| Screen: status menus | matched | conditional-status | S13-resolve-menu.png, S13-archive-menu.png, S10-issue-status-diagram.png |
| Screen: assignee picker | approximated | bulk-select row cell with a searchable popover; invite is left out | S13-assign-menu.png |
| Screen: command palette | matched | action-palette | S13-command-palette.png |
| Screen: saved views | approximated | view-switcher revision (named views with a dirty marker); sharing and permissions left out | S8-all-views.png, S8-unsaved-changes.png |
| Screen: issue detail | matched | inspector rail, sections stacked in the main column | S13-issue-detail.png, S6-t0080.png |
| Screen: stack trace | matched | stack-trace | S13-issue-detail-frames-expanded.png, S13-issue-detail-frames-collapsed.png |
| Screen: breadcrumbs | matched | event-timeline | S13-issue-detail-breadcrumbs.png |
| Screen: trace explorer | matched | aggregate-builder | S13-traces-explorer.png, S13-trace-samples.png |
| Screen: trace waterfall | matched | span-waterfall | S13-trace-waterfall.png, S11-time-compression.png, S11-pinned-columns.png |
| Screen: span panel | matched | span-waterfall | S13-span-panel.png, S13-span-panel-second-span.png, S13-trace-waterfall-panel-closed.png |
| Screen: replay list | approximated | bulk-select table; the dead and rage click cards left out | S13-replay-list.png |
| Screen: replay player | matched | replay-player | S13-replay-player.png, S13-replay-playing.png, S12-replay-details.png |
| Screen: replay tab, empty | matched | base EmptyState inside the tab | S13-replay-errors-tab-empty.png |
| Screen: replay summary, error | left out | AI summaries are not part of the clone | S13-replay-player.png |
| Screen: DOM inspection inside a replay | left out | needs real DOM recordings | unseen |

## Composition

- **Shell.** One `AppShell` with a sidebar holding section nav: Issues (with the saved views starred under it), Traces, Replays. The content area renders one screen at a time; the issue detail, trace and replay pages are full views opened from their lists, with a back control and the list's state kept.
- **Collections** (`useCollection` names): `issues`, `events`, `releases`, `members`, `saved-views` for J1 to J3; `traces`, `spans` for J7; `replays`, `replay-events` for J8.
- **Key map** (our design where marked): ⌘K opens action-palette everywhere, acting on the selection when rows are selected. `/` focuses the query-tokens box. In the issue table, j/k move the highlight, x toggles selection, Enter opens the issue, Esc clears the selection (our design; the studied app advertises no row keys). In span-waterfall, ↑/↓ move between spans, ←/→ collapse and expand, Enter opens the panel, Esc closes it (our design). In replay-player, Space plays or pauses and ←/→ seek 5s while focus is in the player (our design). No binding uses ⌘N, ⌘T, ⌘W or ⌘L.
- **Domain model.**
  - Issue: id, shortId, title, culprit, message, level (fatal, error, warning, info, debug), status (new, ongoing, escalating, regressed, resolved, archived), resolution (now, inNextRelease, inRelease, inCommit), archiveUntil (escalating, forever, a date, an occurrence count, a user count), priority (high, medium, low), assignee, firstSeen, lastSeen, count, userCount, project, firstRelease, lastRelease, unhandled, trend (hourly counts for 24h, daily for 14d).
  - Event: id, issueId, timestamp, message, tags (key, value), contexts (user, browser, os, device), exception (type, value, frames), breadcrumbs, traceId, replayId.
  - Frame: module, function, filename, lineNo, colNo, inApp, contextLines.
  - Breadcrumb: timestamp, category, type, level, message, data.
  - Trace: id, rootTransaction, duration, spanCount, errorCount, project.
  - Span: id, traceId, parentId, op, description, start, duration, project, status, attributes.
  - Replay: id, user, startedAt, duration, urls, browser, os, deadClicks, rageClicks, errorIds.
  - ReplayEvent: replayId, offset, kind (navigation, click, console, network, error), label, detail.
  - Release: version, createdAt. SavedView: name, query, sort, project, environment, period, starred.
- **Sample data** uses invented services, routes and users; never real Sentry projects or customers.

## Proposed patterns

Stop 2 on 2026-10-23 approved eight of these and both revisions, and all ten were built on 2026-10-23; facet-bars was not approved and stays unbuilt.

- **bulk-select** (approved at Stop 2, built): a dense selectable table where ticking any row turns the column header into an action bar in place, with an indeterminate select-all box, actions that disable themselves with a stated reason, and the count of selected rows. When to use: clearing out a photo library or a mail inbox, where the user picks many items and applies one action. Components: indeterminate checkbox, header action bar, trend sparkline cell (a small bar histogram with its peak value), assignee popover cell. Dependencies: none.
- **query-tokens** (approved at Stop 2, built): a search box where `key:value` filters render as removable chips, focus opens a key list grouped by type with recent searches, free text falls back to plain search, and the query lives in the URL. When to use: a recipe collection filtered by `cuisine:thai time:<30`. Components: token chip, suggestion popover. Dependencies: none.
- **conditional-status** (approved at Stop 2, built): a split button whose primary action changes state now and whose menu offers deferred or conditional versions (resolve in the next release; archive until it recurs, until a date, or forever), with a lifecycle that can reverse itself (a resolved item regresses, an archived one escalates). When to use: a task app's "snooze until Monday" or "until they reply". Components: split button, nested condition menu. Dependencies: none.
- **stack-trace** (approved at Stop 2, built): a list of collapsible frames where relevant frames open to a numbered source excerpt with the failing line highlighted, runs of library frames fold into one "show N more" row, and a toggle switches between relevant and full views. When to use: a test-runner app showing why a test failed, or a log viewer showing a crash. Components: code excerpt with line numbers. Dependencies: none.
- **event-timeline** (approved at Stop 2, built): a vertical, time-ordered list of typed entries (icon, category, level, message, time) with a type filter and search, that can follow a playhead and seek to an entry's time when clicked. When to use: a parcel-tracking history or an audit log of a document's edits. Components: entry row, playhead divider. Dependencies: none.
- **facet-bars** (not approved at Stop 2): for each key, its top values as proportional bars with percentages, where clicking a value filters by it. When to use: a reading list showing genre and author spread. Components: percent bar row. Dependencies: none.
- **span-waterfall** (approved at Stop 2, built): a tree of timed rows with indent guides and child-count collapse pills beside a shared time axis of duration bars, compressed empty gaps, error badges, and a side panel that opens on click and squeezes the timeline, with pinnable attribute columns. When to use: a build pipeline's step timings, or a project's tasks and subtasks over time. Components: time axis, duration bar, collapse pill, resizable side panel. Dependencies: none.
- **replay-player** (approved at Stop 2, built): a playback surface with transport controls (back 10s, play/pause, skip to next event, speed), a marker lane over a seek slider, and a side panel of tabs whose lists follow the playhead and seek when an entry's time is clicked. When to use: reviewing a recorded meeting against its transcript, or tagging moments in a training video. Components: marker lane, seek slider, speed stepper. Dependencies: none for the clone, which plays back a sequence of snapshots; replaying real browser recordings would need a recording player library, not proposed.
- **aggregate-builder** (approved at Stop 2, built): a left rail of Visualize, Group By and Sort controls that drives a chart and a table with Samples and Aggregates tabs. When to use: an expense log grouped by category and month. Components: field picker, aggregate picker. Dependencies: none; the chart is drawn in SVG.

## Proposed revisions

- **action-palette** (approved at Stop 2, built): an optional multi-item target, so ⌘K acts on every selected row and its header chip names the count. Additive: single-item use is unchanged. Evidence: S13-command-palette.png, S13-bulk-select.png.
- **view-switcher** (approved at Stop 2, built): optional named views (query, sort and filters saved together) with an unsaved-changes marker and Save, Save as new view and Reset. Additive: views are off unless passed. Evidence: S8-unsaved-changes.png, S8-save-button.png.
