# Bidirectional Brainstorming

<p class="lead mb-1">Make a browser <strong>Proceed</strong> button advance Claude — with no typing in the terminal.</p>

<p class="text-muted">Spec · 2026-06-09 · Approved for Phase 1 · designed on Agent Isles, brainstorming its own successor.</p>

---

## The idea in one picture

Today the loop only goes one way: Claude shows you a screen, but **you have to type in the terminal** to move forward. The browser displays the work; it can't drive it. We want the click itself to be the "go" signal.

<div class="row g-4 align-items-stretch">
<div class="col-md-6">
<div class="card h-100 border-secondary">
<div class="card-header bg-secondary-subtle fw-semibold">Today — half bidirectional</div>
<div class="card-body">
<ol class="mb-0 ps-3">
<li class="mb-2">Claude renders a screen, then <strong>ends its turn</strong></li>
<li class="mb-2">You click an option <span class="text-muted">(saved to a file)</span></li>
<li class="mb-2 text-danger fw-semibold">⌨️ You type in the terminal to continue</li>
<li>Claude wakes up and proceeds</li>
</ol>
</div>
</div>
</div>
<div class="col-md-6">
<div class="card h-100 border-success">
<div class="card-header bg-success-subtle fw-semibold">After — fully bidirectional</div>
<div class="card-body">
<ol class="mb-0 ps-3">
<li class="mb-2">Claude renders a screen with a <strong>Proceed</strong> button</li>
<li class="mb-2">You make your choice</li>
<li class="text-success fw-semibold">⚡ You click <strong>Proceed →</strong> and Claude continues</li>
</ol>
<p class="text-success small mt-3 mb-0">The terminal step is gone.</p>
</div>
</div>
</div>
</div>

---

## What we're building

Three small pieces. Two live in **Agent Isles** vs **Quirk**, split along a clean line: Agent Isles *shows* the button; Quirk *waits* for the click.

<div class="row g-3">
<div class="col-md-4">
<div class="card h-100">
<div class="card-body">
<span class="badge text-bg-primary mb-2">Agent Isles</span>
<h5 class="card-title h6">1 · The Proceed button</h5>
<p class="card-text small mb-0">A new <code>&lt;agent-proceed&gt;</code> button. Greyed out until you pick something, then lights up. Clicking it writes a small "proceed" record to the events file.</p>
</div>
</div>
</div>
<div class="col-md-4">
<div class="card h-100">
<div class="card-body">
<span class="badge text-bg-dark mb-2">Quirk</span>
<h5 class="card-title h6">2 · The <code>wait</code> command</h5>
<p class="card-text small mb-0">A bridge command that pauses Claude, watching the events file. The moment a "proceed" record lands, it hands Claude your choice and the turn continues.</p>
</div>
</div>
</div>
<div class="col-md-4">
<div class="card h-100">
<div class="card-body">
<span class="badge text-bg-dark mb-2">Quirk</span>
<h5 class="card-title h6">3 · The updated loop</h5>
<p class="card-text small mb-0">Document the tighter rhythm in the companion guide: <em>render a screen → <code>wait</code> → continue</em>, instead of "ask the user to type to advance".</p>
</div>
</div>
</div>
</div>

<div class="alert alert-light border mt-3 mb-0">
<strong>The one thing that connects them</strong> is the record the button writes — the same shape whether a file or a live channel delivers it:
<pre class="mb-0 mt-2"><code>{ "type": "proceed", "choice": null, "text": "Proceed →", "timestamp": 1781003090, "selected": ["two-column"] }</code></pre>
</div>

---

## How it ships: two phases

<div class="row g-4">
<div class="col-md-6">
<div class="card h-100 border-success">
<div class="card-header bg-success-subtle fw-semibold">Phase 1 — now · blocking wait</div>
<div class="card-body">
<ul class="mb-0 ps-3">
<li class="mb-1">Ships today, <strong>zero new dependencies</strong></li>
<li class="mb-1">Reuses the events file we already write</li>
<li class="mb-0 text-muted">Trade-off: Claude stays "awake" holding the <code>wait</code> — fine for short, interactive waits</li>
</ul>
</div>
</div>
</div>
<div class="col-md-6">
<div class="card h-100">
<div class="card-header fw-semibold">Phase 2 — later · channels</div>
<div class="card-body">
<ul class="mb-0 ps-3">
<li class="mb-1">Swap the file-watching for a native Claude Code <strong>channel</strong></li>
<li class="mb-1">Claude truly <strong>sleeps</strong> and the click wakes it; two-way (replies, browser approvals)</li>
<li class="mb-0 text-muted">Same "proceed" record — it's a transport swap, not a redesign</li>
</ul>
</div>
</div>
</div>
</div>

---

## Decisions, briefly

| Question | What we chose | Instead of |
|---|---|---|
| How does a click wake Claude? | **Phased** — blocking wait now, channels later | self-polling loop · custom hook |
| What fires "go"? | A **dedicated Proceed button** | auto-advancing on any click |
| Where does the button live? | **Agent Isles** (it renders the UI) | — |
| Where does the waiting live? | **Quirk** (it owns the loop + future channel) | an `isles wait` command |

Why the split: the wait is the seam that a channel will later replace — that's a Claude Code concern, not a rendering one. And it only reads the events file, which Quirk already reads every turn, so it adds no new coupling.

A `<quirk-proceed>` **pack** component was considered and rejected — but on honest grounds: now that the live client forwards `agent-isles:proceed` and the server promotes `type:"proceed"`, a pack *could* emit a clean proceed record (no sentinel hack, and `isles live` can load a pack via an `isles.config.json` in the screen dir). The real reason it lives in core is that "advance/commit on click" is a **general** live-agent primitive — any Agent Isles host wants it — and keeping the event contract, its emitter, and the sanitizer allowlist in one reviewed repo beats splitting the component from the plumbing it depends on.

---

## Risks & open questions

<div class="row g-3">
<div class="col-md-6">
<div class="card h-100 border-warning">
<div class="card-body">
<h6 class="card-title">Watch out for</h6>
<ul class="small mb-0 ps-3">
<li class="mb-1"><strong>Channels are preview-only</strong> (Phase 2): need a launch flag and a live session. Contained to later.</li>
<li class="mb-0"><strong>Blocking wait holds the turn</strong> — wasteful for long waits; Phase 2 fixes it.</li>
</ul>
</div>
</div>
</div>
<div class="col-md-6">
<div class="card h-100 border-success">
<div class="card-body">
<h6 class="card-title">Resolved in build (post-review)</h6>
<ul class="small mb-0 ps-3">
<li class="mb-1"><strong>Timeout</strong>: <code>wait</code> defaults to 110s (under the Bash-tool 120s limit) → clean exit-1 + re-run, not a tool kill.</li>
<li class="mb-1"><strong>Stale events</strong>: <code>wait</code> baselines at start and resets on file-clear, so a leftover proceed can't false-advance even if the server's clear fails.</li>
<li class="mb-0"><strong>Signal auth</strong>: POST/WS reject cross-origin browser requests; <code>selected</code>/<code>text</code> clamped — a hostile page can't wake or inject the agent.</li>
</ul>
</div>
</div>
</div>
</div>

---

<p class="text-muted small">Full decision history and the design screens live in <code>.quirk/brainstorm/successor-design/</code>.</p>
