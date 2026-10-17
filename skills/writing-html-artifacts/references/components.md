# Component kit reference

Generated from `vendor/kit/1.0.0/catalog.json` by `scripts/kit_docs.py reference`. Do not edit by hand.

## How inclusion works

Write any `q-*` tag in a source and the builder inlines the kit automatically; `q-chart` also inlines Chart.js and `q-flow` inlines the flow layout library. Never list `kit` or `flow` in the source header's `libraries`. A tag that breaks its element's contract below fails the build's `kit` check, which names the element and the problem.

## Tag index

- [`q-tabs`](#q-tabs)
- [`q-chart`](#q-chart)
- [`q-stat`](#q-stat)
- [`q-table`](#q-table)
- [`q-timeline`](#q-timeline)
- [`q-code`](#q-code)
- [`q-diff`](#q-diff)
- [`q-diff-note`](#q-diff-note) (inside `q-diff`)
- [`q-board`](#q-board)
- [`q-grid`](#q-grid)
- [`q-panel`](#q-panel)
- [`q-sidenote`](#q-sidenote)
- [`q-compare`](#q-compare)
- [`q-flow`](#q-flow)

## `q-tabs`

Use when a page has two or more parallel views of the same subject and the reader needs one at a time, such as a summary, the details and the raw data.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `label` | no | text | - | - | The tab list's accessible name, for example "Report sections". |

### Children

Direct-child `<section>` elements, each opening with an h2 to h6 heading as its first element child. The heading text becomes the tab label and stays in the panel, visually hidden. Without JavaScript the sections simply stack.

### Example

```html
<q-tabs label="Release review">
  <section>
    <h3>Summary</h3>
    <p>The 2.4 release shipped on schedule. Checkout latency improved, and one rollback was needed for the address form.</p>
  </section>
  <section>
    <h3>Timeline</h3>
    <p>Rollout started Tuesday at 09:00 UTC and reached every region by Wednesday at noon.</p>
  </section>
  <section>
    <h3>Follow-ups</h3>
    <ul>
      <li>Add a canary stage for the address form.</li>
      <li>Alert on checkout p95 above 800 ms.</li>
    </ul>
  </section>
</q-tabs>
```

Companion option html: not allowed (interactive)

## `q-chart`

Use when a small table of numbers is easier to read as a bar, line, area or donut chart and the finding can be stated in one sentence.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `summary` | yes | text | - | - | One sentence stating the finding; it becomes the chart's accessible label. |
| `type` | no | enum | `bar`, `line`, `area`, `donut` | `bar` | Chart type. |
| `x` | no | text | - | - | Header of the column that holds the categories; defaults to the first column. |
| `y` | no | text | - | - | Comma-separated headers of the value columns; defaults to every other column. |
| `stacked` | no | boolean | - | - | Stack the series instead of drawing them side by side. |
| `horizontal` | no | boolean | - | - | Draw bars horizontally; applies to the bar type only. |
| `data-from` | no | ident | - | - | Name of a field in the page's data file to chart instead of an inline table. |

### Children

A `<table>` whose `<thead>` has one `<th>` per column: the first column holds the categories and each other column is one series. Alternatively set data-from and omit the table. Optionally add a child `<script type="application/json">` holding raw Chart.js options, which the theme guarantees override. At most 8 series are drawn.

### Example

```html
<q-chart type="line" summary="Median build time fell from 14 to 9 minutes between June and September." y="Median minutes">
  <table>
    <thead>
      <tr><th>Month</th><th>Median minutes</th></tr>
    </thead>
    <tbody>
      <tr><td>June</td><td>14</td></tr>
      <tr><td>July</td><td>12</td></tr>
      <tr><td>August</td><td>10</td></tr>
      <tr><td>September</td><td>9</td></tr>
    </tbody>
  </table>
  <script type="application/json">{"plugins": {"legend": {"display": false}}}</script>
</q-chart>
```

Companion option html: allowed

## `q-stat`

Use when a single headline number needs a label, a signed change and a definition of its period and denominator.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `direction` | no | enum | `up-good`, `down-good` | `up-good` | Whether a rise is good or bad; colors the delta. |
| `points` | no | number-list | - | - | Two or more comma-separated numbers drawn as a decorative sparkline. |

### Children

Child elements marked with the slot attribute: slot="label", slot="value" and slot="definition" are required, and slot="delta" is optional. The delta's sign comes from its leading +, -, minus sign or digit. Adjacent q-stat elements form a responsive row.

### Example

```html
<q-stat direction="up-good" points="41,43,42,47,52,58">
  <span slot="label">Weekly active users</span>
  <span slot="value">58,200</span>
  <span slot="delta">+11.5%</span>
  <span slot="definition">Distinct signed-in users per ISO week, versus the prior week.</span>
</q-stat>
<q-stat direction="down-good" points="4.1,3.9,3.6,3.4,3.1">
  <span slot="label">Checkout error rate</span>
  <span slot="value">3.1%</span>
  <span slot="delta">-0.3 pts</span>
  <span slot="definition">Failed checkout attempts divided by all attempts, last 7 days.</span>
</q-stat>
<q-stat direction="down-good">
  <span slot="label">Median support wait</span>
  <span slot="value">4m 20s</span>
  <span slot="delta">+12s</span>
  <span slot="definition">Time from first message to first human reply, last 7 days.</span>
</q-stat>
```

Companion option html: allowed

## `q-table`

Use when a table has more than a few rows and the reader will want to sort it, filter it or scroll it without the page scrolling sideways.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `data-from` | no | ident | - | - | Name of a field in the page's data file to build the rows from. |

### Children

A `<table>` with a `<thead>`. Mark numeric columns with class="num" on their `<th>` so they sort by value. Clicking a header sorts ascending, then descending, then back to the authored order. With data-from, each `<th>` binds to the row field named by its data-key attribute, or else by its trimmed text.

### Example

```html
<q-table>
  <table>
    <thead>
      <tr><th>Service</th><th class="num">Requests</th><th class="num">p95 ms</th><th>Owner</th></tr>
    </thead>
    <tbody>
      <tr><td>checkout</td><td>1,204,000</td><td>310</td><td>Payments</td></tr>
      <tr><td>catalog</td><td>3,890,500</td><td>120</td><td>Storefront</td></tr>
      <tr><td>search</td><td>2,410,300</td><td>185</td><td>Discovery</td></tr>
      <tr><td>accounts</td><td>612,900</td><td>95</td><td>Identity</td></tr>
    </tbody>
  </table>
</q-table>
```

Companion option html: not allowed (interactive)

## `q-timeline`

Use when events happen in order and the reader needs to see when each one occurred, such as an incident, a rollout or a project history.

### Attributes

This element takes no attributes of its own.

### Children

An `<ol>` whose every `<li>` holds a `<time datetime>` element followed by the event text. An `<li>` may carry data-tone set to neutral, success, warning or danger.

### Example

```html
<q-timeline>
  <ol>
    <li data-tone="warning"><time datetime="2026-09-14T09:02Z">09:02</time> Error rate on checkout crosses 2%.</li>
    <li data-tone="danger"><time datetime="2026-09-14T09:10Z">09:10</time> Pager fires; incident declared.</li>
    <li data-tone="neutral"><time datetime="2026-09-14T09:31Z">09:31</time> Bad config identified in the 2.4 rollout.</li>
    <li data-tone="success"><time datetime="2026-09-14T09:44Z">09:44</time> Rollback complete; error rate back to baseline.</li>
  </ol>
</q-timeline>
```

Companion option html: allowed

## `q-code`

Use when the reader should copy a command, config or code snippet exactly as written.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `filename` | no | text | - | - | File name shown in the header bar above the code; its extension picks the highlighting language when language is not set. |
| `language` | no | ident | - | - | highlight.js language name or alias, such as yaml, json, bash or tsx; an unknown name shows plain text. |

### Children

A `<pre>` wrapping a `<code>` element with the text to copy. The code is highlighted by language, or else by the filename extension; with neither, or without JavaScript, it shows as plain text.

### Example

```html
<q-code filename="deploy.sh">
  <pre><code>#!/usr/bin/env bash
set -euo pipefail
./build.sh --release
./push.sh --env staging</code></pre>
</q-code>
```

Companion option html: not allowed (interactive)

## `q-diff`

Use when showing a code change for review, optionally with comments attached to specific new-side lines.

### Attributes

This element takes no attributes of its own.

### Children

A `<pre>` of unified diff text, followed by zero or more q-diff-note children. Each note names a file and a new-side line number that must appear in the diff. Code lines are highlighted by each file's extension. Without JavaScript the raw diff shows, then the notes as a list.

### Example

```html
<q-diff>
  <pre>--- a/src/retry.py
+++ b/src/retry.py
@@ -10,6 +10,7 @@ def fetch(url):
     attempt = 0
-    while attempt &lt; 3:
+    while attempt &lt; MAX_ATTEMPTS:
         try:
             return get(url)
         except Timeout:
+            sleep(backoff(attempt))
             attempt += 1</pre>
  <q-diff-note file="src/retry.py" line="11">The limit moves into a named constant so tests can lower it.</q-diff-note>
  <q-diff-note file="src/retry.py" line="15">Backoff runs before the counter changes, so the first retry waits the base delay.</q-diff-note>
</q-diff>
```

Companion option html: allowed

## `q-diff-note`

Use when attaching a review comment to a specific new-side line inside a q-diff.

Must be a child of `q-diff`.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `file` | yes | text | - | - | Path as in the diff's +++ header, with the b/ prefix removed. |
| `line` | yes | integer | - | - | New-side line number the note sits under. |

### Children

Free text: the comment itself.

### Example

```html
<q-diff>
  <pre>--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 # Project
+Run `make test` before opening a pull request.
 Setup notes follow.</pre>
  <q-diff-note file="README.md" line="2">Name the exact command so contributors do not guess.</q-diff-note>
</q-diff>
```

Companion option html: allowed

## `q-board`

Use when the reader should sort cards into columns, such as triage, prioritizing or planning, and hand the result back as Markdown.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `id` | yes | ident | - | - | Board identifier; the saved layout is keyed by it. |

### Children

Direct-child `<section>` elements, each opening with an h2 to h6 heading and then a `<ul>` of `<li>` cards. A card's identity is its data-id attribute, or else its trimmed text.

### Example

```html
<q-board id="triage">
  <section>
    <h3>Now</h3>
    <ul>
      <li data-id="login-bug">Fix login redirect loop</li>
      <li data-id="slow-search">Profile slow search queries</li>
    </ul>
  </section>
  <section>
    <h3>Next</h3>
    <ul>
      <li data-id="csv-export">Add CSV export to reports</li>
    </ul>
  </section>
  <section>
    <h3>Later</h3>
    <ul>
      <li data-id="dark-mode-icons">Redraw icons for dark mode</li>
    </ul>
  </section>
</q-board>
```

Companion option html: not allowed (interactive)

## `q-grid`

Use when several panels, stats or figures should sit side by side and stack on narrow screens, as on a dashboard.

### Attributes

This element takes no attributes of its own.

### Children

Any block children, usually q-panel or q-stat elements. They flow into equal columns: 1 at 700px and below, up to 2 from 701px, up to 4 from 1100px and up to 6 from 1800px (viewport widths). Give a child span="2" (q-panel) or data-span="2" (anything else) to take that many columns; a span never exceeds the columns in the row.

### Example

```html
<q-grid>
  <q-panel span="2">
    <h3>Checkout latency</h3>
    <p>The p95 fell from 410 ms to 310 ms after the cache change.</p>
  </q-panel>
  <q-panel>
    <h3>Error rate</h3>
    <p>3.1% of attempts failed in the last 7 days.</p>
  </q-panel>
  <q-panel>
    <h3>Open incidents</h3>
    <p>None.</p>
  </q-panel>
</q-grid>
```

Companion option html: allowed

## `q-panel`

Use when one dashboard item, such as a chart, a table or a few stats, needs a title and a border of its own.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `span` | no | enum | `1`, `2`, `3`, `4`, `full` | `1` | How many columns of an enclosing q-grid the panel spans; full takes the whole row. |

### Children

A heading (h2, h3 or h4) first: it is the panel's title. The body follows: paragraphs, q-chart, q-table, q-stat or any other content.

### Example

```html
<q-panel>
  <h3>Weekly active users</h3>
  <p>58,200 distinct signed-in users in the last ISO week, up 11.5%.</p>
</q-panel>
```

Companion option html: allowed

## `q-sidenote`

Use when a short aside, source or caveat explains a phrase without interrupting the sentence.

### Attributes

This element takes no attributes of its own.

### Children

The words being annotated, then one child marked slot="note" holding the note. The words are highlighted, and the note opens below them while a mouse hovers them or they have keyboard focus; a tap or click keeps it open. Without JavaScript, and in print, the note reads inline in parentheses after the words.

### Example

```html
<p>Median build time fell to <q-sidenote>nine minutes<span slot="note">Measured on the main branch, excluding reruns.</span></q-sidenote> after the cache moved to the shared runner.</p>
```

Companion option html: not allowed (interactive)

## `q-compare`

Use when two or more options are judged against the same criteria and one of them is recommended.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `recommended` | yes | integer | - | - | The recommended option, counted from 1 across the option columns (the criteria column is not counted). |

### Children

A `<table>` whose first row is the header: the first cell names the criteria column and each other header cell is one option. Every later row is one criterion, with its name in the first cell. At 700px and below each option becomes its own block, the recommended one first. Wider, the table widens past the page column when the options do not fit and nothing sits beside the column; beside a nav rail or pane it scrolls inside its own box. Without JavaScript the table scrolls inside its own box.

### Example

```html
<q-compare recommended="2">
  <table>
    <thead>
      <tr><th>Criterion</th><th>Self-host</th><th>Managed</th><th>Hybrid</th></tr>
    </thead>
    <tbody>
      <tr><th>Monthly cost</th><td>$900</td><td>$2,400</td><td>$1,500</td></tr>
      <tr><th>Setup time</th><td>3 weeks</td><td>2 days</td><td>1 week</td></tr>
      <tr><th>On-call load</th><td>High</td><td>Low</td><td>Medium</td></tr>
    </tbody>
  </table>
</q-compare>
```

Companion option html: not allowed (interactive)

## `q-flow`

Use when a system, pipeline or architecture has paths, groups or node details the reader will pan, zoom and click through to explore, and for any flowchart on an HTML page, including decisions, retries and sub-processes.

### Attributes

| Name | Required | Kind | Values | Default | Description |
|---|---|---|---|---|---|
| `summary` | yes | text | - | - | One sentence stating what the graph shows; it becomes the graph's accessible label. |
| `direction` | no | enum | `right`, `down` | `right` | Flow direction: left to right or top to bottom. |
| `groups` | no | enum | `panels`, `lanes` | `panels` | How top-level groups are drawn: tinted panels or stage bands across the flow. |

### Children

A `<script type="application/json">` child holding the graph data: optional kinds (mapping each kind name to a chart color 1 to 8), optional groups (id, label, optional parent), required nodes (id, label, optional kind, group and short HTML detail, optional shape of box, decision or subprocess, and for a subprocess an optional flow naming the id of another q-flow on the page), and optional edges (from, to, optional label, async boolean and loop boolean for a return edge, and an optional id used only by a trace step's via). Optional traces let the reader step through what happens to one value as it moves through the flow: each trace has an id, a label and steps (at least 2), and each step has a node, a value (the whole value as it leaves that node, trimmed to the fields the reader needs), an optional note, and an optional via naming an edge id when several edges join the two steps. Consecutive steps must be joined by an edge. A decision labels every exit with its answer. Never write coordinates; the element lays the graph out and builds a "Graph as a list" disclosure below the canvas.

### Example

```html
<q-flow summary="Orders flow from checkout through billing to the ledger, and a failed charge retries until it succeeds or is given up." direction="right" groups="panels">
  <script type="application/json">
  {
    "kinds": {"ui": 1, "worker": 2, "database": 3, "queue": 4},
    "groups": [
      {"id": "billing", "label": "Billing"}
    ],
    "nodes": [
      {"id": "checkout", "label": "Checkout", "kind": "ui"},
      {"id": "charge", "label": "Charge worker", "kind": "worker", "group": "billing", "detail": "<p>Retries 3x with exponential backoff, then dead-letters.</p>"},
      {"id": "paid", "label": "Charge settled?", "shape": "decision", "group": "billing"},
      {"id": "ledger", "label": "Ledger", "kind": "database", "group": "billing"},
      {"id": "retries", "label": "Retry queue", "kind": "queue", "group": "billing"}
    ],
    "edges": [
      {"from": "checkout", "to": "charge", "label": "order.created", "async": true},
      {"from": "charge", "to": "paid"},
      {"from": "paid", "to": "ledger", "label": "Yes"},
      {"from": "paid", "to": "retries", "label": "No", "async": true},
      {"from": "retries", "to": "charge", "label": "wait doubles", "loop": true}
    ],
    "traces": [
      {"id": "settles", "label": "Charge settles", "steps": [
        {"node": "checkout", "value": {"order": "A-17", "total": 42}, "note": "The order is placed."},
        {"node": "charge", "value": {"order": "A-17", "attempt": 1}, "note": "The worker calls the provider."},
        {"node": "paid", "value": {"order": "A-17", "settled": true}, "note": "The provider says yes."},
        {"node": "ledger", "value": {"order": "A-17", "status": "paid"}, "note": "The ledger records the payment."}
      ]}
    ]
  }
  </script>
</q-flow>
```

Companion option html: not allowed (interactive)
