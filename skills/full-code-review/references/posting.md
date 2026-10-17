# Delivery & posting

Delivery is always human-gated. The detected seat selects vocabulary and transport;
it never removes the final approval step.

Deep-mode `run.deep.checked_and_dropped` entries are audit context, not findings
to deliver. Findings with `verification_status: "plausible"` stay in the report
for human triage but **never post**, even if severity, a pasted decision, or
explicit `--ids` selects them. List each excluded ID and reason in the preview.
The body builder marks these `post: false`, the author posting script skips
them again, and the reviewer stager omits them before drafts or blocking
counts. Only `verification_status: "confirmed"` deep findings can be posted.

## Author seat

After a valid author-mode paste:

- `Will fix` and `Fix later` are preselected for inline posting.
- `Ignore` never posts.
- `Needs detail` requires a per-item ask.
- `Undecided` does not post and is listed back.

## Author-seat inline comments

With no paste, preselect every finding at or above the report's `run.severity_floor`
(default Should fix). Findings below the floor never post from either seat;
`comment_body.py` marks them `post: false` and the reviewer stager omits them. Show the
proposed batch and obtain final approval.

For a deep report, filter out plausible findings before proposing the batch;
the poster independently blocks them if passed in `--ids`. The report's
`repro` and `what_would_confirm` are review evidence, not permission to bypass
the posting gate.

Posting still creates independent notes, but first cross-checks published discussions
and suppresses findings whose fingerprint marker appears in a note written by the
authenticated forge identity. The marker is the `fp` field of the note's leading
`<!-- quirk-review:v1 … -->` block. Markers are copyable text, so one in anybody else's
note is human context and suppresses nothing. Never edit or delete a previous note.

### Posting the approved batch

Post with the script, which works for both forges, anchors each finding on the correct
diff side, skips any line outside the diff with a warning, and writes a receipt for
every confirmed create as it goes:

```bash
python3 "$SCRIPTS/post_author_comments.py" --report "$REPORT_JSON" --context "$CONTEXT" \
  --bodies "$REVIEW_RUN_DIR/bodies.json" --ids F1,F3 \
  --out "$REVIEW_RUN_DIR/posting-receipts.json" [--overview]
```

`--ids` is exactly the approved batch. A finding not marked `post: true` in
`bodies.json` is skipped with a warning, and the script refuses a `bodies.json` that
`comment_body.py author` did not build from this same report (its `report_sha256` must
match), so a stale file can't post old text on a new finding's line. A skipped
finding (outside the diff, or on a file the forge collapsed) is not posted anywhere
else: read the warnings and tell the user which approved ids did not post. On GitHub
each finding becomes a pull-request review comment (`path`, `line`, `side`,
`commit_id`); on GitLab a positioned discussion built from `refs`. A failed create stops the batch and exits 2 with the IDs already
posted and any warnings collected so far; their receipts stay in `--out`. A create that
times out or returns garbage may still have committed, and the script does not look for
it on resume: before rerunning after a failed create, rerun the live duplicate check so
the same finding is not posted twice. When a comment was created but its receipt could
not be written, the failure names it as posted and carries the receipt under
`unsaved_receipt`; record that by hand instead of reposting. The
`--overview` receipt goes to a sibling file named from the `--out` stem
(`receipts.json` becomes `receipts.overview.json`), so `--out` holds only finding
receipts and `review_memory.py save --receipts` accepts it unchanged. The posted
overview lists what actually posted, rebuilt from the receipts. The report must match
the context's change and project, and its head too when `meta.head_sha` is present
(author reports usually omit it; `meta.source_branch` is compared when both sides name
one). Every requested finding needs a numeric line, or the script exits 2 before the
first create. The script also re-reads the live change before the first create: a change
that is no longer open, or whose head differs from the context's `refs.head`, exits 2 with
nothing posted, so rerun the review.

Two rules that cost the most time when missed:

- **On GitLab, a created note must come back as a `DiffNote`.** A wrong or stale
  `position` does not error; GitLab silently degrades the note to a plain comment
  detached from the line. The script treats a missing `DiffNote` as a failed create,
  names the stray comment's URL in the error, and records it in `<out stem>.stray.json`;
  that finding is skipped on rerun until you delete the comment and its entry.
- **A line outside the current diff cannot be anchored** on either forge. Anchor on the
  nearest changed line and quote the exact code in the body. Never widen the diff to
  make a line anchorable.

Use the finding's `file` and `line` (for a range, anchor on the first line). Build the
bodies with the shared builder, then post each eligible body verbatim as the note text:

```bash
python3 "$SCRIPTS/comment_body.py" author --report "$REPORT_JSON" \
  [--decisions "$REVIEW_RUN_DIR/decisions.json"] --out "$REVIEW_RUN_DIR/bodies.json"
```

`bodies.json` maps each report finding ID to `{body, fingerprint, post}`, and carries
`overview` (the optional overview note), `overview_plan` (the posted and not-posted
lists the posting script rebuilds the overview from), `report_sha256` (the digest the
posting script checks) and `warnings` (each `impact`/`fix_md` fallback taken on a finding that will
post; the CLI also prints them). Only entries
with `post: true` are candidates for the batch, and the live `check` below can still
remove one. `--decisions` must be the author-seat export `validate_triage.py` wrote
for this same report: its `report_sha256` has to match the report, or the CLI exits 2.
It adds the reviewer's triage note to each finding and sets the overview counts. Only
Will fix, Fix later, and Needs detail count as posted; Ignore and Undecided count as not
posted. Without `--decisions`, every finding that memory did not suppress and that sits
at or above `run.severity_floor` counts as posted; the rest, including below-floor
findings, count as not posted. Bodies follow
[`report-template.md` → Inline comment bodies](report-template.md#inline-comment-bodies);
the hidden block already carries the fingerprint, so nothing is appended. Never
hand-edit a body. The overview note is offered only when the user asks for it.
Never auto-post.

### Live duplicate check and receipts

Before previewing the proposed author batch, run:

```bash
python3 "$MEMORY_SCRIPT" check --repo "$REVIEW_SOURCE_ROOT" --report "$REPORT_JSON" --context "$CONTEXT" \
  --out "$REVIEW_RUN_DIR/posting-memory.json"
```

The plan maps the same severity-ranked `F<n>` IDs to `fingerprint`, `state`,
`suppress_post`, and thread context. A failed discussion fetch blocks posting;
do not treat missing API data as “nothing posted”. Omit every `suppress_post: true`
finding from the proposed batch, but keep it in the report and show its thread link.
Human unmarked comments and fuzzy candidates never silently suppress.
Recheck immediately before creating notes if time has passed since preview; if the
eligible batch changed, show the new batch and renew approval. The cross-check and
create are separate API calls: simultaneous sessions retain a narrow GET-to-POST race.

Each body's leading block carries the finding's `fp` (a 64-character lowercase SHA-256
fingerprint) when the report supplies one.

After each successful `DiffNote` create, write its actual receipt into a scratch JSON
map keyed by the report's finding ID, preserving earlier successful entries:

```json
{
  "F1": {
    "published": true,
    "discussion_id": "<returned discussion id>",
    "note_id": 123,
    "url": "https://gitlab.example/group/project/-/merge_requests/42#note_123",
    "head_sha": "<reviewed head SHA>"
  }
}
```

For a validated paste, save with:

```bash
python3 "$MEMORY_SCRIPT" save --report "$REPORT_JSON" \
  --decisions "$REVIEW_RUN_DIR/decisions.json" \
  --receipts "$REVIEW_RUN_DIR/posting-receipts.json"
```

`save` exits 1 when its JSON says `saved: false` (the JSON is still printed). Check the
exit code and, on failure, tell the user their triage decisions or receipts were not
saved. Only confirmed creates get receipts, never proposed/failed notes. For the paste-free
author fallback, use the same save command **without** `--decisions`: it records
receipts only and preserves prior human decisions without inventing new ones.
A finding with a missing or ambiguous anchor has no `fp`, so its body carries no
marker; show that limitation before approval.
If a create's response is lost, cross-check discussions before considering a retry.
If local receipt persistence fails after a successful create, report “posted, memory
save failed”; never repeat the POST to repair a local file.

**Anchor on the correct diff side.** A finding about an *added or changed* line anchors
with `new_path` + `new_line`. A finding about a *removed* line has no new-side position —
anchor it with `old_path` + `old_line` instead, or GitLab will reject the `position` (or
silently attach it to the wrong line). For a renamed file, `old_path` and `new_path`
differ and both are required. When a finding spans a deletion and an addition, anchor on
the new side and quote the removed code in the body.

## Reviewer seat

A structurally valid reviewer-mode paste is mandatory when findings exist. There is no
severity fallback: without a paste, no finding draft is created and the flow ends after
cleanup.

A zero-findings report has no decisions or triage controls but still has a meaningful
clean-review overview. After explicit confirmation to post that result, use
`validate_triage.py --zero-findings` to create a report-bound empty decision artifact.
This is the sole paste-free reviewer path; it infers no disposition and still requires
staging preview plus final publish approval.

### Decision policy

| Slot | Reviewer label | Delivery |
|---|---|---|
| `fix` | Blocking | Inline draft (or support reply); counts as blocking review feedback |
| `later` | Non-blocking | Inline draft (or support reply) marked optional in the body |
| `detail` | Question | Inline draft (or support reply) phrased as an ask |
| `ignore` | Drop | Never posted |
| `none` | Undecided | Never posted; list back |

A Nit selected for any posting slot is normalized to **Non-blocking** and surfaced in
the staging warnings. Drop remains Drop. The staged preview is the final truth the user
approves.

Even a Blocking (`fix`) triage decision cannot stage a plausible finding.
Show it as omitted with reason `plausible finding (never posted)`; do not
count it toward a blocking review. Keep the finding in `report.json` and
its rendered card.

### Trusted bodies

`post_reviewer_review.py` first verifies the normalized decisions' SHA-256 binding to
the exact `report.json`, then builds every body through `scripts/comment_body.py` from
that report plus the trusted review context. The paste contributes only the validated
slot, the optional human note, and the optional support-reply target. Pasted
title/anchor/severity text is never used to construct a posted comment.

Reviewer inline comments use the three-part layout in
[`report-template.md`](report-template.md#inline-comment-bodies): a hidden
`quirk-review:v1` block carrying the fingerprint, a short visible section, and a
collapsed `Details`.

```markdown
<!-- quirk-review:v1
kind: finding
fp: 3f9a…
-->
**Blocking** · Refund path reads the live rate

> **Reviewer note:** we hit this exact drift in the March refund incident.

Refunds issued after a rate change return a different amount than was charged.

**Fix:** read the rate stored on the original charge.

<details><summary>Details</summary>

…body, aside, evidence…

</details>
```

No local `F#` or dimension tag is visible. Non-blocking and Question lead with their
disposition and add a fixed sentence under the lead. The overview is authored from
Summary/verdict, tally, Risk, Assumptions, and any diff-only/head-movement limitation;
its visible part is the verdict, tally, top blockers, and earlier-finding counts, and
the rest sits in `Details`.

### GitHub specifics

GitHub stages the whole batch as **one pending review**: a single create carries the
overview as the review body and every inline finding as a review comment, and support
replies are added inside that pending review through GraphQL. Consequences:

- GitHub allows one pending review per user per pull request, so any existing pending
  review blocks staging (exit 4), the same as GitLab drafts.
- A finding whose line is outside the diff (or on a file the forge collapsed) can't be a
  review comment, because one unplaceable comment fails the whole create. It is omitted
  with a warning and listed under "Not anchored inline" in the overview, so the approved
  finding still reaches the change's author. GitLab stages the same way.
- If the create errors but GitHub committed it anyway, the stager adopts the pending
  review whose body matches the overview instead of creating a second one.
- Cleanup is one user-run `gh api … -X DELETE …/reviews/<id>`, which removes the pending
  review and every comment in it.
- Publish submits the review with `event: COMMENT`. Completion is a separate review with
  `APPROVE` or `REQUEST_CHANGES`; GitHub refuses either on your own pull request.

### Sweep and stage

```bash
python3 "$SCRIPTS/post_reviewer_review.py" stage \
  --report "$REPORT_JSON" --decisions "$REVIEW_RUN_DIR/decisions.json" \
  --context "$CONTEXT" --out "$REVIEW_RUN_DIR/staged-review.json"
```

Before the first POST, the script:

1. revalidates the authenticated user, open MR, author, full head SHA, and `diff_refs`
   — changed base/start refs always abort for a re-run; only head movement is
   partitionable;
2. for a memory-enabled report, fetches all published discussions, reclassifies
   findings against that live snapshot, and omits already-posted notes;
3. paginates every page of the authenticated user's draft notes;
4. requires the draft set to be empty.

It saves report-bound decisions separately from receipts. No draft is considered
published. A stale report or mismatched memory target cannot borrow another change's
posting state.

Any existing draft stops staging and is named. GitLab bulk publication includes every
draft owned by the authenticated user on that merge request, so staging on top would invalidate
the preview.

The overview is staged first, then inline notes in renderer order, then support
replies. Each successful ID
is written immediately to `staged-review.json`. If a later create fails, nothing is
published; show `cleanup_commands`. They are exact **user-run** DELETE commands for only
this run's created IDs. After a failed create, the script re-lists the draft set: a
draft whose body matches the failed note is a committed-but-unacknowledged create and
joins `reconciled` and the cleanup commands; any other unrecorded draft is surfaced in
`unrecognized_drafts` for the user to adjudicate and never gets a delete command. If
the re-list fails too, `cleanup_warning` says cleanup may be incomplete.
The agent is not allowed to execute DELETE.

### Support replies

A support reply backs another person's unresolved comment on the same file and line
instead of opening a duplicate thread. Only the reviewer seat posts them.

- **Offer.** The triage page shows a **Reply in support** toggle, on by default, for a
  finding whose memory `human_context` holds an unresolved comment. It targets the
  first such comment. A comment the posting identity wrote is never offered as a reply
  target. Turning it off posts a normal inline finding.
- **Paste.** A selected target arrives as `  reply: <note_id>` under the finding's
  anchor line. `validate_triage.py` accepts it only when the note ID is an unresolved
  `human_context` entry of that finding, and returns it as `reply_note_id`.
- **Stage.** After the inline drafts, the stager creates the reply as a draft note with
  `in_reply_to_discussion_id` and no position, with the body built by `comment_body`
  (`**Agree · <disposition>** · quirk full-code-review found this independently`, then the why
  and fix lines; the reviewer note moves into `Details`). On GitLab it is one more draft
  in the batch. On GitHub it is a separate mutation after the single review create, so a
  reply failure leaves the pending review without it.
- **Stale target.** If the target is no longer an unresolved `human_context` entry at
  stage time, the finding falls back to an inline draft and the staging warnings say
  so.
- **Preview.** Replies show as `reply → @author`. Drop and Undecided still post
  nothing, and a Nit takes the same Non-blocking normalization as an inline finding.

### Head movement before stage

A moved head blocks normal staging. The script compares old to new, reports changed
paths, and partitions finding IDs. Offer:

1. re-run the review; or
2. after explicit user approval, call stage with `--allow-unaffected`.

The latter omits findings in changed files, reanchors unchanged files with the current
`diff_refs`, and adds a prominent partial-review note to the overview. Compare failure
fails closed.

### Preview and atomic publish

Show the complete staged `preview`, omitted decisions, normalization warnings, and all
draft IDs. Ask for explicit final approval. Then, and only then:

```bash
python3 "$SCRIPTS/post_reviewer_review.py" publish --staged "$REVIEW_RUN_DIR/staged-review.json" --confirm
```

Publish freshly revalidates identity, head, and base/start diff refs, re-lists all
draft pages, and requires
exact set equality with the recorded staged IDs. Extra **or missing** IDs abort. Calls
are adjacent to reduce the unavoidable GET→POST window. One
`POST …/draft_notes/bulk_publish` publishes the batch on GitLab; on GitHub one submit
of the pending review does.
Memory-enabled publication also rechecks published markers before the draft-set
check. If one of the staged findings appeared since staging, abort and offer user
cleanup/restaging; do not publish duplicates or selectively delete staged drafts.
After successful bulk publication, write the published state first, then recover
discussion/note IDs and save receipts. Receipt lookup or ledger failures only add
warnings: publication already happened.

If the head moved after staging, publishing only unaffected notes cannot stay atomic:
the existing drafts cannot be selectively deleted by the agent and bulk publish would
include all of them. Abort, show this run's cleanup commands, and offer user cleanup
followed by rerun/restage. Never switch to per-draft publication.

### Completion

After successful publish, offer all three actions and require an explicit choice:

```bash
python3 "$SCRIPTS/post_reviewer_review.py" complete --staged "$REVIEW_RUN_DIR/staged-review.json" \
  --action approve|request-changes|comment-only
```

- any Blocking finding suggests request-changes, including one that could not be anchored inline and is listed in the overview;
- otherwise approve may be suggested;
- approve is bound to the reviewed SHA;
- request-changes uses GitLab's merge-request reviewer-state mutation, or a `REQUEST_CHANGES` pull-request review on GitHub;
- comment-only performs no completion mutation.

A completion failure is reported as “review published, completion failed”; it never
pretends the already-visible review rolled back.

## Slack

Slack remains an optional separate delivery. Condense to one line per finding, drop
code blocks, lead with risk, and use an available Slack send tool. It does not replace
posting approval.

## Scope discipline

Anchor on changed lines, using the old side for removed code (see "Anchor on the
correct diff side"). Reviewer inline finding drafts carry a GitLab
text position and are resolvable. Support-reply drafts have no position; they sit inside
an existing discussion. The overview is the sole non-resolvable note.
