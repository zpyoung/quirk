# filing-requests — Logic Spec

A quirk skill that runs a guided, evidence-gathering session about a request the user wants to
file — a bug report, a feature request, or a code-change request — and emits a terse, provenance-
marked artifact as markdown and, on explicit confirmation, as a GitHub issue.

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

## Data flow

The user invokes the skill with a description of what they want to file. The skill resolves the
target repo from the working directory, checks write access, globs for issue templates
(`.github/ISSUE_TEMPLATE/*.yml`, `.github/ISSUE_TEMPLATE/*.md`, `.gitlab/issue_templates/*.md`),
and reads `--depth` (default `read`).

It infers a request type from the description and asks one combined question: confirm the type,
and confirm the inspection depth. If its reading of the description suggests this is not a
fileable request, that judgment and its evidence go in the same turn.

With type confirmed, the field set is fixed — from the repo's template when one was found,
otherwise from the per-type core schema in `reference/field-catalogs.md`. The skill walks the
field set. For each field it first attempts resolution by inspection at the permitted depth; what
resolves becomes an `observed` field with its source recorded. What does not resolve becomes a
question to the user, and the answer becomes a `reported` field.

Two interrupts can fire during this walk. A **contradiction** — inspection disagrees with
something the user stated — is surfaced immediately with a citation, and the user's resolution
determines which value survives and with what provenance. **Type drift** — the accumulating
answers indicate a different request type — is surfaced with the evidence that changed the
picture; if the user switches, answers already given are mapped onto the new type's field set and
not re-asked.

**Core fields** are the required subset of the active field set — the sections the repo's template
marks required, or, absent a template, the required core listed for that type in
`reference/field-catalogs.md`. A core field is **resolved** when it holds a value with provenance
`observed` or `reported`, or is marked `missing` with a stated reason. Optional fields never gate
anything.

Once every core field is resolved or the user has answered at least once for each, the skill
renders the canonical form to markdown and shows it. Remaining questions are then driven by what
the draft makes visibly thin or wrong. The loop ends when all core fields are resolved — a field
the user cannot answer is resolved by marking it `missing`, so the loop always terminates.

At emission, the secret scanner runs over the canonical form's field values and reports any match
by field name. The skill will not proceed until the user resolves each finding (redact or keep).
The markdown artifact is then written to `docs/quirk/requests/YYYY-MM-DD-<slug>.md`
unconditionally. Only then, and only on a separate confirmation that displays the exact body and
destination, does the skill shell out to `gh issue create`.

In headless mode there are no questions. Fields resolvable by inspection are populated; everything
else is marked `missing` with reason `no human in session`. The artifact carries a prominent
statement that no human confirmed it. It is never filed to a tracker automatically.

## Key decisions & rationale

**Inspection buys question budget.** This is the skill's reason to exist. Anything the repo can
answer is not asked. The information-mismatch research says the highest-value fields are the ones
reporters skip; a coding agent can often establish several of them without asking at all.

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

**The request is not fileable.** The user describes what is actually a configuration error on
their side. The skill states this with the evidence and points to the relevant docs. If the user
disagrees and wants it filed anyway, the session continues and the artifact is produced.

**Inspection contradicts the user.** The user says the crash is in the auth layer; the traceback
terminates in the serializer. The skill shows both with `file:line` and asks. If the user holds
their position, their claim ships as `reported` and the contradicting observation is not silently
discarded — it appears as an `observed` field alongside it.

**Type drift.** The user opens with a feature request; the answers describe a production
regression. The skill names the evidence, offers to switch to the bug schema, and carries the
answers over. The user may decline and stay on the feature-request track.

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
- The canonical JSON representation with per-field provenance
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
- Request type is inferred from the description, then confirmed before branching
- Type drift is surfaced with evidence; on switch, existing answers carry over

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
- Headless mode is supported, degraded, and visibly marked as unconfirmed

**artifact-structure**

- An existing repo issue template is detected and conformed to
- Absent a template: required core plus optional extras, with empty sections pruned
- Unobtainable fields are emitted as sections marked missing, with the reason
- Three request types; anything else uses the nearest schema and states its nature in prose

**tone-and-length**

- Terse by default with a soft per-type ceiling; overflow cuts narrative, never fields
- Evidential register — structure over narrative, evidence adjacent to claims
- The problem stays primary; a reporter's proposed fix is included as a marked, open suggestion
- Symptom-first specific title, drafted by the skill, overridable by the user

**provenance-and-safety**

- AI-assistance disclosure appears when the target is public or third-party; when visibility or
  ownership cannot be determined confidently, the skill discloses
- Secrets are scanned for and reported by field; emission blocks until acknowledged
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

**Projection** — rendering the canonical form into a target format (markdown, GitHub issue body,
later GitLab and Jira). A pure function of the canonical form.

**Type drift** — the mid-session discovery that the confirmed request type is wrong, given the
answers gathered since.

## Status & amendments

**Status:** Draft — awaiting user review.

**Amendments:** none yet.
