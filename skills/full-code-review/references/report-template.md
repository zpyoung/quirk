# Markdown report and inline-comment format

Render the review in these five sections, in this order. This is the layout implemented
by `scripts/render_report.py --format md`. The coordinator authors `report.json` per
`html-report.md`; it does not hand-render this document. This file also defines the body
used for each gated inline comment.

The adversarial lens's claim table has no section of its own. It goes into the report's
`process_notes`, which the HTML page shows under Assumptions and notes and this
Markdown backend does not render. Claims that came back `wrong`, `misleading`, or
`partial` also appear as findings.

GitLab CommonMark discipline is binding: put a blank line between consecutive
bold-label lines, and separate findings with `---`, so labels and findings do not
collapse when posted.

## 1. Summary

Source fields:

- Heading: `meta.title`
- Opening narrative: `meta.standfirst_md`, when present
- Tally: derived from `findings`; authored counts are never accepted
- Verdict and seat: `meta.verdict`, `meta.seat`
- Source access and diff-only limitation: `run.source_access*`
- Dimensions run/skipped, diff size, coverage, guidance, run notes: `run.*`
- Mutation summary when the probe ran: derived from `mutation_probe`
- Adjudication line when `run.adjudication` is present, beside the tally:
  `Adjudicated 23: 15 agreed, 3 dropped, 2 fixes replaced, 1 unreachable, 1 survived,
  1 disputed, 2 merged` when complete, `⚠️ Not adjudicated: <reason>` when failed, and
  `Not adjudicated (turned off by policy)` when disabled

`run.dimensions_run` and `run.dimensions_skipped` carry the lens ids and,
for a skip, the reason: `test-adequacy, tests (no test files)`,
`comments (no comments added or modified)`, `adversarial (no change
description)`. `run.coverage` states `all 12 changed files reviewed` — or the ⚠️ form
naming what never reached the specialists (`diff unavailable`, `binary (not
text-reviewable)`), with `untracked` and `forge file list was truncated — rebuilt from
git` noted separately as provenance for files that *were* reviewed. Repeat any of it
under Assumptions. A report that omits coverage while files went unreviewed is wrong.

A `--since` delta review sets `run.since` (`ref` and `sha`); the Summary states it as
"Reviewed since" and names the review as report only.

For deep mode, `run.deep` adds the budget, elapsed time, execution consent and
sandbox status, and each area's ID, files, hotspot questions, status, and any
read-only degradation to the Summary, plus hunk coverage (`run.deep.hunk_coverage`) and any
`run.deep.unexamined` hunks. Name `unreached_areas` explicitly and set
`run.incomplete` and `meta.verdict` to `Incomplete review` rather than implying
those files were checked.

```markdown
# Valuing pinned credits at their locked rate

## 1. Summary

The change is focused, but two correctness findings need resolution.

**Tally:** 0 Must fix · 2 Should fix · 1 Nit

**Verdict:** Fix, then merge

**Seat:** reviewer

**Source access:** borrowed-worktree

**Dimensions run:** correctness, db

**Dimensions skipped:** tests (no tests changed)

**Diff size:** 12 files, 340 lines

**Coverage:** all 12 changed files reviewed

**Mutation probe:** run — 7 mutants, 6 killed, 1 survived

**Guidance loaded:** repo CLAUDE.md, pack guidance
```

## 2. Risk Assessment

Source: `risk.level`, full `risk.verbatim_md`, then `risk.caveats`. The specialist's
risk output is preserved unabbreviated. If `risk` is absent or `null`, this section
is omitted rather than stubbed.

```markdown
## 2. Risk Assessment

**Risk level:** Medium

<full risk.verbatim_md>

**Caveat — The gate claim is not total:**

<caveat.body_md>
```

## 3. Findings

The derived tally appears first. Findings use renderer-assigned IDs after stable
severity ranking. Sources are `severity`, plural `dimensions` (or singular
`dimension` degradation), `file`, `line`, `impact`, `body_md`/`issue`, and
`recommendation_md`/`recommendation`. A ` ```diff ` fence in the recommendation is
kept verbatim.

Deep-mode findings also show `evidence` (`reproduced` or `read from code`) and
`verification_status` (`confirmed` or `plausible`). For `repro`, print the
checker's command and observed output as a Reproduction block; for `plausible`,
show `what_would_confirm` beside a clear warning. A plausible finding remains
in the report for triage but never posts, even if marked Blocking or Will fix.

Adjudicated findings also show `production` as `**In production:** <label>: <path>`
under the impact. Any outcome other than `agreed` adds an `**Adjudication:**` line
(Survived challenge, Fix replaced, Unreachable, or Disputed); a Disputed finding adds
`**What would settle this:**` with `adjudication.what_would_settle`. The HTML page shows
the same outcome as a badge, the Disputed condition as a callout, and the objection,
proof, original fix, severity change, and merged members in a collapsed aside.

```markdown
## 3. Findings

**Derived tally:** 0 Must fix · 2 Should fix · 1 Nit

### F1 — By-type values do not reconcile to the total

**Severity:** Should fix

**Dimensions:** correctness, coordinator verification

**Location:** `billing/api/controller.py:211-261`

**Impact:** Merchants see per-type credit balances that do not add up to the total.

The helper rounds every part before summing, while the top-level value rounds once.

**Recommendation:**

Accumulate at full precision and quantize each emitted final amount once.

---

### F2 — Pinned-balance query has no row cap

...
```

When either source has entries, append a collapsed `<details><summary>Checked and dropped
(N)</summary>...</details>` at the end of this section from the union of
`run.deep.checked_and_dropped` and `run.adjudication.checked_and_dropped`. Each entry
includes its anchor and the specific refutation; an adjudicator entry also shows its
`proof`. Dropped claims are not counted as findings.

When empty, emit `No findings — see per-dimension notes below.` followed by one
bold-labeled line per `run.clean_notes` entry. Missing clean notes produce a generic
line and a renderer warning.

When memory is present, keep per-finding memory out of the findings themselves; it
is coordinator context. Add “Appears fixed” and
“Re-found after resolution / Possible regression” sections as applicable, even when
the current finding list is empty. “Appears fixed” is a handoff to
`quirk:receiving-code-review`, never an automatic thread resolution.

## 4. Assumptions

Source: top-level `assumptions`, after the coordinator consolidates finding-local
and whole-review assumptions. Include execution refusal, sandbox/dependency
degradation, and incomplete area coverage when deep mode is enabled.

```markdown
## 4. Assumptions

- Assumed `/webhook` is authenticated by the upstream gateway.
- Assumed the feature is enabled for the target store.
```

An empty list emits `- None recorded.` in the Markdown fallback. The HTML page omits
an empty Assumptions section.

## 5. Recommendations

Source: `recommended_order`, already prioritized blockers-first by the coordinator.

```markdown
## 5. Recommendations

1. Fix the reconciliation invariant before merge.
2. Add an application-level ceiling and telemetry to the unbounded path.
3. Address the naming nit if that block is touched again.
```

An empty list emits `1. No follow-up actions recorded.` in the Markdown fallback.

`recommended_order` feeds this section only. The HTML page renders no ordering
section: it severity-ranks the findings already, and each card carries its own
recommendation, so a prose restatement of that order earned no space. A Markdown paste
into GitLab has neither, which is why the section survives here.

## Inline comment bodies

Every comment the skill posts has three parts, built by `scripts/comment_body.py` from
trusted `report.json` data and used by both seats:

1. a hidden `<!-- quirk-review:v1 … -->` YAML block at the top (`kind`, `fp`, `seat`,
   `severity`, `disposition`, `dimensions`, `file`, `line`, `head_sha`, `verified`);
2. a short visible section that reads without expanding anything;
3. a collapsed `Details` section, omitted when it would add nothing beyond the visible
   lines.

The complete triage paste is validated first, then each `F<n>` is resolved against
`report.json`. Pasted title, anchor, severity, and finding prose are never used; the
paste contributes only the decision slot, the reviewer's note, and a support-reply
target. Author delivery runs `comment_body.py author` (see `posting.md`); reviewer
delivery builds the same bodies inside the stager. Before posting, run the live
cross-check and omit already-posted findings per `posting.md`.

Deep-mode delivery is restricted to `verification_status: "confirmed"`.
The builder, author poster, and reviewer stager must all exclude
`verification_status: "plausible"` before constructing or posting any
finding body, regardless of triage disposition or severity floor. Keep
plausible findings visible in the rendered report and list them as omitted
in the posting preview; do not recast them as confirmed.

### Finding comment

The visible section, in order:

1. **Lead.** `**<lead>** · <title>`. The reviewer seat leads with the disposition
   (Blocking, Non-blocking, Question); the author seat leads with the severity (Must
   fix, Should fix, Nit). No local `F<n>` or dimension tag appears.
2. **Fixed sentence.** Non-blocking adds an optional/non-blocking sentence and Question
   adds a clarification ask, directly under the lead.
3. **Reviewer note.** The triage note as a `> **Reviewer note:**` quote, only when one
   exists.
4. **Why.** `impact`, one sentence.
5. **Fix.** `**Fix:** <fix_md>`, one line.

```markdown
<!-- quirk-review:v1
kind: finding
fp: 3f9a1c2e…
seat: reviewer
severity: Should fix
disposition: Non-blocking
dimensions: [correctness]
file: billing/api/controller.py
line: 211
head_sha: 6b6e4be0…
verified: true
-->
**Non-blocking** · By-type values do not reconcile to the total

*Optional feedback — this does not block the merge.*

Merchants see per-type credit balances that do not add up to the total.

**Fix:** accumulate at full precision and quantize each emitted amount once.

<details><summary>Details</summary>

The helper rounds every part before summing, while the top-level value rounds once.

**Evidence:** mutation probe · mutant survived · verified

</details>
```

Source mapping:

| Comment part | Report field |
|---|---|
| Lead title | `title` |
| Why | `impact` |
| Fix | `fix_md` |
| `Details` | `body_md` (falling back to `issue`), then `aside_md` as a quote, then `evidence`, `verified`, and finding-local `assumptions` |

The full `recommendation_md` is never posted. A finding without `impact` or `fix_md`
falls back to the first sentence of `body_md` or `recommendation_md`, and the builder
or staging preview names each fallback as a warning. A fallback sentence longer than the
field's cap (200 characters for the why line, 160 for the Fix line) is dropped instead:
the line is omitted and a warning names the finding. `Details` is omitted when the body
only repeats the why line and no aside, evidence, assumptions, or support note exist.
Drop and Undecided create no note. Any posted Nit on the reviewer seat is normalized to
Non-blocking and the staged preview warns about it.

### Reviewer overview body

The non-inline overview is built only from trusted report data. Its visible section is
the verdict and tally line, a diff-only or head-moved warning when one applies, up to
three Blocking titles, and a count of earlier findings still open or resolved but still
present when non-zero. Its `Details` holds:

- `meta.standfirst_md`, `risk.level` with `risk.verbatim_md`, and top-level `assumptions`;
- clean dimensions and the mutation probe summary;
- earlier findings still open, previously resolved but still present, and appears fixed;
- run limits: the `run.source_access_reason`, skipped dimensions, a head-movement note
  when `--allow-unaffected` was used, and posted and not-posted counts.

```markdown
<!-- quirk-review:v1
kind: overview
seat: reviewer
head_sha: 6b6e4be0…
report_sha256: 9e1f…
posted: [3f9a…]
still_open: [55aa…]
-->
**Fix, then merge** · 0 Must fix · 2 Should fix · 1 Nit

> Diff-only review: every finding is unverified.

1 earlier finding still open

<details><summary>Details</summary>

**Summary**

The change is focused, but two correctness findings need resolution.

**Run limits**

- Posted: 2 · Not posted: 1

</details>
```

It is staged before the inline drafts so the batch presents framing before detail. It is
the sole non-resolvable note. The author seat's optional overview note has the same shape.

### Support reply

A reviewer-seat reply inside another person's discussion, in place of the inline finding.
It reuses the finding fields with `kind: support`, `supports_discussion`, and
`supports_note` in the block. The reviewer's note goes inside `Details`, so the visible
section stays at the lead, the why, and the fix. Staging rules are in `posting.md` →
Support replies.

```markdown
<!-- quirk-review:v1
kind: support
fp: 3f9a1c2e…
supports_discussion: 9f2c…
supports_note: 481223
disposition: Blocking
-->
**Agree · Blocking** · quirk full-code-review found this independently

Merchants see per-type credit balances that do not add up to the total.

**Fix:** accumulate at full precision and quantize each emitted amount once.
```

### Escaping

All report text is neutralized before it enters a body:

- Every line ending GitLab honors (CRLF, CR, U+2028, U+2029) is first normalized to LF,
  so none can hide a line start from the escapes below.
- Metadata values that contain `-->`, a line break, or a leading `#` are written as
  escaped, quoted strings, so they cannot close the hidden block.
- Literal `<details` and `</details>` in any text are escaped, so they cannot close
  `Details` early.
- A line-leading `/` is backslash-escaped, inside code fences too, so GitLab never runs
  it as a quick action under the posting user's account. GitLab's quick-action extractor
  may not skip the same fences the builder tracks, so a fenced `/command` shows a
  visible backslash.
- Outside a code fence, a line-leading `<` that starts any tag, comment, declaration,
  processing instruction, or CDATA section has its `<` escaped as `&lt;`, so it cannot
  swallow the rest of the note.
- Outside code fences and code spans, an `@` mention gets a zero-width space after the
  `@`, so it does not notify anyone.
- A dangling code fence is closed.
- The block carries review mechanics only (IDs, dimensions, flags), never secrets: it is
  hidden, not private.
