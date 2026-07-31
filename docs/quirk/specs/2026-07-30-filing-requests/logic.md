# filing-requests — Logic Spec

## Purpose

A quirk skill that runs a guided, evidence-gathering session about a request the user wants to
file — a bug report, a feature request, or a code-change request — and emits a terse, provenance-
marked artifact as markdown and, on explicit confirmation, as a GitHub issue.

It exists because the fields developers most need are the ones reporters most often omit, and
because a coding agent can establish several of them by reading the repository instead of asking.
Its first version covers the session, the markdown artifact, and GitHub filing; GitLab and Jira
projections are deferred.

## Conceptual model

**An evidence-gathering interview that writes short.**

The skill inverts the usual issue-template trade-off. A web form can only ask, so it asks for
everything, and reporters abandon it. A coding agent can *look* — so `filing-requests` spends
inspection budget to buy back question budget, and spends the questions it saves on what only the
human knows. The artifact it emits is deliberately terse, because length is the tell that gets
AI-authored issues discarded.

Two research findings define the problem it solves, and they pull in opposite directions:

1. Developers value steps to reproduce, stack traces, and test cases most, and those are exactly
   what reporters omit — the *information mismatch* (Bettenburg/Zimmermann). This argues for
   asking more.
2. Padded prose and invented specificity are the signature markers of AI-authored issues, and
   maintainers now reject on sight. This argues for writing less, and asserting less.

The resolution is that **completeness and length are separable**. The skill is thorough about
fields and miserly about words. Every field is either established, or explicitly marked missing
with a reason — never quietly filled with something plausible.

### Three stages

**Orient.** Establish ground: which repo, whether the user can write to it, whether it has issue
templates, and what depth of inspection is permitted. Infer the request type from the user's
opening description and confirm it — folding the depth choice into that same question, so
orientation costs exactly one turn. If the evidence says this should not be filed at all, say so
with reasoning; the user may override.

**Establish.** Determine the field set (repo template if present, else per-type core schema).
Before asking the user anything, try to answer it from the repo. Ask only what inspection cannot
settle. Surface contradictions with a citation and let the user resolve them. Surface type drift
and offer to switch, carrying existing answers onto the new schema. Once the core fields are
populated, draft and show the artifact; from there the visible draft drives the remaining
questions.

**Emit.** Scan for secrets and block until acknowledged. Write the markdown artifact
unconditionally. File to GitHub only on a separate, explicit confirmation.

### The canonical form is the spine

Between Establish and Emit sits an explicit JSON representation. Its defining property: **every
field carries its provenance.**

```json
{
  "type": "bug",
  "title": "Export fails with UnicodeDecodeError on reports containing em-dashes",
  "target": { "kind": "github", "repo": "acme/reports", "writable": true, "third_party": false },
  "fields": [
    {
      "name": "steps_to_reproduce",
      "value": "1. Create a report with an em-dash in the title\n2. Click Export as PDF",
      "provenance": "reported"
    },
    {
      "name": "environment",
      "value": "reports 2.4.1, Python 3.11.6",
      "provenance": "observed",
      "source": "poetry.lock, pyproject.toml"
    },
    {
      "name": "root_cause",
      "value": "the traceback terminates in src/export.py:142, which opens without an encoding argument",
      "provenance": "inferred"
    },
    {
      "name": "frequency",
      "provenance": "missing",
      "reason": "intermittent; observed 3x over two weeks with no identified trigger"
    }
  ],
  "proposed_solution": { "value": "pass encoding='utf-8'", "attributed_to": "reporter" },
  "verified_against": ["src/export.py:142", "poetry.lock", "git log since v2.3.0"],
  "disclosure_required": false
}
```

Four locked decisions fall out of this structure mechanically rather than depending on model
discipline:

- **Assertion rules.** The renderer states `observed` and `reported` plainly, hedges `inferred`,
  and prints `missing` with its reason. Invented specificity has nowhere to enter, because a field
  with no provenance cannot render.
- **The "verified against" line.** Assembled from `observed` sources, not written freehand.
- **Per-claim voice.** Provenance markers come from data, so one clean report voice stays honest.
- **Projection.** Markdown, and later GitLab and Jira, are pure functions of this structure.
  Fixture JSON in, expected output asserted, no model in the test.

### Negative observation

Inspection can establish that something is **absent**, and that is a first-class `observed`
result, not a failure to resolve. "No handler for PDF export exists under `src/export/`" is a
verified fact with a citable source, and for feature requests it is the *primary* thing inspection
produces. A negative observation records what was searched as its source, so a reader can judge
the search's adequacy:

```json
{
  "name": "current_behavior",
  "value": "no PDF export path exists; `src/export/` implements CSV and JSON only",
  "provenance": "observed",
  "source": "src/export/__init__.py, grep -r 'pdf' src/ (no matches)",
  "polarity": "negative"
}
```

This matters because it is the guard against the documented failure of agents proposing things a
project already has or already rejected. A feature request whose `current_behavior` field is a
negative observation has been checked; one where it is `reported` has not.

### Per-type field cores

Absent a repo template, each type has a required core and a set of optionals. These are named here
rather than deferred, because they are product decisions, not implementation detail.
`reference/field-catalogs.md` holds the question wording and the per-field inspection strategy;
the cores themselves are fixed by this spec.

**Bug** — core: `current_behavior`, `expected_behavior`, `steps_to_reproduce`, `environment`.
Optional: `stack_trace`, `frequency`, `regression_range`, `workaround`.
Inspection typically resolves `environment` and often `regression_range`; the rest are usually
`reported`.

**Feature** — core: `problem`, `who_benefits`, `current_behavior`, `acceptance_criteria`.
Optional: `value_or_impact`, `constraints`, `out_of_scope`, `prior_art`.
`problem` is stated as a problem, not a solution — the strongest evidence-backed finding for this
type. `current_behavior` is normally a negative observation. `constraints` and `prior_art` are
partially inspectable (language version floors, architectural boundaries, whether a similar
mechanism already exists); `who_benefits` and `acceptance_criteria` are irreducibly human.

**Code-change** — core: `scope`, `why_now`, `blast_radius`.
Optional: `migration`, `rollback`, `test_plan`, `perf_impact`.
`scope` and `blast_radius` are substantially inspectable — the affected modules and their callers
are discoverable — which makes this the type where inspection buys the most question budget.

A worked feature-request canonical form, for contrast with the bug example above:

```json
{
  "type": "feature",
  "title": "Export reports as PDF",
  "fields": [
    {
      "name": "problem",
      "value": "finance forwards reports to auditors who reject CSV; they retype them by hand",
      "provenance": "reported"
    },
    { "name": "who_benefits", "value": "finance team, ~6 people, monthly close", "provenance": "reported" },
    {
      "name": "current_behavior",
      "value": "no PDF export path exists; `src/export/` implements CSV and JSON only",
      "provenance": "observed",
      "source": "src/export/__init__.py, grep -r 'pdf' src/ (no matches)",
      "polarity": "negative"
    },
    {
      "name": "acceptance_criteria",
      "value": "Given a report with 50+ rows, When the user exports as PDF, Then a paginated PDF downloads with the same column order as the CSV export",
      "provenance": "reported"
    },
    {
      "name": "constraints",
      "value": "must work on the 3.9 floor declared in pyproject.toml",
      "provenance": "observed",
      "source": "pyproject.toml"
    }
  ],
  "verified_against": ["src/export/__init__.py", "pyproject.toml"],
  "disclosure_required": false
}
```

## Data flow

The user invokes the skill with a description of what they want to file. The skill resolves the
target repo from the working directory, checks write access, globs for issue templates
(`.github/ISSUE_TEMPLATE/*.yml`, `.github/ISSUE_TEMPLATE/*.md`, `.gitlab/issue_templates/*.md`),
and reads `--depth` (default `read`).

It infers a request type from the description and asks one combined question: confirm the type,
and confirm the inspection depth. If its reading of the description suggests this is not a
fileable request, that judgment and its evidence go in the same turn. The non-fileable conditions
are type-shaped and run in both directions:

| Inferred type | Non-fileable conditions checked |
|---|---|
| Bug | configuration error on the reporter's side; already fixed on `main`; not actually broken — the described behavior is intended, making this a feature request |
| Feature | the capability already exists; the project explicitly rejected it previously (a `DECISIONS`/ADR entry, a documented non-goal); it is a support question about how to use what exists |
| Code-change | already done; the described state does not match the repo |

*Already exists* and *previously rejected* are the feature-side analogues of *already fixed* and
*config error*, and they address the documented failure of agents proposing work a project has
already decided against.

### Choosing among templates

The glob usually matches more than one file, so "the repo's template" needs a selection rule.
Resolution runs in this order, and stops at the first step that yields exactly one template:

1. **Discard non-templates.** `.github/ISSUE_TEMPLATE/config.yml` is GitHub's chooser
   configuration, not a template, and is never a candidate. Neither is any file whose parsed form
   has no body sections.
2. **Match the confirmed type against each candidate's declared identity** — a YAML form's `name`
   and `labels`, then its filename stem. `bug`, `defect`, `regression` match the bug type;
   `feature`, `enhancement`, `proposal`, `idea` match feature; `chore`, `task`, `refactor`,
   `maintenance` match code-change.
3. **If exactly one candidate matches, use it.** If several do, ask the user to choose, listing
   each by name and path. If none match, fall back to the per-type core and record that no
   template applied.

The fallback is not a failure mode to be avoided — a repo whose templates do not cover the
confirmed type is better served by the per-type core than by a template written for something
else. The one thing the skill must not do is pick silently among several: which template is chosen
determines the field set, so a silent pick is a silent change to what gets asked and emitted.

### Required sections in a template

Three rules apply in order, and they apply identically to YAML forms and markdown templates:

1. **The template supplies structure and ordering.** Its sections, in its order, shape the emitted
   artifact.
2. **Requiredness is the union of the template's own markings and the per-type core.** A GitHub
   YAML form declares its markings with `validations.required`, and those inputs are required.
   Markdown templates have no such mechanism, so they contribute no markings — inventing a
   convention from their formatting would be guessing at a maintainer's intent. In both cases the
   per-type core is *additive*: any core field the template omits is still gathered, and is
   appended in core order after the template's own sections. A template can add requirements; it
   cannot subtract them.
3. **The non-waivable gate is global and overrides both.** No template, of either kind, can waive
   a feature request's `problem` or `acceptance_criteria`. A YAML form that marks neither required
   does not thereby make them optional — it only declines to add requirements of its own.

The asymmetry to notice is that markdown's lack of markings is not a special case needing its own
rule; it is the empty set going into the same union. That keeps two guarantees that would
otherwise collide: the maintainer's declared structure and requirements are honored, and a feature
request still cannot ship without a stated problem and a testable criterion.

With type confirmed and the template resolved, the field set is fixed. The skill walks it. For
each field it first attempts resolution by inspection at the permitted depth; what resolves becomes
an `observed` field with its source recorded, including negative observations. What does not
resolve becomes a question to the user, and the answer becomes a `reported` field.

Two interrupts can fire during this walk. A **contradiction** — inspection disagrees with
something the user stated — is surfaced immediately with a citation, and the user's resolution
determines which value survives and with what provenance. **Type drift** — the accumulating
answers indicate a different request type — is surfaced with the evidence that changed the
picture; if the user switches, answers already given are mapped onto the new type's field set and
not re-asked.

Drift is symmetric and both directions are expected. Feature → bug fires when a request for new
behavior turns out to describe a regression against behavior that used to work. Bug → feature
fires when nothing is broken and the reporter is asking for behavior the system never had — the
more common direction, and the one maintainers most often have to re-triage by hand.

**Nothing the user supplied is ever discarded on drift.** Carry-over runs by explicit mapping,
and anything without a mapping is preserved rather than dropped:

| From (bug) | To (feature) | Why |
|---|---|---|
| `current_behavior` | `current_behavior` | same field, carried as-is |
| `steps_to_reproduce` | appended to `current_behavior` if that field already holds content, else becomes it | what the user did and saw describes how the system behaves today |
| `expected_behavior` | `acceptance_criteria`, as a `reported` draft the user must confirm | it states a desired outcome, but a criterion has to be testable and the user's phrasing may not be |
| `environment` | `constraints` | where it has to work is a constraint on the feature |

| From (feature) | To (bug) | Why |
|---|---|---|
| `current_behavior` | `current_behavior` | same field, carried as-is |
| `acceptance_criteria` | `expected_behavior` | the desired outcome becomes the expectation that was violated |
| `who_benefits` | dropped from the core, retained as an optional `affected_users` | who wants it is context for a bug, not a required field |
| `problem` | appended to `current_behavior` if that field already holds content, else becomes it | the problem statement usually describes the symptom |

**Where two source fields map to one destination, the table is applied top to bottom and the later
row appends rather than overwrites** — the destination's existing content is kept and the incoming
value is added below it, under a short lead-in naming where it came from. Ordering the identity
mapping first is what makes this deterministic: `current_behavior` lands before
`steps_to_reproduce` is appended to it, and `problem` before it is folded in on the reverse
direction.

A field with no row in the applicable table is retained as an optional field under its original
name and rendered after the new type's sections. Every carried field keeps the provenance it
already had, and `expected_behavior → acceptance_criteria` is the one mapping that re-opens a
question, because a testable criterion is a stronger claim than the phrasing it came from.

**Core fields** are the required subset of the active field set — the sections the repo's template
marks required, or, absent a template, the required core listed for that type above. A core field
is **resolved** when it holds a value with provenance `observed` or `reported`, or is marked
`missing` with a stated reason. Optional fields never gate anything.

`missing` does not carry the same weight for every field, so two core fields are **non-waivable**:
a feature request's `problem` and `acceptance_criteria`. A bug report with no reproduction steps is
still a valid report — the reason is itself diagnostic, and maintainers say they prefer an honest
"intermittent, no reliable trigger" to a fabricated recipe. A feature request with no stated
problem or no acceptance criteria is not a feature request; it is a wish, and filing it wastes the
maintainer attention this skill exists to protect.

When a non-waivable field cannot be resolved, the skill does not emit. It says which field is
unresolved and why that blocks, and offers the two honest exits: keep working on it now, or save
the partial canonical form so the session can resume later. Nothing is filed, and nothing is
fabricated to get past the gate.

Termination still holds. Every waivable core field can be resolved by marking it `missing`, and
the two non-waivable fields terminate the loop by halting it explicitly rather than by being
filled — a stop, not a spin.

Once every core field is resolved, the skill renders the canonical form to markdown and shows it.
Remaining questions are then driven by what the draft makes visibly thin or wrong.

At emission, the secret scanner runs over **every string the artifact will render** — the
`fields[]` values, and equally `title`, `proposed_solution`, the `verified_against` entries, and
the `reason` text on `missing` fields. Scanning only `fields[]` would leave the title and the reporter's
proposed fix unscanned, and both render into the emitted issue. The rule is scope-by-output: if it
can appear in the artifact, it is scanned. Matches are reported by the path that located them
(`fields[2].value`, `title`) so the user can see exactly what leaked and where. The skill will not
proceed until the user resolves each finding (redact or keep).
The markdown artifact is then written to `docs/quirk/requests/YYYY-MM-DD-<slug>.md`
unconditionally. Only then, and only on a separate confirmation that displays the exact body and
destination, does the skill shell out to `gh issue create`.

In headless mode there are no questions. Fields resolvable by inspection are populated; everything
else is marked `missing` with reason `no human in session`. The artifact carries a prominent
statement that no human confirmed it. It is never filed to a tracker automatically.

Headless is therefore viable for bug and code-change requests, whose cores are substantially
inspectable, and **not** viable for feature requests, whose two non-waivable fields are
irreducibly human. A headless feature request halts with the same non-waivable message rather than
emitting a hollow artifact. This is the correct outcome: an unattended process cannot know who
benefits or what "done" means, and a machine-generated wish is precisely the artifact maintainers
are building defenses against.

## Key decisions & rationale

**Inspection buys question budget.** This is the skill's reason to exist. Anything the repo can
answer is not asked. The information-mismatch research says the highest-value fields are the ones
reporters skip; a coding agent can often establish several of them without asking at all.

**The inspection advantage is unevenly distributed across types, and the design admits it.** For
bugs and code-changes, inspection resolves several core fields outright — environment, regression
range, affected modules and their callers. For feature requests it mostly produces *negative*
observations and constraints; `who_benefits` and `acceptance_criteria` cannot be inspected at all.
A feature-request session is therefore closer to a pure interview, and the skill's edge over a
form narrows to two things: it verifies the capability doesn't already exist and wasn't already
rejected, and it refuses to emit without a testable acceptance criterion. Those are worth having,
but they are a different kind of value than the bug path delivers, and the spec does not pretend
otherwise.

**Provenance is structural, not stylistic.** Making provenance a required property of every field
converts the anti-slop guardrails from instructions the model might follow into invariants the
renderer enforces. This is the single most important design choice in the spec.

**The file is unconditional; the filing is not.** Filing is outward-facing and effectively
irreversible — a deleted issue has already notified every watcher. The markdown artifact costs
nothing and preserves the session's work even when filing is impossible or declined.

**The skill inspects the code, not the tracker.** "Already fixed on main" is a repo question and
is in scope. "Is this a duplicate of #410" is a tracker question and is out. This boundary keeps
the integration surface small and avoids the documented false-duplicate failure mode.

**Deterministic work goes in Python.** Secret scanning and template parsing have correct answers
and must be testable. Model judgment on "did it notice the AWS key" has no pytest assertion.

**No question cap, despite the abandonment research.** This is a deliberate divergence and needs
its reasoning on record. The 5–10%-per-field abandonment figure measures anonymous web forms
filled by drive-by reporters; that is not this population. A user who invokes a skill has already
opted in, and can stop at any point with the artifact-so-far intact. The draft-then-refine loop
also supplies a stopping rule the raw research does not model: questions run until the *draft* is
complete, and a visible draft makes "complete" concrete rather than open-ended. The residual risk
is real — a long session on a complex bug may still be abandoned — and the mitigation is that
inspection removes questions before they are ever asked, so the count falls without the ceiling.

**It is a sibling of `brainstorming`, not a subordinate.** `brainstorming` fires on "build/
implement X" and terminates in an execution skill. `filing-requests` fires on "file/report/write
up X" and terminates in an artifact. Both descriptions must disambiguate explicitly, or both will
trigger on "I want a feature that…".

## Behavior & scenarios

**Ordinary bug report, repo present, template exists.** The skill reads the repo's bug template,
adopts its sections, resolves environment from lockfiles and the failing line from the traceback,
and asks the user only for the reproduction steps and the expected behavior. Draft appears after
those two answers. The user corrects one detail. Artifact written; user confirms; issue filed.

**Ordinary feature request.** The user wants PDF export. The skill greps for an existing
implementation, finds none, and records `current_behavior` as a negative observation citing what
it searched. It reads `pyproject.toml` and records the 3.9 floor as an `observed` constraint. It
then asks the three things it cannot know: what problem this solves, who it affects, and what
"done" looks like. The user's first answer to the last one is "it should export PDFs" — a
restatement, not a criterion — so the skill asks for a concrete pass/fail and gets a
Given/When/Then. Draft appears; the user adds a note about column ordering. Filed.

**The request is not fileable.** The user describes what is actually a configuration error on
their side. The skill states this with the evidence and points to the relevant docs. If the user
disagrees and wants it filed anyway, the session continues and the artifact is produced.

**The feature already exists.** The user asks for CSV export scoped to a date range. Inspection
finds the `--since` / `--until` flags already implemented and documented. The skill says so with
the file and the doc reference, and the session ends as a support answer rather than an issue.
The user can override, and if they do, the artifact leads with the existing capability so the
maintainer sees immediately what the request is actually asking to change.

**The feature was previously rejected.** Inspection finds an ADR under `docs/adr/` recording that
plugin-based exporters were considered and declined. The skill surfaces the decision and its
stated reasoning before any fields are gathered. A request that proceeds anyway is filed with that
prior decision cited — which reframes it from a proposal into a request to revisit, and is the
difference between engaging with a project's history and ignoring it.

**Bug → feature drift.** The user files "export is broken — it won't produce PDFs." Inspection
establishes that PDF export was never implemented; nothing is broken. The skill surfaces this,
offers to switch to the feature schema, and carries the reproduction steps over into
`current_behavior` rather than dropping them. The user's original framing is preserved in the
record, but the artifact files as what it actually is.

**Feature request blocked on a non-waivable field.** The user wants "better search" and cannot
articulate what "better" would mean concretely — every attempt restates the wish. The skill does
not emit. It names `acceptance_criteria` as unresolved, explains that a feature request without a
pass/fail condition cannot be acted on, and offers to save the partial canonical form to resume
later. Nothing is filed and nothing is invented to clear the gate.

**Inspection contradicts the user.** The user says the crash is in the auth layer; the traceback
terminates in the serializer. The skill shows both with `file:line` and asks. If the user holds
their position, their claim ships as `reported` and the contradicting observation is not silently
discarded — it appears as an `observed` field alongside it.

**Feature → bug drift.** The user opens with a feature request; the answers describe a production
regression against behavior that used to work. The skill names the evidence, offers to switch to
the bug schema, and carries the answers over. The user may decline and stay on the feature-request
track.

**Unobtainable field.** An intermittent race condition with no reliable trigger. The reproduction
section is emitted as `missing` with the reason stated, including how often it was observed and
over what period — which is itself diagnostic.

**Secret found at emission.** The pasted stack trace contains a connection string. The skill names
the field and the match, and refuses to write or file until the user chooses to redact or keep.

**No write access.** Detected during Orient. The skill says so before the session starts, and
completes it anyway; the markdown artifact is fully usable for pasting into the web UI.

**Headless from CI.** A test failure triggers the skill with no human. Environment, failing test,
and traceback are resolved by inspection; expected behavior and business impact are marked
`missing — no human in session`. The artifact is written and left for a human.

## Scope & non-goals

### In scope for v1

- The guided session, all three request types, with type inference and mid-session drift handling
- Repo issue-template detection and conformance (GitHub and GitLab template formats)
- Repo inspection at three depths (`none` / `read` / `run`)
- The canonical JSON representation with per-field provenance, including negative observations
- Per-type required cores, and the non-waivable gate on feature requests
- Markdown projection and artifact write to `docs/quirk/requests/`
- Secret scanning over canonical fields, blocking on findings
- GitHub filing via `gh`, on separate explicit confirmation
- Headless degraded mode
- pytest coverage of the deterministic layers (template parsing, secret scan, projection)

### Explicit non-goals

- **Duplicate detection.** Knowingly accepted trade-off, not an oversight. The anti-pattern
  research recommends duplicate checking, but its own strongest cautionary case is an AI triage
  bot that created self-reinforcing false-duplicate chains and locked issues against appeal. The
  failure mode of doing this badly is better documented than the cost of skipping it.
- **Any triage automation** — no labeling, closing, prioritizing, or duplicate-marking.
- **Credential custody.** The skill never prompts for, stores, or transmits a token.
- **Multi-target emission.** One target per session.
- **Splitting scope-spanning requests** into multiple artifacts.
- **PR authoring.** This skill files requests; it does not implement them.
- **Round-trip drift fidelity.** The two carry-over tables are deliberately lossy in one
  direction, and drifting back does not undo them. Bug → feature folds `steps_to_reproduce` into
  `current_behavior` and renames `environment` to `constraints`; feature → bug has no rows that
  split them back out, so a bug → feature → bug round trip leaves both unresolved and the skill
  asks for them again. Nothing is *discarded* — the content is visible in the fields it merged
  into — but the answers no longer sit where the bug field set looks for them. Adding inverse
  rows was considered and rejected: `append_or_become` merges two fields into one string, so any
  reverse row would have to re-split prose by guessing where the boundary was, which is exactly
  the invented specificity the whole design exists to prevent. Round trips are rare (drift fires
  on evidence, and evidence rarely reverses twice), and the honest cost of re-asking is smaller
  than the cost of a fabricated split.

### Deferred to later versions

- GitLab projection (via `glab`)
- Jira projection, including `createmeta` query for required custom fields
- Re-projecting an existing canonical artifact to a second tracker with cross-links
- Optional local persistence of the session trail (questions asked, reclassifications, resolved
  contradictions)

## Decisions Locked

**classification-gate**

- Non-fileable requests are flagged with reasoning; the user may override and file anyway
- Duplicate checking is out of scope entirely
- Non-fileable conditions are type-shaped: bug (config error, already fixed, not actually broken);
  feature (already exists, previously rejected, support question); code-change (already done)
- Request type is inferred from the description, then confirmed before branching
- Type drift is surfaced with evidence and runs in both directions; on switch, existing answers
  carry over by an explicit per-direction mapping table, nothing the user supplied is discarded,
  unmapped fields are retained as optionals under their original names, and only
  `expected_behavior → acceptance_criteria` re-opens a question

**evidence-authority**

- Investigation depth is a per-session dial: `none` / `read` (default) / `run`
- Contradictions between inspection and user claims are shown with a citation; the user resolves
- Only `observed` and `reported` values are asserted as fact; `inferred` is hedged and labeled;
  `missing` is marked with its reason and never filled speculatively
- One neutral report voice, with provenance carried per claim

**session-economics**

- The depth dial is folded into the type-confirmation question, costing no extra turn
- No cap on question count; the session runs until the draft is complete
- A draft appears once core fields are populated, and drives the remaining questions
- Headless mode is supported, degraded, and visibly marked as unconfirmed — for bug and
  code-change requests only; a headless feature request halts on its non-waivable fields

**artifact-structure**

- An existing repo issue template is detected and conformed to; among several candidates the skill
  discards non-templates (`config.yml`), matches the confirmed type against each candidate's name,
  labels, and filename stem, asks the user when more than one still matches, and falls back to the
  per-type core when none do — it never picks silently
- A template supplies structure and ordering; requiredness is the **union** of the template's own
  markings (a YAML form's `validations.required`; markdown contributes none) and the per-type core,
  so a template can add requirements but never subtract them, and core fields the template omits
  are appended in core order. The non-waivable gate is global and overrides both — no template of
  either kind can waive a feature request's `problem` or `acceptance_criteria`
- Absent a template: required core plus optional extras, with empty sections pruned
- Unobtainable fields are emitted as sections marked missing, with the reason — except the two
  non-waivable fields (a feature request's `problem` and `acceptance_criteria`), which halt
  emission instead
- Per-type required cores are fixed by this spec: bug (`current_behavior`, `expected_behavior`,
  `steps_to_reproduce`, `environment`), feature (`problem`, `who_benefits`, `current_behavior`,
  `acceptance_criteria`), code-change (`scope`, `why_now`, `blast_radius`)
- Three request types; anything else uses the nearest schema and states its nature in prose

**tone-and-length**

- Terse by default with a soft per-type ceiling; overflow cuts narrative, never fields. The
  ceiling is per-type because the types are not the same shape: a bug report is short because its
  evidence is short, while a feature request's acceptance criteria may legitimately run to several
  Given/When/Then clauses. Acceptance criteria and reproduction steps are exempt from the ceiling
  entirely — they are the payload, and trimming them to hit a length target inverts the purpose
- Evidential register — structure over narrative, evidence adjacent to claims
- The problem stays primary; a reporter's proposed fix is included as a marked, open suggestion
- Symptom-first specific title, drafted by the skill, overridable by the user

**provenance-and-safety**

- AI-assistance disclosure appears when the target is public or third-party; when visibility or
  ownership cannot be determined confidently, the skill discloses
- Secrets are scanned for across every string that renders into the artifact — not only `fields[]`
  but `title`, `proposed_solution`, `verified_against`, and `missing` reasons — reported by the
  path that located them; emission blocks until acknowledged
- The artifact carries conclusions only; the session trail may optionally be saved locally
- A brief "verified against" line names what was actually checked

**data-mapping**

- A canonical intermediate is projected per tracker; the target may change late in the session
- Jira (deferred) queries `createmeta` and asks only for required fields still unfilled
- Only structurally required metadata is set (issue type); labels and priority are proposed, not
  applied
- One target per session; a cheap re-projection is offered for a second

**emission-and-auth**

- The markdown artifact is always written; tracker filing requires separate explicit confirmation
- Authentication delegates to already-authenticated `gh` / `glab` / an environment token
- Absent write access, this is detected and stated during Orient; the session still completes
- Default artifact path is `docs/quirk/requests/YYYY-MM-DD-<slug>.md`

**Skill-level**

- Name: `filing-requests`, following quirk's gerund convention
- Architecture: SKILL.md flow + `reference/` catalogs + stdlib-only `scripts/` + canonical JSON
- Sibling of `brainstorming`, with deliberately disjoint trigger phrasing
- v1 ships the session, markdown, and GitHub filing

## Industry Insights

**Evidence-backed (peer-reviewed).**

- The *information mismatch*: developers rate steps to reproduce, stack traces, and test cases
  most valuable; reporters most often omit exactly those. Bettenburg et al., "What Makes a Good
  Bug Report?", FSE 2008 (n = 466 developers across Apache, Eclipse, Mozilla); extended in IEEE
  TSE Vol. 36 No. 5, 2010. <https://dl.acm.org/doi/10.1145/1453101.1453146>
- Eleven distinct factors drive bug reports to non-reproducibility; poor reproduction steps drive
  disproportionate manual triage effort. ACM SIGSOFT 2019.
  <https://arxiv.org/pdf/1906.07107>
- Report quality has a statistically significant effect on time-to-resolution in roughly 33% of
  projects studied. Springer Empirical Software Engineering, 2020.
  <https://link.springer.com/article/10.1007/s10664-020-09882-z>

**Practitioner consensus.**

- Feature-request quality hinges on stating the problem before the solution, with testable
  acceptance criteria (Given/When/Then) written before development. Atlassian, AltexSoft,
  Tricentis. INVEST criteria (Wake) for story quality.
- Field-count guidance: roughly 2–3 fields for a docs issue, 6–8 for a bug; proportional template
  sizing. <https://tenthirtyam.org/dispatches/2026/04/23/how-to-write-effective-github-issue-templates/>
- Form abandonment averages ~67%, with each required field beyond three costing an estimated
  5–10% of completions. Sourced to form-analytics industry reporting, not to software-engineering
  research — see the caveat below.
- The frequently quoted "83% of developers value steps to reproduce vs. 8% for build information"
  traces to a practitioner blog, **not** to the Bettenburg/Zimmermann paper. The qualitative
  ranking is well supported; the specific percentages should not be cited as study-backed.

**Maintainer sentiment on AI-authored issues (2024–2026).**

- curl ended a six-year, $86k bug-bounty program in early 2026 after roughly 20% of submissions
  became AI-generated reports describing vulnerabilities that did not exist; Stenberg estimated
  ~$150 of volunteer triage cost per spurious report.
  <https://www.bleepingcomputer.com/news/security/curl-ending-bug-bounty-program-after-flood-of-ai-slop-reports/>
- Documented red flags for AI-authored issues: invented specificity (version matrices or
  environments the author never observed), confident claims outrunning evidence, padded prose,
  prescriptive solutions that ignore project context, and undisclosed LLM authorship.
- Over-automation failure: an AI triage bot in the `anthropics/claude-code` repository created
  self-reinforcing false-duplicate closure chains and locked issues after 7 days, preventing
  appeal. <https://github.com/anthropics/claude-code/issues/35923> This case directly motivates
  the no-triage-automation and no-duplicate-detection non-goals.
- Kubernetes documented comparable friction from auto-closing stale issues.
  <https://github.com/kubernetes/kubernetes/issues/103151>

**Sourcing caveat.** Research was gathered by two parallel web-research agents. Peer-reviewed
citations above were checked against their primary venues. Several 2026-dated industry claims
(monthly AI-PR volumes, GitHub's pull-request kill switch, curl's precise shutdown dates) come
from single secondary sources and are recorded here as directional context, not as load-bearing
facts. No design decision in this spec rests solely on an unverified figure.

## Deferred Ideas

The session stayed within scope; no scope creep was captured by the guard. The items below were
raised during divergent discovery and deliberately set aside rather than absorbed:

- **Recording the brainstorm journey inline in the artifact** — valuable for future archaeology,
  rejected as incompatible with the terseness principle. Preserved as an optional local file
  instead.
- **Auto-splitting scope-spanning requests** into multiple cross-linked artifacts — correct in
  principle, but a wrong split yields two half-issues worse than one whole one.
- **Mirroring register from the repo's existing issues** — adapts to local culture, but
  faithfully imitates repos whose existing issues may themselves be poor.
- **Post-filing mutation and immutability policy** — discarded during scoring: a skill cannot
  enforce tracker-side immutability, so the decision is not the skill's to make.

## Glossary

**Canonical form** — the tracker-agnostic JSON representation produced by the session, from which
all output formats are projected.

**Provenance** — the required per-field property recording how a value is known: `observed`
(established by inspection, with a source), `reported` (stated by the user), `inferred` (reasoned
to by the skill), or `missing` (unavailable, with a reason).

**Depth dial** — the per-session bound on repo inspection: `none` (no inspection), `read`
(read files, git history, lockfiles — the default), `run` (execute tests or reproduction steps).

**Information mismatch** — the empirical finding that the bug-report fields developers value most
are the ones reporters most often omit.

**Invented specificity** — asserting concrete detail (versions, environments, reproduction steps)
the author never actually observed. The failure mode the provenance system exists to prevent.

**Negative observation** — an `observed` field establishing that something is *absent*, recording
what was searched as its source. The primary product of inspection for feature requests, and the
guard against proposing what a project already has.

**Non-waivable field** — a core field that cannot be resolved by marking it `missing`. A feature
request's `problem` and `acceptance_criteria`; without them the artifact is a wish, not a request.
An unresolvable non-waivable field halts emission rather than shipping a hollow artifact.

**Projection** — rendering the canonical form into a target format (markdown, GitHub issue body,
later GitLab and Jira). A pure function of the canonical form.

**Type drift** — the mid-session discovery that the confirmed request type is wrong, given the
answers gathered since.

## Status & amendments

**Status:** Reviewed (adversarial-review rounds 1–2 closed). Tech spec: requested.

**Amendments:**

- **2026-07-30 — feature-request parity.** Review found the spec was bug-biased: six of eight
  scenarios and the sole canonical example were bug-shaped, no per-type field cores were named,
  and several rules that read as type-neutral were in fact tuned to bug reports. Closed five gaps:
  (1) per-type required cores fixed in the spec body rather than deferred to a reference file;
  (2) negative observation defined as a first-class `observed` result, with a feature-shaped
  canonical example added; (3) `problem` and `acceptance_criteria` made non-waivable, so a feature
  request cannot ship hollow via the `missing` escape — with the consequence that headless mode is
  bug and code-change only; (4) the non-fileable gate and type drift extended to both directions,
  adding *already exists* and *previously rejected* and the bug → feature transition; (5) the
  terseness ceiling made genuinely per-type, exempting acceptance criteria and reproduction steps.
  Also recorded, under Key decisions, that the inspection advantage is structurally weaker for
  feature requests rather than papering over it.

- **2026-07-30 — adversarial review round 1.** Reviewed with the `adversarial-review` skill at
  `deep` depth, profile `spec-design`, reviewer `gemini-3.1-pro-preview` (google), independence
  `full`; refute stage `gpt-5.6-sol` (openai). Verdict `NEEDS_FIXES`, 0 suppressed, 0 contested.
  Three findings survived refutation at `HIGH` and are closed here:
  - `missing-mapping-logic` (F1) — template conformance named no selection rule when a repo has
    several templates. Added an ordered resolution: discard non-templates, match the confirmed type
    against name/labels/filename, ask when ambiguous, fall back to the per-type core. Never a
    silent pick, because the choice determines the field set.
  - `undefined-contract` (F2) — "sections the template marks required" assumed a mechanism markdown
    templates lack. Split the contract: YAML `validations.required` is authoritative; markdown
    templates supply structure and ordering while the per-type core decides what is required. This
    was a collision between the template-conformance decision and the non-waivable cores, added in
    separate passes and not reconciled at the time.
  - `unhandled-state` (F3) — drift carry-over specified only `steps_to_reproduce`. Added explicit
    mapping tables for both directions, with unmapped fields retained as optionals rather than
    dropped.

  Also closed `failing-check` (F4) by adding the `Purpose` heading the section-coverage check
  requires.

  **Fixed but not adjudicated:** the secret scan was scoped to `fields[]` values while `title` and
  `proposed_solution` are top-level keys that also render into the emitted issue. Raised by a
  promote run that was discarded on a harness fault rather than refuted, so it carries no ruling;
  verified directly against the text and fixed by scoping the scan to every string that renders.
  Recorded here as unadjudicated rather than confirmed.

  **Not addressed:** 22 `unresolvable-reference` pre-pass findings blocked the verdict. They name
  the spec's own schema field names and paths it plans to create — which the `spec-design` profile
  itself classifies as "not a finding at all" — but no stage adjudicated them, so they blocked by
  default. Left standing rather than self-graded.

- **2026-07-30 — adversarial review round 2 (closure).** Bounded closure pass over the round-1 fix
  delta, same reviewer and profile, lens narrowed to re-checking the closed findings and hunting
  regressions in the delta itself. `section-coverage` verified passing. F1 and F3 held. **Two
  regressions introduced by the round-1 fixes were caught and closed:**
  - The YAML rule ("`validations.required` is authoritative: those inputs are the core fields, and
    the rest are optional") contradicted the global non-waivable guarantee, and specified an append
    behavior for markdown templates that it never stated for YAML. Replaced with three ordered
    rules applying identically to both kinds: template supplies structure; requiredness is the
    union of template markings and the per-type core, so a template can add but never subtract;
    the non-waivable gate is global and overrides both.
  - The bug → feature drift table mapped both `steps_to_reproduce` and `current_behavior` onto
    `current_behavior` with no collision rule, while the reverse table handled its `problem`
    collision. Added an explicit rule — tables apply top to bottom, later rows append rather than
    overwrite, identity mappings ordered first so the result is deterministic — and made the
    reverse table's `problem` row use the same append semantics.

  These two were raised by a single promote dispatch with no independent refute stage, so they
  carry no refutation ruling. Both were verified directly against the text before fixing: a table
  with two rows sharing one destination, and a local rule contradicting a global one.
