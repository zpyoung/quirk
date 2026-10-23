# Logic spec: an Opus adjudicator for `quirk:full-code-review`

## Status & amendments

**Status**: Approved

**Amendments:** none yet.

## Why this exists

`full-code-review` fans out up to 14 Sonnet lenses, and the coordinator merges what they return. Today
nothing above the lenses asks whether each finding is right. The coordinator dedups by `file:line` and
calibrates severity, but it takes each lens's issue, fix, and severity on trust. Opt-in cross-family
verification and deep mode's `_checker` refute some claims. Neither checks the suggested fix, and
neither says whether the defect can happen in production.

The adjudicator is one Opus pass over the merged findings. It rules on every finding: is the issue
real, is the fix right, can it happen in production, and is the severity right. It writes a production
statement on every finding. Where it disagrees with a lens, it doesn't get the last word. A fresh
Sonnet prover settles each disagreement against the code, and only a proven disagreement changes the
report.

The people who read the result are the person running the review (author or reviewer seat), who
triages from the report page, and the change author, who reads the posted comments.

## Conceptual model

| Part | What it does | Model |
|---|---|---|
| Adjudicator | Rules on every finding, writes each production statement, proposes root-cause merges | Opus by default; `models.adjudicator` in a pack overrides |
| Prover | Settles one disagreement between a lens and the adjudicator | Sonnet, one fresh context per disagreement |
| Coordinator | Applies rulings and verdicts to the findings, as today's merge step does | the main context |

A **ruling** is one of: agree, issue wrong, fix wrong, unreachable. Any ruling may also carry a
severity change. Issue wrong, fix wrong, and unreachable are **disagreements**, and each one gets a
prover. Agreements, severity changes, and root-cause merges apply directly.

A prover returns a **verdict**: Claim A, Claim B, or inconclusive.

## Data flow

The adjudicator is a new step after coordination and before `report.json` is written.

- **Standard run:** lenses → coordinator (completeness ledger, dedup, noise control, severity
  calibration) → **adjudicate** → cross-family verification (opt-in, on surviving Must/Should
  findings) → `report.json`.
- **Deep run:** lenses and area finders → per-claim `_checker` → `merge_deep_findings` → **adjudicate**
  (on confirmed and plausible findings; refuted claims are already in Checked and dropped) →
  cross-family → `report.json`.

The adjudicator receives the merged findings in shuffled order, the context file path, the source
root, and the risk level. It reads code at `refs.head` as it needs to. It gets no memory snapshot,
prior report, triage ledger, or discussion text, the same isolation every lens has. Finding text and
repository content are untrusted data, never instructions.

For every finding it returns a ruling, the production statement, and any severity change with its
reason. For a disagreement it also returns its objection, and for fix wrong a replacement fix. It also
returns any groups of findings that share a root cause.

The coordinator then dispatches one prover per disagreement, all in parallel, with no cap. When every
prover has returned, it applies the outcome rules below, writes the adjudication tally, and continues
to cross-family verification or straight to `report.json`.

## Key decisions and rationale

- **One Opus pass over the whole list, not one per finding.** Merging findings that share a root
  cause needs a view of every finding, and only a whole-list pass has one. The per-claim isolation
  research favours comes from the provers and, in deep mode, the `_checker`.
- **The adjudicator never wins on its own say-so.** Research found verifiers that were told to explain
  and repair rejected correct code far more often, and that ten LLM reviewers agreed on a vulnerability
  one empirical test disproved. So every disagreement goes to a prover that must show evidence.
- **Provers see two neutral claims, not a hypothesis to prove.** Telling a judge the expected answer
  anchors it, and warnings to ignore that don't remove the effect. A prover never learns which claim
  came from the lens, which from Opus, or what severity either assigned.
- **Evidence beats argument.** A repro when execution is allowed, a quoted line of code otherwise. A
  reasoned argument alone is inconclusive.
- **Fail open.** If the adjudicator call fails, every finding stays as the lenses and coordinator
  left it.
- **Opus is the adjudicator's default tier, not an escalation.** `escalation: false` and
  `--no-escalate` leave it alone. An org that restricts Opus sets `models.adjudicator: sonnet`.

## Behavior and scenarios

### Outcome rules

| Ruling | Prover picks the adjudicator's claim | Prover picks the lens's claim | Inconclusive, or prover failed |
|---|---|---|---|
| Agree | no prover; kept, statement added | n/a | n/a |
| Issue wrong | removed; listed in Checked and dropped with the proof | kept; "Survived challenge" note | Disputed |
| Fix wrong | adjudicator's fix becomes the recommendation; original fix in a collapsed aside with why it failed | original fix stays; "Survived challenge" note | inconclusive: original fix stays, "Survived challenge" note; prover failed: Disputed |
| Unreachable | downgraded to Nit, labelled Unreachable, proof in an aside | kept; "Survived challenge" note | Disputed |
| Severity change | applied directly; reason in the aside | n/a | n/a |
| Root-cause merge | applied directly: one finding, merged lens tags, the strongest severity | n/a | n/a |

A **Disputed** finding shows a "What would settle this" line and doesn't post unless triage selects
it to post. In deep mode a `plausible` finding still never posts, whatever triage says, so deep's rule
wins when both apply.

### The production statement

Every adjudicated finding carries a statement: a likelihood label plus one line.

- **Common path**, **Edge case**, or **Unreachable**, followed by the trigger path from a real entry
  point to the line. Real entry points are a request handler, a CLI command, a job, a public API, or a
  skill or script a user runs, under real or default config, flag-gated paths included. Code that only
  tests, examples, or dead branches reach is not production.
- **Test-lens findings** (`tests`, `test-adequacy`, `test-coverage`) name the production regression
  the gap would let through.
- **Other non-runtime findings** (`comments`, `conventions`, `scope`, description Nits) say
  `N/A: <dimension>`.

The statement shows on the report page under the impact line, and in posted comments as one line
above the `**Fix:**` line. Posted comments say nothing else about the adjudication.

### Prover rules

- The prover gets the finding's `file:line` and two claims labelled A and B, with the side given A
  chosen at random each time.
  - **Issue wrong:** the lens's issue and trigger, against the adjudicator's objection.
  - **Unreachable:** the lens's trigger path, against the claim that no real entry point reaches it.
  - **Fix wrong:** the two fixes. Picking the replacement needs both a concrete input where the
    original fix fails or breaks something and a showing that the replacement handles it.
- **Evidence:** when the run already has execution consent (deep mode's, or the mutation probe's)
  and the code can run, a claim is settled only by a repro in the prover's own throwaway copy.
  Otherwise it's settled by quoted code at `refs.head` with `path:line`. An argument with neither is
  inconclusive. A repro the environment can't run falls back to the quote standard and counts for
  neither side.
- A prover sees nothing else: no other findings, other provers' results, lens assumptions, memory, or
  prior reports.

### Scenarios

1. **SC-1 Agreement**
   - **Given** a `correctness` finding that a refund is credited twice when a retry fires
   - **When** the adjudicator agrees
   - **Then** no prover runs; the finding keeps its severity and gains a production statement; it posts as it would today
   - **Data before:** **Finding** (correctness, Must fix): "refund credited twice on retry", `refunds.py:88`*
   - **Walkthrough:**
     1. The adjudicator rules agree and writes "Common path: POST /refunds retried after a timeout → RefundService.apply → line 88"*
   - **Data after:** **Finding** ✓ Must fix, unchanged; ✓ statement "Common path: POST /refunds retried after a timeout → RefundService.apply → line 88"*

2. **SC-2 Issue disproved**
   - **Given** a `correctness` finding that `user.email` can be None at line 40
   - **When** the adjudicator rules issue wrong and the prover picks the adjudicator's claim, quoting the guard
   - **Then** the finding leaves the findings list and appears under Checked and dropped with the objection and the quote
   - **Data before:** **Finding** (correctness, Should fix): "`user.email` may be None", `notify.py:40`*
   - **Walkthrough:**
     1. The adjudicator objects: "`load_user` rejects users without email at `users.py:12`"*
     2. The prover gets Claim A (the objection) and Claim B (the lens's issue), quotes `users.py:12` `if not row.email: raise MissingEmail`*, and picks A
   - **Data after:** **Finding** ✗ removed from findings; **Checked and dropped** ✓ entry `notify.py:40` with the objection and the quoted guard

3. **SC-3 Challenge fails**
   - **Given** the same finding, but the guard only covers one of two callers
   - **When** the prover picks the lens's claim, quoting the unguarded caller
   - **Then** the finding stays at its severity and gains a "Survived challenge" note naming the objection and why it failed
   - **Data before:** **Finding** (correctness, Should fix): "`user.email` may be None", `notify.py:40`*
   - **Walkthrough:**
     1. The adjudicator objects that `load_user` guards it
     2. The prover quotes `batch.py:77` calling `notify()` with a raw row that skips `load_user`*, and picks the lens's claim
   - **Data after:** **Finding** ✓ Should fix, unchanged; ✓ aside "Survived challenge: `load_user` guards one caller, but `batch.py:77` bypasses it"*

4. **SC-4 Fix replaced**
   - **Given** a finding whose suggested fix changes `<` to `<=` in a pagination loop
   - **When** the adjudicator rules fix wrong and the prover shows the original fix reads one row past the end on the last page while the replacement doesn't
   - **Then** the replacement becomes the recommendation and the original fix moves to a collapsed aside with the failing input
   - **Data before:** **Finding** recommendation: `<` → `<=` at `pager.py:31`*
   - **Walkthrough:**
     1. The adjudicator proposes clamping the end index with `min(end, total)`* instead
     2. The prover runs both fixes against a 10-row* table with page size 5*: the original fix reads row 11*, the replacement doesn't
   - **Data after:** **Finding** ✓ recommendation is the clamp; ✓ aside "Original fix `<=` reads past the end when total is a multiple of page size"; badge Fix replaced

5. **SC-5 Fix dispute inconclusive**
   - **Given** a fix disagreement where the prover can't produce an input that breaks the original fix
   - **When** the prover returns inconclusive
   - **Then** the original fix stays, with a "Survived challenge" note; the finding is not Disputed and posts normally
   - **Data before:** **Finding** (Should fix) with the lens's fix
   - **Walkthrough:**
     1. The adjudicator proposes a different fix
     2. The prover finds no input where the lens's fix fails, so it can't show both halves, and returns inconclusive
   - **Data after:** **Finding** ✓ lens's fix kept; ✓ "Survived challenge" note; ✗ not Disputed

6. **SC-6 Proven unreachable**
   - **Given** a `resilience` finding about an unhandled timeout in a code path only a test helper calls
   - **When** the adjudicator rules unreachable and the prover confirms no real entry point reaches it
   - **Then** the finding drops to Nit, labelled Unreachable, with the proof in an aside; it doesn't post by default
   - **Data before:** **Finding** (resilience, Should fix): "no timeout on fetch", `client.py:120`*
   - **Walkthrough:**
     1. The adjudicator rules unreachable: only `tests/helpers.py:9`* calls it
     2. The prover searches callers at `refs.head`, finds only the test helper, and picks the adjudicator's claim
   - **Data after:** **Finding** ✓ Nit; ✓ statement "Unreachable: only `tests/helpers.py:9` calls it"*; ✓ badge Unreachable

7. **SC-7 Issue dispute inconclusive**
   - **Given** an issue disagreement that turns on a config value the source doesn't set
   - **When** the prover returns inconclusive
   - **Then** the finding is Disputed with a "What would settle this" line, and posts only if triage selects it
   - **Data before:** **Finding** (safety, Must fix): "debug endpoint exposed"*
   - **Walkthrough:**
     1. The adjudicator objects: production sets `DEBUG=false`
     2. The prover finds no production config in the repo and returns inconclusive
   - **Data after:** **Finding** ✓ Disputed; ✓ "What would settle this: the deployed value of `DEBUG`"*; ✗ not preselected for posting

8. **SC-8 Severity change**
   - **Given** a Must fix finding whose wrong result is a cosmetic log line
   - **When** the adjudicator agrees the issue is real but rates it Should fix
   - **Then** the severity changes with no prover, and the reason shows in the aside

9. **SC-9 Root-cause merge**
   - **Given** `correctness` at `api.py:50` and `db` at `repo.py:210` both caused by one missing transaction
   - **When** the adjudicator groups them
   - **Then** the report shows one finding at the root-cause anchor, tagged with both lenses, at the stronger of the two severities
   - **Data before:** **Finding 1** (correctness, Should fix) `api.py:50`*; **Finding 2** (db, Must fix) `repo.py:210`*
   - **Walkthrough:**
     1. The adjudicator groups both under "writes not wrapped in a transaction"* anchored at `repo.py:210`*
   - **Data after:** **Finding** ✓ Must fix, `[correctness][db]`, `repo.py:210`*; ✗ separate `api.py:50` finding

10. **SC-10 Adjudicator fails**
    - **Given** a run where the adjudicator call errors or returns malformed output after one retry
    - **When** the coordinator writes the report
    - **Then** every finding stays as coordination left it, with no production statements; the summary and terminal digest carry a ⚠️ "not adjudicated" note; the run is not marked incomplete

11. **SC-11 Pack disables it**
    - **Given** a pack with `adjudicator: { enabled: false }`
    - **When** the review runs
    - **Then** no adjudicator or prover runs, and the summary says the run was not adjudicated and that policy turned it off

12. **SC-12 Diff-only run**
    - **Given** a reviewer-seat run with no source checkout
    - **When** the adjudicator runs
    - **Then** it writes statements from the diff; provers can quote only the diff, so most issue and unreachable disputes become Disputed and most fix disputes keep the original fix; every finding stays `verified: false`

13. **SC-13 Non-runtime findings**
    - **Given** a `conventions` finding and a `test-adequacy` finding
    - **When** the adjudicator writes statements
    - **Then** the conventions finding says `N/A: conventions` and the test-adequacy finding names the regression the missing assertion would let through
    - **Data after:** **Finding** (conventions) ✓ "N/A: conventions"; **Finding** (test-adequacy) ✓ "Would miss: refunds over the original charge amount being accepted"*

### Report surface

- Each finding touched by the adjudicator carries one badge: Survived challenge, Fix replaced,
  Unreachable, or Disputed.
- Checked and dropped is a collapsed section on every run, not only deep runs. Each entry has the
  anchor, the objection, and the prover's quote or repro.
- The summary and terminal digest carry one tally line, for example "Adjudicated 23: 15 agreed,
  3 dropped, 2 fixes replaced, 1 unreachable, 1 survived, 1 disputed, 2 merged".

## Scope and non-goals

- The adjudicator never adds a finding. It rules on and merges what the lenses found.
- It doesn't replace cross-family verification or the deep `_checker`.
- No cap on provers, and no sharding of the adjudicator.
- Triage controls, memory fingerprints, and posting approval gates are unchanged.
- Provers never prompt for their own execution consent.
- No pack setting for which paths count as production.

## Success criteria

All four are run by hand with live models, like today's smoke corpus.

1. **No real bug lost.** All five existing smoke cases (`correctness`, `safety`, `test-adequacy`,
   `db`, `scope`) still exit 0, and each planted bug survives adjudication at Should fix or higher
   with a production statement.
2. **A false positive caught.** A new case plants code that looks broken but is guarded elsewhere. It
   passes when the issue is absent from the findings or appears only under Checked and dropped, and
   fails if it appears as a postable Must or Should fix.
3. **A wrong fix caught.** A new case plants a bug whose obvious fix is wrong at a boundary. It passes
   when the finding is present and its recommendation contains a marker that only the correct fix has,
   named in that case's `expected.json`.
4. **Every finding has a statement.** A unit test confirms the renderer rejects an adjudicated report
   with a finding missing its production statement.

## Decisions Locked

**Fit with existing verifiers**
- Runs on every review; a pack can turn it off.
- Runs before cross-family verification, which checks what survives.
- In deep mode, runs after the `_checker` on confirmed and plausible findings.
- Opus by default regardless of escalation settings; `models.adjudicator` overrides.

**What an overturned finding becomes**
- Disproven issue: removed, listed in Checked and dropped with the proof.
- Replaced fix: the adjudicator's fix is the recommendation; the original sits in a collapsed aside.
- Failed challenge: original kept, with a "Survived challenge" note.
- Inconclusive issue or unreachable dispute: Disputed, can't post until triaged.
- Inconclusive fix dispute: original fix stays, "Survived challenge" note.
- Severity change: applied directly with a recorded reason.

**Proof standard for provers**
- Two neutral claims, randomized order, no model names or severities.
- A repro whenever execution is allowed and the code can run; a quote otherwise.
- One fresh prover per disagreement.
- A fix swap needs a failing input for the original and a passing showing for the replacement.
- Provers execute only under consent the run already has.

**Production-reachability statement**
- Production means reachable from a real entry point under real or default config, flagged paths
  included.
- Form: Common path / Edge case / Unreachable label plus a one-line trigger path.
- A proven unreachable finding drops to Nit, labelled Unreachable.
- Test lenses name the uncaught regression; other non-runtime findings say N/A.
- Shown on the report page and in posted comments.

**Scope, cost, and success**
- Judges and merges root causes; never adds findings.
- No prover cap.
- Success is the existing smoke corpus plus a planted false positive and a planted wrong fix.
- A failed adjudicator leaves a ⚠️ note and doesn't mark the run incomplete.
- Structure: one Opus pass over the whole list (approach A), over per-finding Opus and sharded passes.

## Industry Insights

- Stronger-model review rarely beats the stronger model alone, and cost 2.6 to 2.8 times as much
  ([arXiv 2610.15897](https://arxiv.org/abs/2610.15897)). The adjudicator earns its keep only if the
  smoke cases show it.
- Requiring a verifier to explain and repair raised its false-negative rate on correct code from
  26.2% to 73.2% ([arXiv 2603.00539](https://arxiv.org/pdf/2603.00539)). This is why a ruling alone
  never changes a finding.
- Anchoring metadata blocked 48% of corrections, and "disregard it" warnings didn't remove the effect
  ([arXiv 2608.25869](https://arxiv.org/abs/2608.25869)). Hence neutral A/B claims for provers.
- Ten reviewers unanimously endorsed a nonexistent OpenSSL vulnerability, and one empirical test
  removed it ([Refute-or-Promote, arXiv 2604.19049](https://arxiv.org/abs/2604.19049)). Hence repro
  first.
- Code-review judges said "true" on at least 85.5% of comments against a 63.8% base rate, and the best
  caught 37.7% of bad comments ([CRJudgeBench, arXiv 2609.37216](https://arxiv.org/html/2609.37216v1)).
- Listwise judging has position bias that varies by judge; stronger models stay more consistent as
  lists grow ([ACL IJCNLP 2025](https://aclanthology.org/2025.ijcnlp-long.18/)). Hence shuffled order.
- Batch filters should keep every finding when the judge call fails
  ([QASecClaw, arXiv 2605.01885](https://arxiv.org/pdf/2605.01885)).
- Sharding helped only when load exceeded judge capacity, and helped little where claims can be
  checked by reading ([arXiv 2608.06422](https://arxiv.org/html/2608.06422v1)).
- None of the surveyed tools (Anthropic Code Review, CodeRabbit, Bugbot, Greptile) has a judge that
  checks suggested fixes ([Claude Code docs](https://code.claude.com/docs/en/code-review),
  [CodeRabbit write-up](https://theaiengineer.substack.com/p/how-coderabbit-actually-works)).

Most of this evidence comes from general LLM-as-judge work, not code-review findings, so the success
criteria above are the real test.

## Deferred Ideas

- Shard the adjudicator by file cluster if real runs show one pass struggling with a long list.
- Run the adjudicator twice with different orders to measure position bias.
- A pack setting listing which paths count as production.
- `--stats` showing how often each lens is overturned, to tune noisy lenses.
- `[tech-spec]` Where adjudication results live in `report.json` (finding fields, `run.adjudication`,
  generalizing `run.deep.checked_and_dropped`), and how a root-cause merge interacts with memory
  fingerprints.

## Glossary

- **Adjudicator**: the Opus pass that rules on every finding.
- **Ruling**: the adjudicator's call on one finding: agree, issue wrong, fix wrong, or unreachable,
  optionally with a severity change.
- **Disagreement**: a ruling other than agree; each gets a prover.
- **Prover**: a fresh Sonnet agent that settles one disagreement against the code.
- **Verdict**: a prover's answer: Claim A, Claim B, or inconclusive.
- **Survived challenge**: the lens's version held up against the adjudicator's.
- **Disputed**: a disagreement no one could settle; the finding posts only if triage selects it.
- **Production statement**: the likelihood label plus a one-line trigger path, or a test-lens
  regression, or `N/A: <dimension>`.
- **Checked and dropped**: the collapsed report section listing findings removed by proof.
