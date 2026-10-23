# PagerDuty study note

Captured 2026-10-23 from public docs pages and public videos only; no login. Frame paths are relative to the repo's `skills/building-mini-apps/` folder; the media folder is gitignored, so the files exist only on the capture machine. A frame named `S4-t0271.png` is the video frame at 271 seconds; `S2-docs-snooze.png` is a screenshot of a docs page.

## Sources

| ID | URL | Kind | Date | Shows |
|----|-----|------|------|-------|
| S1 | https://docs.pagerduty.com/incident-management/incidents/overview | official | undated, viewed 2026-10-23 | Incident statuses (Triggered, Acknowledged, Resolved), priority vs urgency vs severity, lifecycle, acknowledge, unacknowledge, resolve, the Timeline tab and its filter (text, one page screenshot) |
| S2 | https://docs.pagerduty.com/incident-management/incidents/edit-incidents | official | undated, viewed 2026-10-23 | Merge, snooze rules and presets, edit urgency and priority, reassign service, notes (text, one page screenshot of the snooze section with its dropdown) |
| S3 | https://docs.pagerduty.com/get-started/navigate-incidents-page | official | undated, viewed 2026-10-23 | Incidents page: open-incident counters, Assigned to me / All, status filter, row actions, urgency ordering (text, one page screenshot with the list illustrations). The requested `support.pagerduty.com/main/docs/navigate-the-incidents-page` redirects here. |
| S4 | https://www.youtube.com/watch?v=DU5RB64ydXw | official | 2026-08-03 | "PagerDuty Incident Priority" (PagerDuty channel). Current web UI in Chrome: service page with an open-incidents table, an acknowledged incident's detail page with its action bar, the resolve confirmation, Responders panel |
| S5 | https://www.youtube.com/watch?v=NJvIiX_6Yv8 | official | 2022-08-09 | "PagerDuty Incident Response Demo (Extended)" (PagerDuty channel). Older web UI: an acknowledged P1 incident's detail page, tabs, Run Action and Run Play modals, New Status Update modal. Frame `S5-tNNNN` is NNNN seconds in. |
| S6 | https://www.youtube.com/watch?v=3AdG_vyiZig | official | 2024-05-15 | "Manage incidents end-to-end with PagerDuty" (PagerDuty channel, 93 s). Marketing montage; frames were reviewed and show no incident list or detail page, so nothing from it is cited below. |

Search for a recent third-party walkthrough of the Incidents page returned only vendor videos and integration tutorials; no candidate showed the list itself. The Incidents page appears only as the docs illustrations in S3 and as the service-page table in S4.

## Observations

Lifecycle states and acknowledge

- S1, `references/media/pagerduty/S1-docs-statuses.png`: the three incident statuses are named exactly Triggered, Acknowledged and Resolved. A new incident is always Triggered, whether created by an integration ("triggered") or by a person ("declared"). → feeds: command-center
- S1, section "Incident Statuses": acknowledging claims ownership ("The user who acknowledges an incident claims ownership of the issue and halts the escalation process"). While acknowledged, no notifications go out until the acknowledgement timeout; when it is reached the incident returns to Triggered and escalation resumes. → feeds: command-center
- S1, section "Acknowledge an Incident": Unacknowledge is under the More... button on the detail page. It returns the incident to Triggered, re-sends notifications and resumes escalation. Each incident is limited to 100 acknowledgements. → feeds: command-center
- S1, section "Incident Lifecycle", step 4: users who are not assigned can acknowledge or resolve from the Incidents dashboard depending on permissions. Alerts cannot be acknowledged; they are only triggered or resolved. Resolving an incident resolves its alerts, and resolving all alerts resolves the incident. → feeds: command-center
- S4, `references/media/pagerduty/S4-t0271.png`: right after acknowledging, a green toast across the top reads "Incident 209 has been acknowledged." The status block shows "Acknowledged" in large orange type beside a "Duration 00h 01m" counter and an orange "P2" priority chip. The status is a colored word, not a pill. → feeds: command-center
- S4, `references/media/pagerduty/S4-t0271.png`: the action bar on an acknowledged incident reads Snooze (with a caret), Escalate (caret), Reassign, Add Responders, then Run Workflow, Send Status Update, More (caret), and a filled blue "Resolve" with a check at the far right. There is no Acknowledge button in this frame; Snooze sits where it would be. → feeds: command-center
- S5, `references/media/pagerduty/S5-t0322.png`: the 2022 UI has the same bar with Snooze, Escalate, Reassign, Add Responders, Run a Play, Run Actions, More, and a green "Resolve" at the far right, so Resolve has been the one filled, separated button across both versions. The status block reads "Acknowledged" in orange with "Duration 00h 10m" and a dark red "P1" chip. → feeds: command-center

Snooze

- S2, `references/media/pagerduty/S2-docs-snooze.png`: snooze presets are 1 hour, 4 hours, 8 hours, 24 hours and Other; the maximum for Other is 168 hours (one week). The screenshot shows them as a dropdown under the Snooze button: "1 hr", "4 hrs", "8 hrs", "24 hrs", "Other...". → feeds: command-center
- S2, section "Snooze an Incident": snooze is only available for acknowledged incidents, and "Snooze replaces the Acknowledge button". At expiry an unresolved incident goes back to Triggered and notifies again by the user's notification rules; if another user has come on call since, both are notified. All snooze actions are written to the incident log. → feeds: command-center
- S2, subsections of "Snooze an Incident": reassigning a snoozed incident cancels the timer and resets the acknowledgement timeout to the service default; another user acknowledging a snoozed incident ends the snooze; adding an escalation policy as a responder means snoozing no longer stops escalation; a snooze longer than the service's auto-resolve time keeps the incident snoozed and resets the auto-resolve timer afterwards. → feeds: command-center
- S2, section "Snooze an Incident", "Other" paragraph: the custom option lets the user set a length, snooze until a time tomorrow, or base it on a service's support hours. The mobile app lists 1 hour, 4 hours, 24 hours, "for" and "until". No reason field is mentioned anywhere on the page. → feeds: command-center

Resolve and reopen

- S1, section "Incident Statuses": Resolved means no further notifications, and "You can reopen it if further work is needed." The Reopen Incidents page is in the docs navigation but was not part of this study. → feeds: command-center
- S4, `references/media/pagerduty/S4-t0271.png`: clicking Resolve opens a centered modal titled `Resolve "This is a P2!"?` with Cancel (outlined) and "Resolve Incident" (filled, greyed while a spinner shows). The body is empty at this moment. The page behind dims but stays readable. → feeds: command-center
- S2, section "Merge Behavior": merging resolves the other incidents with the resolution reason "Merged" and links them to the target. The target must be open, and an incident holds at most 1,000 alerts. → feeds: command-center

Urgency, priority and list ordering

- S1, section "Priority, Urgency, and Severity": priority orders work (P1, Sev-1) and is set per incident; urgency (high or low) decides how the assignee is notified; severity belongs to alerts, not incidents. Three separate fields. → feeds: command-center
- S2, section "Edit Incident Urgency": urgency is a High/Low dropdown on the detail page. Raising an acknowledged incident from low to high returns it to unacknowledged and escalation continues with high-urgency rules. → feeds: command-center
- S3, `references/media/pagerduty/S3-docs-incidents-page.png`: the list's own rule is that high-urgency incidents sit above low-urgency ones, and "Incidents maintain this urgency-based order even after acknowledgment". The illustration shows columns Status (red "Triggered" text), Priority (an orange "P2" chip, otherwise "--"), Urgency (plain "High" or "Low"), Title. → feeds: command-center
- S3, `references/media/pagerduty/S3-docs-incidents-page.png`: rows are two lines. The title is a blue link; under it a small caps "SHOW DETAILS (1 triggered alert)" toggle, and the incident number ("#4726") sits right-aligned in small grey type. A second illustration shows tabs Open, Triggered, Acknowledged, Any Status with the active one underlined in orange. → feeds: command-center
- S3, sections "Incidents on All Teams" and "High and Low Urgency Incidents": the top of the page shows counters for open incidents; triggered counts are red, acknowledged orange, zero is blue. Below, "Assigned to me" and "All" switch the scope, and a status filter offers Open, Triggered, Acknowledged, Resolved, Any Status. Checking a row enables Acknowledge, Reassign, Resolve, Snooze and Merge Incidents. → feeds: command-center
- S4, `references/media/pagerduty/S4-t0149.png`: on a service page the table is headed Status, Priority, Urgency, Incident Type, Alerts, Title, Assigned To, Created (with sort arrows on Priority and Created). Above it sit Acknowledge, Resolve, Snooze and Merge Incidents, all greyed because nothing is checked, plus an "All statuses" dropdown and a "Go to incident #" field. The empty state is one centered line, "There are currently no open incidents on this service", with a "+ Create an incident" link. → feeds: command-center

Alert grouping

- S2, section "Merge Incidents": merging pulls the alerts of several incidents into one target, and the dedup key moves with them. Responders of the source incidents are not carried over; subscribers must be re-added. Alerts merged by mistake can be moved to a new or existing incident from the Alerts section. → feeds: command-center
- S5, `references/media/pagerduty/S5-t0322.png`: the Alerts tab of a detail page carries a "Grouping Now" chip beside the "ALERTS" heading, "5 triggered" under it and a link "Alert grouping details". The table has Trigger and Resolve buttons (greyed), Customize Columns, and a per-page selector. → feeds: command-center
- S1, section "Incident Trigger Limitations": an incident stops taking new trigger events after 100 events with the same deduplication key; services with over 100K open incidents auto-resolve new incidents after 24 hours. → feeds: command-center

Detail page and timeline

- S1, section "Incident Timeline": the Timeline tab lists the timestamp of each status change plus every action taken and notification sent, and it can be filtered by specific events and actions. The page shows the filter only as an illustration; the event kinds are not enumerated. → feeds: command-center
- S4, `references/media/pagerduty/S4-t0271.png`: the detail page is a main column plus a right "Responders" panel and a "Notes" box below it. The title row has a breadcrumb (Incidents > Incident #209), an Edit pencil, a "Base Incident" caret, and an orange "ANOMALY" badge with "Not similar to any incidents on this service in the preceding 30 days." Below the action bar, label/value rows read Status ("Acknowledged by" a linked name), Opened ("3:39 PM (a minute ago)"), Assigned to, Escalation policy, Responders (a count of 1 beside a check icon and a count of 1 beside a pending icon), Dedicated channel. A tab strip at the bottom reads Details, Status Updates, Timeline, Automation Actions Log, Past Incidents, Related Incidents. → feeds: command-center
- S5, `references/media/pagerduty/S5-t0322.png`: in the 2022 UI the lower tab strip reads Alerts (with a count), Status Updates, Timeline, Past Incidents, Related Incidents (with a count). Counts sit in small badges. The "Frequent" label says "Similar to 72% of incidents on this service in the preceding 30 days." → feeds: command-center
- S4, `references/media/pagerduty/S4-t0276.png`: the Post-Incident Review tab is empty when opened (a blank body under Overview / Post-Incident Review tabs), while the Responders panel stays put. Responders are listed as Assignee, Incident Commander (Unassigned), Customer Liaison (Unassigned), then "Requested responders" grouped by team with a Renotify link on each group. → feeds: command-center
- S5, `references/media/pagerduty/S5-t0360.png`: "Status Updates" is a tab with a "+ New Update" button; the modal "New Status Update" has a text area, a notice "This update will be published to your status dashboard", and "Send Update" disabled until text exists. Impacted Business Services and Subscribers sit in a left column of that tab. → feeds: command-center
- S5, `references/media/pagerduty/S5-t0258.png`: "Run Actions" opens a modal "RUN ACTION" naming the action ("Rolling Node Restart"), tags (Rundeck, Remediation), a runner, arguments, and Run Job / Cancel. `references/media/pagerduty/S5-t0320.png` shows "Run a Play" as a smaller modal, `Run "Inventory API P1"?`, with "Run this Play" and Cancel. Both are per-incident actions kept out of the main bar's one-click verbs. → feeds: command-center
- S5, `references/media/pagerduty/S5-t0322.png`: hovering Run Actions shows a dark tooltip with a one-line description ("Run automation actions to diagnose or remediate the incident"). → feeds: command-center

Loading

- S4, `references/media/pagerduty/S4-t0271.png`: the resolve dialog shows a centered spinner inside the modal while its body loads, so the dialog frame appears first and its contents later. → feeds: command-center

## Unseen

- Keyboard shortcuts: none of S1 to S3 documents any shortcut for acknowledge, snooze or resolve, and no video showed one.
- The Incidents page itself as a live screen: only docs illustrations (S3) and the service-page table (S4) were available. Row hover, row selection tint and the counters strip were not seen in a real frame.
- The Timeline tab's content: S1 says it has a filter, but no frame opened it, so event kinds, icons and timestamp format are not known.
- The Snooze dropdown on the detail page in a live frame, and what the incident looks like while snoozed (status word, countdown).
- Whether resolving asks for a note or a required field: the S4 dialog was still loading, and "Required Fields on Resolve" was not read.
- Reopen: the docs mention it but no source showed the control or the resulting state.
- Row density and row anatomy of the main Incidents list in a live frame: the S4 table was empty, so only column order and header styling were seen there. Loading and error states for the list were not seen either.
- The mobile app flows (S2 text mentions them) and the trigger notification itself.

## Patterns fed

- command-center: Triggered, Acknowledged and Resolved as the whole visible lifecycle, with acknowledge meaning "I own this, stop escalating" and a timeout that silently returns the item to Triggered; Snooze offered only on acknowledged items, with presets of 1, 4, 8 and 24 hours, a one-week cap and an "Other" for custom or "until tomorrow"; a single filled Resolve at the right of the action bar, away from the other verbs; the list sorted urgency-first and kept in that order after acknowledgement, with priority as a separate colored chip; a status tab strip (Open, Triggered, Acknowledged, Any Status) plus an "Assigned to me / All" scope and counters colored red, orange and blue; row actions that enable only once rows are checked; a detail page with the status as a large colored word, a duration counter, a Responders panel and a Timeline tab.
- view-switcher: the status tab strip and the "Assigned to me / All" scope switch above the Incidents table (S3).
