# Graceful degradation

Every degraded path still produces a review; what changes is what the report can claim.
Name each degradation that applied in the Summary and under Assumptions.

| Situation | Behavior |
|---|---|
| No supported forge (unknown host with neither or both CLIs authenticated, Bitbucket, plain local changes) | The review runs fully. Delivery is the local report plus `report.json`; nothing posts. The Summary names `fallback_reason` or the detection reason. |
| For `--branch`: forge call fails, or no change request exists | `prepare_diff.py` falls back to a git diff and reports `fallback_reason`. `adversarial` skips because `has_description` is false. |
| For `--change`: forge call fails | The run stops with `diff_source_failed`; there is no git fallback. |
| `--local`, or a change request with an empty description | `has_description` is false, so `adversarial` skips; record it in the Summary. |
| Missing or thin description | Resolve intent once before fan-out. A declined prompt or non-interactive run uses the guess with an Assumption. `scope` still runs unless diff-only, and flags the description only for a change-request target. |
| Diff adds or modifies no comment lines | `comments` returns no findings after its first pass, without reading source. |
| No test files in the diff | `test-adequacy` and `tests` skip; if production source changed, `test-coverage` runs instead. |
| Code not locally runnable at `refs.head` (deps unavailable, baseline suite red, or a remote change not checked out) | The mutation probe is skipped; the test lenses use static reasoning and record it as an Assumption. |
| Mutation consent withheld | Static test reasoning and an Assumption; refusal is never an error. |
| Large diff | `prepare_diff.py` batches by file and never silently truncates. |
| The forge omitted a file's diff (GitLab does this for large files without setting `overflow`; GitHub drops the file's `patch`) | Recovered from local git using the change refs. Anything unrecoverable is listed in `diff_unavailable` and reported as not reviewed, never dropped silently. |
| No other repository is searchable for `cross-repo` | The lens degrades to local heuristics and says so in each finding's `assumptions`. |
| A mapped model is unavailable | The lens retries once on its built-in default tier; `run.models` and Assumptions name the model that ran. |
| A lens still fails | The report is marked incomplete and names the lens; it is never presented as clean. |
| Pygments not installed | Offered once in the preflight; if declined or the install fails, code outside the built-in languages renders uncoloured and the renderer warns (`highlighter: builtin`). |
| Headless, or no browser | Render with `--no-open`; the artifact path still prints. A failed auto-open is non-fatal and reports `opened: false`. Headless runs stop after the report and never post. |
| No matching local clone in reviewer seat | Ask before a shallow temporary clone; diff-only only after the user declines. |
| Diff-only source | Every finding stays unverified and the posted overview names the checks that could not run. `scope` is skipped and recorded in `run.dimensions_skipped`, because its separable-concern findings require source verification. |
| Deep execution disallowed (fork, untrusted author, unknown GitLab reviewer trust, or `diff-only`) | No consent prompt and no code execution. Area and contract finders inspect source/diff read-only; `run.deep` records the reason, and Assumptions and coverage name what was not reproduced. |
| Deep execution consent declined or tool/dependency setup fails | Continue read-only; name the affected area and reason in coverage. An unavailable OS sandbox uses the consented standalone worktree fallback with an explicit environment-only isolation warning, not a claim of OS enforcement. |
| Deep 80% finder-start cutoff reaches pending areas | Mark each unstarted area `unreached`; include its ID in `run.deep.unreached_areas` and ⚠️ coverage, set `run.incomplete: true` and `meta.verdict: "Incomplete review"`, and check collected claims before reporting. |
| Deep capacity estimate says the areas do not fit the budget | Interactive runs ask once whether to raise the budget, hunt only the top-priority areas, or continue. Headless runs hunt the top `fit_count` areas by `priority` and mark the rest `unreached` with `degraded_reason: "capacity"`. Those areas are named in `run.deep.unreached_areas` and the ⚠️ note "not hunted (over capacity)", and the report is incomplete. |
| Deep finder leaves hunks unexamined after follow-ups | The area counts as unreached; `run.deep.unexamined` maps it to the missing hunk ids, the ⚠️ coverage note names them, and the report is incomplete. |
| Deep run finishes complete but over its time budget | A neutral note, "Deep review exceeded its time budget (Xm of Ym)". The report is not marked incomplete on that account. |
| `--since <ref>` delta review | The diff is narrowed to changes after the ref and `run.since` records it. The run is report only: memory load, reconcile and save refuse it, both posting scripts refuse it, and the Summary says so. |
| Deep checker refutes a claim | Drop it from findings and keep its anchor and quoted reason in collapsed `run.deep.checked_and_dropped`. Do not expose unchecked candidates. |
| Deep checker can establish mechanism but not the external trigger | Keep `verification_status: "plausible"` with `what_would_confirm`, no invented `repro`, and block posting from both seats even if triaged to post. Confirmed findings can show the checker's own `repro` command/output. |
| Deep checker fails or reaches the deadline | Record its candidate ID/reason in `run.deep.checker_failures`, withhold that claim, and mark the report incomplete. A missing verdict without a declared failure is an input error. |
| Adjudication turned off by policy (`adjudicator: {enabled: false}`) | No adjudicator or prover runs and no finding carries a production statement. `run.adjudication` is `disabled` with reason "turned off by policy", and the Summary says the run was not adjudicated and that policy turned it off. |
| Adjudicator fails twice, or returns malformed rulings after one re-ask (including after the `sonnet` model retry) | Fail open: every finding stays as the merge left it, with no production statements. `run.adjudication` is `failed` with the reason, and the Summary and terminal digest carry a ⚠️ "not adjudicated" note. The report is not marked incomplete. |
| A prover fails or returns nothing usable | That finding is Disputed, with "Prover did not return; check the objection by hand." as what would settle it. It posts only if triage selects it, and a deep `plausible` finding still never posts. The other disagreements are unaffected. |
| Diff-only source and adjudication | The adjudicator writes statements from the diff and provers can quote only the diff, so most issue and unreachable disputes become Disputed and fix disputes keep the original fix. Every finding stays `verified: false`. |
| Provers without execution consent (no deep consent, no mutation-probe consent, or a repro the environment cannot run) | Provers settle disputes by quoting `path:line` code at `refs.head`; a repro that cannot run counts for neither side, and an argument with no quote is inconclusive. They never ask for consent of their own. |
| Ledger missing, corrupt, or from a future schema | Surface the warning and review independently; never overwrite an unreadable or future record. Markers in the authenticated identity's own notes still recover published-note identity on a new machine. |
| Posting identity unknown | Markers cannot be attributed, so treat every one as human context, warn, and repost rather than silently suppress. |
| Discussion cross-check unavailable | Continue the report and triage; block every write to the forge until a fresh cross-check succeeds. |
| Change fetch, identity, or head is incoherent | Stop. Never guess a seat or review an empty diff. |

There is no "lens not installed" degradation: every checklist ships with the skill, so a
lens is only ever absent because its run condition did not apply or policy skipped it.
