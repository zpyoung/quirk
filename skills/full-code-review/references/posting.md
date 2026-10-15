# Delivery & posting

Delivery is always human-gated. The detected seat selects vocabulary and transport;
it never removes the final approval step.

## Author seat

After a valid author-mode paste:

- `Will fix` and `Fix later` are preselected for inline posting.
- `Ignore` never posts.
- `Needs detail` requires a per-item ask.
- `Undecided` does not post and is listed back.

## Author-seat inline comments

With no paste, preserve the existing fallback: preselect Must fix and Should fix and
ask before Nit. Show the proposed batch and obtain final approval.

Posting still creates independent notes, but first cross-checks published discussions
and suppresses findings whose fingerprint marker appears in a note written by the
authenticated forge identity. The marker is the `fp` field of the note's leading
`<!-- quirk-review:v1 … -->` block. Markers are copyable text, so one in anybody else's
note is human context and suppresses nothing. Never edit or delete a previous note.

### GitLab

Create each note as a positioned discussion. Write the payload to a file and pass it
with `--input`; the JSON content type is required, because GitLab answers 415 without it:

```bash
glab api --hostname "$HOST" --method POST -H "Content-Type: application/json" \
  "projects/<url-encoded project>/merge_requests/<number>/discussions" \
  --input "$REVIEW_RUN_DIR/note-F1.json"
```

The payload is `{"body": <body>, "position": {...}}`. Build `position` from the
context file's `refs` (`base_sha`/`start_sha`/`head_sha` ← `refs.base`/`refs.start`/
`refs.head`) with `position_type: "text"` and the side-appropriate path and line from
the finding (see "Anchor on the correct diff side" below).

Two rules that cost the most time when missed:

- **Verify each created note came back as a `DiffNote`.** A wrong or stale `position`
  does not error — GitLab silently degrades the note to a plain comment detached from
  the line.
- **If the finding's line isn't part of the current diff, GitLab rejects the
  `position`.** Anchor on the nearest changed line and quote the exact code in the
  body. Never widen the diff to make a line anchorable.

Write bodies containing backticks to a file and pass the file — command substitution
runs inside double quotes, so an inlined body gets partially executed by the shell.

Use the finding's `file` and `line` (for a range, anchor on the first line). Build the
bodies with the shared builder, then post each eligible body verbatim as the note text:

```bash
python3 "$SCRIPTS/comment_body.py" author --report "$REPORT_JSON" \
  [--decisions "$DECISIONS_JSON"] --out "$REVIEW_RUN_DIR/bodies.json"
```

`bodies.json` maps each report finding ID to `{body, fingerprint, post}`, and carries
`overview` (the optional overview note) and `warnings` (each `impact`/`fix_md`
fallback taken on a finding that will post; the CLI also prints them). Only entries
with `post: true` are candidates for the batch, and the live `check` below can still
remove one. `--decisions` must be the author-seat export `validate_triage.py` wrote
for this same report: its `report_sha256` has to match the report, or the CLI exits 2.
It adds the reviewer's triage note to each finding and sets the overview counts. Only
Will fix, Fix later, and Needs detail count as posted; Ignore and Undecided count as not
posted. Without `--decisions`, every finding that memory did not suppress counts as
posted. Bodies follow
[`report-template.md` → Inline comment bodies](report-template.md#inline-comment-bodies);
the hidden block already carries the fingerprint, so nothing is appended. Never
hand-edit a body. The overview note is offered only when the user asks for it.
Never auto-post.

### Live duplicate check and receipts

Before previewing the proposed author batch, run:

```bash
python3 "$MEMORY_SCRIPT" check --report "$REPORT_JSON" --context "$CONTEXT" \
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
Only confirmed creates get receipts, never proposed/failed notes. For the paste-free
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

### Sweep and stage

```bash
python3 "$SCRIPTS/post_reviewer_review.py" stage \
  --report "$REPORT_JSON" --decisions "$DECISIONS_JSON" \
  --context "$CONTEXT_JSON" --out "$STAGED_JSON"
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
  and fix lines; the reviewer note moves into `Details`). It joins the single atomic
  batch.
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
python3 "$SCRIPTS/post_reviewer_review.py" publish --staged "$STAGED_JSON" --confirm
```

Publish freshly revalidates identity, head, and base/start diff refs, re-lists all
draft pages, and requires
exact set equality with the recorded staged IDs. Extra **or missing** IDs abort. Calls
are adjacent to reduce the unavoidable GET→POST window. One
`POST …/draft_notes/bulk_publish` publishes the batch.
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
python3 "$SCRIPTS/post_reviewer_review.py" complete --staged "$STAGED_JSON" \
  --action approve|request-changes|comment-only
```

- any Blocking finding suggests request-changes;
- otherwise approve may be suggested;
- approve is bound to the reviewed SHA;
- request-changes uses GitLab's merge-request reviewer-state mutation;
- comment-only performs no completion mutation.

A completion failure is reported as “review published, completion failed”; it never
pretends the already-visible review rolled back.

## Slack

Slack remains an optional separate delivery. Condense to one line per finding, drop
code blocks, lead with risk, and use an available Slack send tool. It does not replace
posting approval.

## Scope discipline

Only anchor on changed new-side lines. Reviewer inline finding drafts carry a GitLab
text position and are resolvable. Support-reply drafts have no position; they sit inside
an existing discussion. The overview is the sole non-resolvable note.
