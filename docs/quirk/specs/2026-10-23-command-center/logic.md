# Logic spec: `command-center`, the eleventh building-mini-apps pattern

## Status & amendments

**Status**: Approved · Tech spec: authored (`tech.md`; tier gate fired: >3 files across docs, scripts, tests and gallery)

**Amendments:** none yet.

This spec adds one pattern to the skill approved in
[the building-mini-apps logic spec](../2026-10-22-building-mini-apps/logic.md). Everything that spec
locks (template shape, stack, house style, quality bar, the media rules) holds here unchanged; this
document covers only what the new pattern adds.

I asked for a "command center" template. After comparing three models on a design board (Home
Assistant tiles, a PagerDuty-style attention queue, and Grafana panels), I chose a hybrid of the first
two: an overview of things I watch, where I can act on each one, and a queue of whatever needs me
right now.

## Conceptual model

The command-center pattern is for apps where the user watches a set of things and acts on whichever
ones need them. It is an overview you act from, not a dashboard you read.

- **Tile**: one watched thing (a device, an account, a service, a project) with a current state.
  Some tiles are controls: an on/off toggle, a level, a target value. Others only report. Tiles sit
  in named sections that come from the data, such as rooms.
- **Flag rule**: a tile's condition for "this needs you", such as "the lock is unlocked" or
  "humidity is above 55%". A rule also says how urgent its item is.
- **Attention item**: an entry in the "needs you" queue. A flag rule opens one, and the app can add
  items no tile represents, such as a bill that is due. An item has a title, an urgency (Now or
  Later), an optional link to its tile, and a timeline.
- **Timeline**: the item's append-only list of events (opened, flagged again, acknowledged, snoozed,
  snooze ended, cleared, resolved, reopened). The item's status is always derived from its timeline,
  never stored on its own.
- **Status**: open, acknowledged, snoozed, or resolved. Acknowledged means "I've seen it and I own
  it"; it stays in the queue. Snoozed hides it until a time. Resolved removes it from the queue.

The only charts are a sparkline inside numeric tiles and a larger history chart in a tile's details
dialog. Standalone chart panels belong to read-only dashboards, which the skill hands to
writing-html-artifacts.

## Data flow

Tiles and items live in the app's store. Optionally, the app passes a refresh function and an
interval; the block calls it on that interval and writes the returned tile states to the store.

Every time tile states change, the flag rules run against them:

- A condition that has just become true either opens a new item, adds a "Flagged again" entry to
  the tile's open item, or reopens the tile's item if it was resolved within the last 24 hours.
- A condition that has just stopped being true resolves the tile's item with a "Cleared" entry.
- A tile whose value is older than its staleness threshold is marked stale. If that tile opts in,
  staleness itself is a flag rule and opens a Later item.

The screen reads the same records. The header shows the source label and the refresh state. The
badge row shows summary badges and an "N need you" count. The tile board shows sections of tiles.
The queue column groups open and acknowledged items into Now and Later.

The user's actions write back: a tile toggle changes the tile's state (and so may clear a flag);
acknowledge, snooze, and resolve append timeline events. One coarse tick, about once a minute and
on every render, compares each snooze's end time with the clock; an expired snooze appends "Snooze
ended" and the item returns as open.

## Key decisions & rationale

- **Two click targets per tile.** The tile's icon toggles; the tile body opens details. This is Home
  Assistant's default, and its own design discussions trace accidental changes to tiles where one
  click both opens and toggles. Tiles marked sensitive (a door lock, a garage door) ask before
  toggling; others toggle at once.
- **Acknowledge is ownership, not closure.** It follows PagerDuty: an acknowledged item stays in the
  queue. Snooze departs from PagerDuty, which allows snooze only after acknowledging: here it works
  from open or acknowledged, because a single user doesn't need the extra step.
- **Snooze takes preset times plus an optional note.** incident.io requires a reason; for one person
  that's friction, so the note is optional and goes in the timeline when given.
- **Status is derived from the timeline.** Storing it separately invites the two to disagree, and the
  timeline is already the record the user reads.
- **Two urgency levels.** Research on alert fatigue says fewer tiers get more attention. Now items
  head the queue; Later items wait under them.
- **A condition that clears resolves its item.** The queue then shows only what is still true, which
  is the main defense against over-flagging.
- **Staleness is visible but opt-in for the queue.** Stale values look live by default, so a stale
  tile always says so with text and an icon. Only tiles that opt in turn staleness into an item,
  because most sensors going quiet isn't worth a queue entry.
- **The page says where its data comes from.** The header shows a source label and the refresh
  state (Live, Paused, Stale) with the last refresh time. The demo says "Sample data", so nothing
  implies it is live when it isn't.
- **The block is assembled from exported parts plus pure logic.** `CommandCenter` is built from
  parts the app can use alone or rearrange (the badge row, the tile board, the tile dialog, the
  attention queue), which take plain props with no shared wrapper. The flag rules and the item
  lifecycle are pure functions, and one hook wires them to the store, the refresh, and the tick.
  This is the shape the inspector, view-switcher, and staged-table-edit blocks already use, and an
  agent editing one file at a time can't silently break a hidden provider contract.

## Behavior & scenarios

1. **SC-1 A tile condition opens an item**
   - **Given** the Front door tile is locked and has no item
   - **When** the door reports unlocked
   - **Then** the tile shows the attention style with "Unlocked" in text and an icon; a Now item "Front door unlocked" opens in the queue with an "Opened" timeline entry; the "N need you" count goes up by one
   - **Data before:** **Front door tile**: Locked; **Queue**: 2 open items
   - **Walkthrough:**
     1. The refresh returns the Front door as unlocked
     2. The lock rule's condition becomes true; no open or recently resolved item exists for the tile
     3. A new item opens with urgency Now
   - **Data after:** **Front door tile**: ✓ Unlocked, attention style; **Item "Front door unlocked"**: ✓ open, Now, timeline "Opened 07:10*"; **Queue**: ✓ 3 open items

2. **SC-2 The condition clears and the item resolves itself**
   - **Given** the Front door item is open
   - **When** the user locks the door from the tile's icon and confirms
   - **Then** the tile shows Locked; the item resolves with "Cleared: Front door locked" and leaves the queue
   - **Data before:** **Front door tile**: Unlocked, sensitive; **Item "Front door unlocked"**: open
   - **Walkthrough:**
     1. The user clicks the tile's lock icon
     2. A confirm dialog asks "Lock Front door?"; the user confirms
     3. The tile state becomes Locked; the lock rule's condition becomes false
   - **Data after:** **Front door tile**: ✓ Locked; **Item "Front door unlocked"**: ✓ resolved, timeline adds "Cleared: Front door locked 07:25*"; **Queue**: ✓ item removed

3. **SC-3 A repeat flag reuses or reopens**
   - **Given** a tile flags while its item is (a) still open, (b) resolved 3 hours ago, or (c) resolved 2 days ago
   - **When** the condition becomes true again
   - **Then** (a) the open item gains a "Flagged again" entry; (b) the resolved item reopens with a "Reopened" entry; (c) a new item opens
   - **Data before:** **Basement humidity item**: (a) open; (b) resolved 3 h ago; (c) resolved 2 d ago
   - **Walkthrough:**
     1. Humidity crosses 55% again
     2. The rule finds the tile's latest item and checks its status and resolve time against 24 hours
   - **Data after:** (a) ✓ same item, timeline adds "Flagged again"; (b) ✓ same item reopened, status open; (c) ✓ new item, the old one stays resolved

4. **SC-4 Acknowledge keeps the item in the queue**
   - **Given** the Basement humidity item is open
   - **When** the user selects it and presses `a`
   - **Then** its status reads Acknowledged; it stays in the queue in the same urgency group; the timeline adds "Acknowledged"

5. **SC-5 Snooze and return**
   - **Given** the Basement humidity item is acknowledged
   - **When** the user snoozes it with "Tomorrow morning" and the note "Emptying the tank tonight", and later the snooze time passes while the page is open
   - **Then** the item leaves the queue at once; when the time passes it returns as open, the timeline adds "Snooze ended", and a polite screen-reader announcement says "Basement humidity is back"
   - **Data before:** **Item "Basement humidity above 55%"**: acknowledged
   - **Walkthrough:**
     1. The user picks Tomorrow morning (08:00*) and types the note
     2. The timeline adds "Snoozed until 08:00, Emptying the tank tonight"; the item leaves the queue
     3. At the next tick after 08:00 the item's snooze has ended
   - **Data after:** **Item "Basement humidity above 55%"**: ✓ open, back in the Later group; timeline ends "Snooze ended 08:00*"

6. **SC-6 A standalone item**
   - **Given** the app adds the item "Electric bill due Friday" with urgency Later and no tile
   - **When** the user opens it in the queue
   - **Then** it shows acknowledge, snooze, and resolve, and no tile link; it leaves the queue only when snoozed or resolved by hand

7. **SC-7 Tile details for a flagged tile**
   - **Given** the NAS backup tile is flagged and its item is open
   - **When** the user clicks the tile body
   - **Then** a dialog opens with the tile's controls (if any), its exact last-update time, a history chart, and below them the linked item's actions and timeline; acting on the item there updates the queue at once; Esc closes the dialog and returns focus to the tile

8. **SC-8 A stale tile**
   - **Given** the Garage temperature tile has a 1-hour staleness threshold and last updated 3 hours ago, and the NAS backup tile opts in to staleness with a 24-hour threshold
   - **When** the page renders
   - **Then** the Garage tile shows its value dimmed with "Stale" and an icon and "Updated 3 h ago", and opens no item; if the NAS backup tile goes 24 hours without an update, a Later item "NAS backup has not reported" opens

9. **SC-9 Refresh states**
   - **Given** the app passed a refresh function with a 30-second interval
   - **When** refreshes succeed, the user pauses, and later a refresh fails
   - **Then** the header shows "Live, updated 07:05" while refreshing; "Paused" with a Resume control after pausing (no refreshes run); after a failure, an error banner with Retry while the last good tile states stay on screen and the refresh state reads "Stale since 07:05"
   - **Screen states:**

     | Situation | Header refresh state | Tiles |
     |---|---|---|
     | Refreshing normally | ✓ "Live · updated 07:05" | current |
     | Paused | ✓ "Paused" plus Resume | last values, unchanged |
     | Refresh failed | ✓ "Stale since 07:05" plus an error banner with Retry | last good values, not cleared |
     | No refresh function | ✓ source label only | as given by the app |

10. **SC-10 Keyboard triage**
    - **Given** focus is in the queue with three items
    - **When** the user presses `j`, `k`, `a`, `s`, `r`, and Enter
    - **Then** `j` and `k` move the selection; `a` acknowledges, `s` opens the snooze choices, and `r` resolves the selected item; Enter expands it in place; none of these fire while focus is in a text field

11. **SC-11 Narrow window**
    - **Given** the window is under about 768 px wide
    - **When** the page renders with 3 open items
    - **Then** the queue becomes a collapsed "3 need you" strip above the tiles that expands in place; tiles flow in one column underneath

12. **SC-12 Empty and loading states**
    - **Given** (a) the store is loading, (b) the app has no tiles, or (c) nothing needs the user
    - **When** the page renders
    - **Then** (a) the base loading state shows in the tile area; (b) the base empty state reads "No tiles yet"; (c) the queue column reads "Nothing needs you" and the count badge is hidden

13. **SC-13 The demo shows the lifecycle**
    - **Given** the gallery demo with sample home data and the source label "Sample data"
    - **When** the user picks events from the demo's "Simulate event" menu (door unlocks, humidity rises, humidity falls, backup fails, backup succeeds)
    - **Then** tiles change and items open, gain entries, and resolve exactly as in SC-1 to SC-3; nothing changes unless the user picks an event or acts; the menu exists only in the demo, not in the block

## Scope & non-goals

In scope:

- The pattern reference `references/patterns/command-center.md`, with the same six sections as the
  other ten.
- Three app studies under `references/apps/`: Home Assistant, from its public demo
  (demo.home-assistant.io) and docs, with frames captured to the gitignored media folder; PagerDuty
  and incident.io, from their docs and public videos.
- The block, its demo, and its registry item, built to the parent spec's quality bar.
- Adding the pattern and the three apps to the skill's index, `check_docs.py`, and the skill test's
  pattern list.
- A one-line amendment to the parent spec's scope noting the eleventh pattern and linking here.

Not in scope:

- Push, email, or OS notifications. Attention shows only in the page.
- Escalation, on-call schedules, or assigning items to people. It is single-user.
- An in-app editor for flag rules or staleness thresholds. They live in the app's data or code.
- Drag-to-rearrange tiles or an edit mode. Order comes from the data.
- Chart panels as tiles or sections.
- A built-in integration with any service. The refresh function is the app's to write.
- Logging into PagerDuty, incident.io, or any other app.

## Decisions Locked

**Model**
- A hybrid of Home Assistant's dashboard (artboard A) and an incident.io / PagerDuty attention queue (artboard B), chosen after the [design board](https://claude.ai/artifact/1AG62L26P2g9EMogKom5EJ).

**What lands in the queue**
- Tile conditions and standalone items; an item is its own record with an optional tile link.
- A condition that clears resolves its item automatically, with a timeline entry.
- A repeat flag reuses the open item, reopens one resolved within 24 hours, and otherwise opens a new one.
- Two urgency levels: Now and Later.

**Tile and queue actions**
- The icon toggles; the tile body opens details.
- Only tiles marked sensitive confirm before toggling.
- Snooze works from open or acknowledged; the item returns as open.
- Snooze offers 1 hour, This evening, Tomorrow morning, Next week, and a date, plus an optional note.
- A flagged tile's details dialog shows the linked item's actions and timeline.
- Keys: `j`/`k` move, `a` acknowledge, `s` snooze, `r` resolve, Enter expand (our design).

**Layout**
- A queue column on the right, always visible; tile details open in a dialog.
- The badge row holds summary badges and one "N need you" count that focuses the queue.
- A selected queue item expands in place in the column.
- Below about 768 px the queue becomes a collapsible "N need you" strip above the tiles.
- Tiles are grouped into named sections from the data, in data order.

**Freshness and honesty**
- A tile shows its age only when older than its own staleness threshold; the dialog always shows the exact time.
- A stale tile shows a dimmed value with "Stale" text and an icon, and opens a Later item only if it opts in.
- The header shows a source label from the app (the demo's is "Sample data · loaded 07:05").
- The demo has a "Simulate event" menu; the block has no simulator.
- A snooze that ends while the page is open returns the item at once with a polite announcement.

**Scope extensions**
- Numeric tiles show a sparkline; the details dialog shows a larger history chart; no chart panels.
- The block accepts a refresh function and interval, with Live, Paused, and Stale states, a pause control, and an error state on failure.

**Studies and spec**
- Home Assistant is studied from its public demo plus docs, with frames captured; PagerDuty and incident.io from docs and public videos, with no logins.
- Both PagerDuty and incident.io get a study note.
- This spec is new and links to the parent; the parent gets a one-line scope amendment.

**Block shape**
- `CommandCenter` is assembled from exported parts with plain props and no shared wrapper, plus pure rule and lifecycle functions and one wiring hook.

## Industry Insights

- **Home Assistant's tile has two targets.** The tile body opens more-info by default and the icon
  toggles; badges sit above the view, and an entity-filter badge shows only entities matching
  conditions. ([Tile card](https://www.home-assistant.io/dashboards/tile/),
  [Badges](https://www.home-assistant.io/dashboards/badges/),
  [Actions](https://www.home-assistant.io/dashboards/actions/),
  [Sections view](https://www.home-assistant.io/dashboards/sections/))
- **Tiles that both open and toggle cause accidental changes.** Home Assistant's own design review
  settled on "a toggle should toggle", with optional confirmation.
  ([frontend discussion #8905](https://github.com/home-assistant/frontend/discussions/8905))
- **Acknowledge claims ownership; snooze is a timed pause that returns.** In PagerDuty, snooze is
  only for acknowledged incidents and returns them to triggered on expiry; incident.io requires a
  reason for a snooze and counts it as an acknowledgement.
  ([PagerDuty incidents](https://docs.pagerduty.com/incident-management/incidents/overview),
  [PagerDuty editing incidents](https://docs.pagerduty.com/incident-management/incidents/edit-incidents),
  [incident.io snoozing](https://docs.incident.io/on-call/snoozing-escalations))
- **Urgency and priority are separate in PagerDuty**, and incident.io groups repeated alerts into
  one incident within a window.
  ([incident.io grouping](https://docs.incident.io/alerts/grouping-alerts))
- **Over-flagging is the main failure of alert inboxes**; most alerts need no action, so fewer
  tiers and auto-clearing matter. (vendor figures, unverified:
  [incident.io](https://incident.io/blog/escalation-policy-anti-patterns))
- **Stale values look live by default.** Show "as of" times and Live, Stale, or Paused states.
  ([Smashing Magazine](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/),
  [DEV field lesson](https://dev.to/atlasscada/the-dashboard-said-everything-was-fine-a-field-lesson-in-honest-data-3nf1))
- **Status needs text, not color alone** (WCAG 1.4.1), and toggle buttons keep a constant label
  with `aria-pressed`. ([Scottish Government status tag](https://designsystem.gov.scot/components/status-tag),
  [APG button pattern](https://www.w3.org/WAI/ARIA/apg/patterns/button/))
- **Live regions get chatty**: one polite region for summaries, assertive only for failures.
  ([rightsaidjames](https://rightsaidjames.com/2025/08/aria-live-regions-when-to-use-polite-assertive/))
- **Keep the logic headless and derive state.** Rules and lifecycle as plain functions; status
  derived from the event log; store an expiry time and recheck on a coarse tick rather than one
  timer per item, since background tabs throttle timers.
  ([Fowler, headless component](https://www.martinfowler.com/articles/headless-component.html),
  [Fowler, event sourcing](https://martinfowler.com/eaaDev/EventSourcing.html),
  [MDN setTimeout](https://developer.mozilla.org/en-US/docs/Web/API/Window/setTimeout))
- **Copied blocks become the app's code.** A big config object turns into prop soup, and compound
  parts that depend on a hidden provider break when moved; section-sized parts plus a thin composer
  adapt best. ([shadcn architecture](https://www.matthewswong.com/en/blog/shadcn-ui-component-architecture/),
  [Smashing, compound components](https://www.smashingmagazine.com/2021/08/compound-components-react/),
  [Tremor Blocks](https://blocks.tremor.so/))

## Deferred Ideas

- `[tech-spec]` Keyboard movement across the tile grid (roving focus versus plain Tab order). No
  source covered dense tile grids; the tech spec picks one and the reference marks it "our design".
- `[tech-spec]` Whether the timeline's event shape carries a version, since saved timelines outlive
  the code that wrote them.

## Glossary

- **Tile**: one watched thing with a current state, shown in a section; it may also be a control.
- **Sensitive tile**: a tile whose toggle asks for confirmation.
- **Flag rule**: a tile's condition for needing the user, with the urgency of the item it opens.
- **Attention item**: an entry in the "needs you" queue, from a flag rule or added by the app.
- **Timeline**: an item's append-only list of events; its status is derived from it.
- **Acknowledged**: seen and owned; still in the queue.
- **Snoozed**: hidden until a time, then back as open.
- **Stale**: a tile whose last update is older than its staleness threshold.
- **Source label**: the header text saying where the data comes from.
- **Refresh state**: Live, Paused, or Stale, for apps that pass a refresh function.
