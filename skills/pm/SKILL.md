---
name: pm
description: Use when the user asks what to work on next, wants to review or update the roadmap, is starting/finishing/parking a tracked task, wants to close something as wontfix/superseded, or asks about backlog or task status. Also use when the user invokes /quirk:pm:* commands. Routes to bin/pm.py, the consumer for BUGS.md / DEFERRED.md / TEST_BACKLOG.md / proposals.md.
---

# PM: Shepherding the Backlog

quirk's typed artifacts are an append-only queue with no consumer — entries go in and nothing
reports depth or tells you what's done. `bin/pm.py` is that consumer: it turns the ledger into an
ordered plan (`ROADMAP.md`) and a lifecycle (`open → in_progress → delivered → closed`).

**It records and surfaces state; it does not enforce it.** Every check it runs is a mistake-catcher
for a cooperative worker, not a guarantee — never phrase a refusal as though it stops deliberate
circumvention.

**Never `Edit`/`Write` an artifact file (`BUGS.md`, `DEFERRED.md`, `TEST_BACKLOG.md`,
`proposals.md`, `ROADMAP.md`) directly.** Every mutation routes through `bin/pm.py` or
`bin/artifact_append.py`, invoked by one of the nine commands below. Reading these files for
context is fine; writing to them outside the scripts is not.

## Job 1 — roadmap and what's next

| Command | Does | Gate |
|---|---|---|
| `/quirk:pm:roadmap` | Propose or revise the milestone grouping | you ratify before it writes |
| `/quirk:pm:next` | Shortlist ~5 ready entries, recommend 1 | read-only; any intake write is ratified |

Code computes the ready-set, its sort order, and the shortlist — never a total ordering by the
model, which is unstable by construction (LLM judges violate transitivity at material rates). Two
things stay yours to do in prose, because code cannot do them:

- **The milestone grouping.** `roadmap` validates the *grammar* of whatever you propose; it never
  proposes the grouping itself. Gather the open entries, group them into milestones with a
  rationale, show the proposal, and only write on explicit approval.
- **The one-candidate recommendation.** `next` computes and orders the shortlist; you argue for one
  entry from it, with a stated reason. Push back on the sort if you disagree — but don't rewrite it.

`next` reports the unplaced count on every run, whether or not you act on it — medium/low-urgency
work sitting in no milestone is otherwise invisible to the whole system. Offer to place it;
declining is fine. Placement is a roadmap write and goes through the same ratification gate.

## Job 2 — ushering a started task

| Command | Does | Gate |
|---|---|---|
| `/quirk:pm:start` | Baseline a probe, mark `in_progress` | unattended |
| `/quirk:pm:finish` | Re-run the probe on `HEAD`, mark `delivered` | unattended |
| `/quirk:pm:park` | Return to `open`, keep the attempt on record | unattended |
| `/quirk:pm:decide` | Terminal `wontfix`/`superseded` | **human-gated — never unattended** |
| `/quirk:pm:reconcile` | Promote `delivered` → `closed` from git ancestry | unattended, origin-side |

The red→green baseline is the mechanism: a probe must **fail** at `start` — a probe that already
passes doesn't discriminate the entry, and `start` refuses it — and must **pass** at `finish`.
Working unverified is a deliberate choice, never a default: `--probe none`, typed out.

`decide` is the one transition that removes work from the board without anything being done, and
it's the only one locked human-gated. Confirm the exact ID, the `--as` value, and the reason with
the user before running it — every time, even mid-session, even if the request seemed to already
authorize it.

Phase note: `start` runs locally only (`--here`) in this build. Cross-repo dispatch — `--repo`,
worktree creation, the handoff packet — is a later phase and isn't available yet.

## Other commands

| Command | Does |
|---|---|
| `/quirk:pm:status` | Index + doctor findings, read-only |
| `/quirk:pm:migrate` | Idempotent v1 → v2 schema upgrade |

## First-time setup

If a `pm.py` command reports a ledger file missing, the project hasn't run
`/quirk:artifacts:init` — suggest it before anything else. A missing `ROADMAP.md` is not this case;
it just means no milestones exist yet, which every read command handles as the empty case.
