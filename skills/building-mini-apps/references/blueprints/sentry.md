# Sentry blueprint

## Core jobs

| ID | Job | State |
|---|---|---|
| J1 | Triage the issue stream: scan unresolved issues, filter and sort them by frequency, users affected and age | confirmed |
| J2 | Investigate one issue: read its stack trace, breadcrumbs, tags and event context | confirmed |
| J3 | Act on issues: assign, resolve, ignore or merge, one at a time or in bulk | confirmed |
| J7 | Follow a trace across services: the trace explorer and its span waterfall | confirmed |
| J8 | Watch a session replay around an error | confirmed |
