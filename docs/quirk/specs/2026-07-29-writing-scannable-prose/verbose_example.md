## Description

A credit account pinned by plan `02` holds a foreign-currency promise plus the single `locked_exchange_rate` that realizes it. Nothing stopped a later credit-add from landing on that account at a different rate, which would leave one account holding two rates and no way to say which one redemption honors.

This MR adds a guard to `CreditService.create_credit_adjustment` that rejects any **positive credit** to a pinned account with **422**, except the account's own opening row and a reversal of its own debit. Anything else must create a new account.

The guard runs on **both** write paths onto a pinned account's rate. Besides `create_credit_adjustment`, plan `02`'s grant path (`_create_credit_account`) writes the opening row through the model-level `create_adjustment` directly — that is the write that *establishes* a pin, and it now runs the guard first rather than being the one write it never sees.

**Inert on deploy:** the guard only reaches its decision clauses when `credit_account.presentment_currency_code` is non-NULL. Its only writer is plan `02` (!35312), now **merged to `stage`** — but that writer is itself gated behind `multicurrency_credit_issuance_enabled`, enabled for **zero stores**, so no row can acquire a pin today. A production check on 2026-07-28 found **zero rows** with it set. No redemption, debit, or unpinned-account behavior changes.

> 📍 Rationale for the non-obvious decisions lives in the code where it applies — the whitelist framing and clause ordering, the deliberate absence of a `flush()`, why `populate_existing()` is required, why the reversal check loads the full ORM entity, and why the schema and controller were left alone.

## Impacted Areas in Application

- Credit adjustment creation — internal + public `POST /api/credit_accounts/{id}/credit_adjustments`
- `CreditService.create_credit_adjustment` and plan `02`'s grant path, and every internal caller of them (redemption, refunds, gift issuance, rewards)
- `utils/numbers.to_comparable_decimal` — new shared helper, called only by the guard today
- No schema, migration, response-shape, or redemption change

## Related Issues

https://recharge.atlassian.net/browse/PRO-271

Follows !35312 (plan `02`, FX lock at grant time), which has **merged to `stage`**. This branch is rebased onto that, so plan `02`'s grant path is in the base and the two are tested together here. Plan `02` creates the pinned accounts this guard protects, so **this must land before `multicurrency_credit_issuance_enabled` is turned on for any store**.

## Decision Table

Evaluated in order, as the first statement inside the existing `locked_route_context` + `begin()` block, on both `create_credit_adjustment` and plan `02`'s grant path. Order is part of the contract: clause 1 runs before the pin re-read so redemption debits and zero-amount rows never pay for a row lock.

| Clause | Condition | Outcome |
| --- | --- | --- |
| 1 | Effective `adj_type` is not a credit | allow — `decision=not_credit` |
| 1 | `amount <= 0` | allow — `decision=nonpositive` |
| 2 | Account has no `presentment_currency_code` | allow — `decision=unpinned` |
| 3 | Asserted currency or rate disagrees with the pin | **reject** |
| 4 | Ledger is empty **and** `amount` matches `initial_value` (exactly, or at ledger precision) | allow — `decision=opening` |
| 5 | Reverses a debit this same account holds, without exceeding it in total | allow — `decision=reversal` |
| 6 | Everything else | **reject** |

A **whitelist, not a blacklist** — an unanticipated route lands in clause 6 by default, which is the safe direction for money.

Three details that are load-bearing rather than incidental:

- **Clause 1 resolves the effective `adj_type` the way the writer will.** `create_adjustment` defaults a missing/falsy `adj_type` to a credit when `amount >= 0` (`credit_adjustment_model.py:466-467`). Reading `data["adj_type"]` naively let a caller omit the field and walk straight past the guard.
- **Clause 2 re-reads from the primary under `FOR UPDATE`**, never from the replica-sourced DTO the caller already has. A just-pinned account can still read back unpinned on the replica.
- **Clause 3 checks what will actually be persisted**, not just the `transaction_currency_details` parameter. `create_adjustment(**data)` accepts `transaction_currency_code` / `transaction_exchange_rate_used` directly, so rate fields placed in `data` bypassed an earlier version of this check.

## Known Limitation — the row lock is inert, and that is pre-existing

**`SELECT ... FOR UPDATE` does not serialize anything on `CreditService`'s session.** Probed directly inside `db_session.begin(subtransactions=True)`: MySQL reports `@@autocommit = 1` and **zero** rows in `information_schema.innodb_trx`, while SQLAlchemy reports `in_transaction = True` — which is why this has gone unnoticed.

Cause: `RoutedWorkerSession.get_bind()` (`database.py:929-935`) resolves the default bind through `get_db_engine()` with no `isolation_level`, and that argument defaults to `"AUTOCOMMIT"` (`database.py:889`). Only `NewRoutedWorkerSession` requests `READ COMMITTED`, and `CreditService` does not use it.

**Not introduced here** — before this MR there was no guard at all. But it is wider than credits: `create_adjustment`'s own `ending_balance` lock (`credit_adjustment_model.py:455`) rides the same session class and bind, so that protection is very likely inert too. Escalated separately for DBA review.

What this costs the guard: two *concurrent* first-credits onto the same brand-new pinned account can both pass the opening-row exemption. Single-threaded behavior — the KAIZEN #6 merchant scenario and effectively all real traffic — is correct and unaffected.

`test_create_credit_adjustment_concurrent_opening_row_exactly_one_wins` races that exact window and is marked **`xfail(strict=True)`** with the reasoning inline. Strict means it flips to a hard failure the moment isolation is fixed. **When that lands, delete the marker, not the test.**

## Deliberate Non-Changes

Each is annotated in the file it applies to, because the absence is the decision:

| Site | Why nothing changed |
| --- | --- |
| `credit_adjustments_schema.py` | No currency/rate field added. An API top-up carries no rate evidence, so the service can never verify one as same-rate — adding a field would create a claim the guard would then have to validate rather than reject. |
| `credit_adjustments_controller.py` | No `try`/`except`. `SingleRatePinnedAccountError` subclasses `UnprocessableError`, which `@app.errorhandler` already renders as a 422 with the messages payload. Mapping code here would be dead weight. |
| `_load_pinned_account_for_update` | No `flush()` before the locking read. Under AUTOCOMMIT a flush **durably commits** whatever else is pending on the caller's session — a broad, reachable loss (redemption-revoke and checkout hold pending objects across this call) traded against a narrow hypothetical one no caller performs today. Re-adding the flush is the regression. |
| Clause 3 rate comparison | `credit_adjustment.transaction_exchange_rate_used` is `DECIMAL(12,6)` against a `DECIMAL(20,10)` pin, so a >6dp rate passes the clause and persists rounded. Ruled low: `locked_exchange_rate` is what redemption uses and is untouched — the adjustment column records what was used, it is not a second authority. Documented for plan `02`. |

## Interaction With Plan `02`'s Two-Precision Grant

Worth calling out, because it is the non-obvious part of wiring the guard into the grant path.

Plan `02` stores a converted grant at two precisions on purpose: `credit_account.initial_value` keeps the conversion's full `DECIMAL(12,6)`, while the opening ledger row keeps the 2-decimal amount that can actually be spent. Its own `recurring_conversion` test case is the example — EUR 20 at a rate of 3 gives `6.666667` on the account and `6.67` in the ledger.

Clause 4 (`_is_own_opening_row`) matched the credited amount against `initial_value` by exact equality. Routing the grant path through the guard with that unchanged makes **the account's own opening row fail its own exemption** on any conversion that does not land on a whole cent — it falls through to clause 5, finds no reversal reference, and 422s. Verified: with the guard wired in and clause 4 untouched, `recurring_conversion` fails with `single_rate_guard_reason=reference_type_not_reversal`.

Clause 4 now accepts the ledger-precision rounding of `initial_value` as well as exact equality. That widens the exemption by exactly one additional amount, still only on an empty ledger.

## Spec Deviation

`tech.md` declares the reversal check `-> bool`. It returns `Optional[str]` instead, because the same document requires the rejection log to distinguish the four reversal failure modes — which a `bool` cannot carry. Named `_own_debit_reversal_failure_reason` so the inverted truthiness reads correctly; the call site tests `is None` explicitly. Caller-visible behavior is unchanged: one exception type, no new inputs accepted.

## How to QA

Requires a pinned credit account. Either run plan `02`'s flow on a stage store with `multicurrency_credit_issuance_enabled`, or set the three columns directly on an existing account:

```sql
UPDATE credit_account
SET presentment_currency_code = 'EUR',
    presentment_initial_value = 20.00,
    locked_exchange_rate = 1.1000000000
WHERE id = <id> AND store_id = <store_id>;
```

Against `POST /api/credit_accounts/<id>/credit_adjustments`:

1. **Top-up rejected.** Post `{"amount": "100.00", "type": "credit"}` to the pinned account (ledger non-empty). Expect **422**:
   ```json
   {"errors": {"credit_account_id": ["This credit account is pinned to EUR and cannot accept additional credit; create a new credit account instead."]}}
   ```
   Confirm it is a **422, not a 500** — the guard raises a well-formed `UnprocessableError`. Note the error keys on `credit_account_id`, not `amount`: no amount would have worked, so a client must not retry smaller.
2. **Debits unaffected.** Post a debit to the same account → **201**.
3. **Zero amount unaffected.** Post `amount: 0` → **201**.
4. **Own opening row allowed.** On a *fresh* pinned account with an empty ledger, post a credit equal to `initial_value` → **201**. Post one that differs → **422**.
5. **Own debit reversal allowed.** Take the debit from step 2 and post a credit with `reference_type: "credit_adjustment"`, `reference_id: <that debit's id>` → **201**.
6. **Foreign reversal rejected.** Same shape, but `reference_id` pointing at another account's debit, or at a credit row, or omitted entirely → **422**.
7. **Unpinned unchanged.** Repeat 1–6 against an account with `presentment_currency_code IS NULL` → all succeed exactly as before.

## Post Deploy Monitoring

**No signal change is expected.** With zero pinned accounts, the guard returns before it ever reaches a pinned account, so it emits nothing at all.

The guard logs only when it actually acts on a pinned account — the pass-through paths are silent, so log volume stays at zero until pinning is enabled:

- `"Allowed credit adjustment on pinned single-rate account"` (INFO), with `single_rate_guard_exemption` ∈ `{opening_row, own_debit_reversal}` — the two writes the guard permits.
- `"Rejected credit adjustment on pinned single-rate account"` (WARNING) — the merchant-impact signal. A sustained rise once pinning is on means a caller is routing top-ups to pinned accounts instead of creating new ones.

**Any** of these before `multicurrency_credit_issuance_enabled` is turned on means an account is pinned that should not be — investigate before dismissing.

The rejection log carries `single_rate_guard_reason` (the specific reason) alongside `single_rate_guard_reason_category`, which pre-splits operator error from an internal defect so a query does not have to hardcode the reason list:

- **`reason_category=operator`:** `rate_disagreement`, `reference_type_not_reversal`, `missing_reference_id`, `reference_amount_exceeds_debit`
- **`reason_category=internal`:** `reference_id_not_coercible`, `reference_id_not_found`, `reference_owned_by_other_account`, `reference_not_a_debit`, `reference_amount_not_comparable`

`reference_amount_exceeds_debit` is the newest and the one most likely to appear first: clause 5 now caps the *running total* credited back against a referenced debit at that debit's magnitude, rather than accepting any amount that cites it. Partial reversals stay legal and repeatable (`revoke_credit_redemption` and the recharge-credits gateway both pass a smaller explicit amount) — only the sum is bounded.

The log also carries `credit_account_id` (always the *rejected* account, not the service's bound one), `presentment_currency_code`, `attempted_amount`, and `reference_type`.

Also watch:

- **422 rate on `POST /credit_accounts/{id}/credit_adjustments`** — should be flat until pinning is on.
- **500s on the same endpoint** — the guard should never produce one. Two paths that previously could were closed: a NULL `initial_value`, and a non-numeric `transaction_exchange_rate_used` reaching `Decimal(str(...))` as an uncaught `InvalidOperation`. Both now fail closed to the guard's own 422.
- **ERROR-level volume on this endpoint, not just WARNING.** Every API-surfaced rejection emits
  **two** log lines: the guard's structured `WARNING` above, then a bare
  `app.logger.error("API 422 Error URI: ...")` from the generic `UnprocessableError` handler
  (`utils/error_handlers.py`), which carries no clause and no correlation id. This is pre-existing
  behavior for every 422 in the repo, not introduced here — but it means an on-call watching ERROR
  volume on `POST /credit_accounts/{id}/credit_adjustments` will see guard activity at a severity
  this plan would otherwise not lead them to expect. Correlate on the structured WARNING, not the
  ERROR count.
- **p99 latency on that endpoint and on charge-pay-using-credits.** Clause 2 adds one indexed primary-key point read on `credit_account` for every *positive credit* adjustment, on all accounts, pinned or not. That is the one part of this MR that is not inert. It takes no real lock (see the isolation limitation above), so there is no added contention risk — only the round trip.

## Post Deploy Action

- [ ] Link the session-isolation escalation ticket here once filed. **Fixing it is a precondition for plan `02` enabling pinning for any store** — the concurrent-first-credit window is unprotected until then.

No flag gates this guard directly, and deliberately so: a separate flag would allow a state where accounts are pinned but unguarded, which is worse than either extreme. The operational kill switch is plan `02`'s `multicurrency_credit_issuance_enabled` — disabling it stops new pins, which keeps this guard inert.

## Risk Assessment

:green_circle: **LOW** — major severity, remote likelihood.

- **Severity: Major.** Credits participate in charge payment collection and refunds, so a wrongful rejection would block merchant credit issuance. Not Critical: the guard cannot reject a debit or a redemption, and the write path itself is untouched.
- **Likelihood: Remote.** Narrow, single-purpose diff over a well-understood path. The decision clauses are unreachable on every production account today (zero rows have `presentment_currency_code` set), 57 net-new tests cover every clause, both exemptions, both write paths onto a pin, and the exception's own attributes, with each rejection reason asserted individually. The only always-on change is one indexed point read.
- **High-risk files:** none. `services/credit.py` is not on this repo's CLAUDE.md high-risk list (`charge.py`, `charge_pay.py`, `purchase_item.py`, `regen.py`). Monitoring, QA, and coverage are included above regardless, since this is a money path.
- **Risk reduction considered:** a dedicated beta flag was rejected for the reason in Post Deploy Action. Log-only mode is effectively already in place — with zero pinned accounts the guard returns before it can act, so it is silent by construction. The diff is single-concern and not worth splitting further.

## Test Coverage

- **57 net-new test cases** in `test_credit_service.py` (one `xfail(strict=True)`), plus **3 pinned-account cases** split into their own API test. Includes direct unit tests for the two pure functions (`_effective_rate_assertion`, `_rate_details_match_pin`) and the exception's `credit_account_id` / `presentment_currency_code` contract. **No existing expectation edited**; three near-identical rate-coercion cases were merged into one parameterized test.
- **31 net-new cases** in `tests/utils/test_numbers.py`, covering `to_comparable_decimal` directly.
- **The three touched test files: 275 passed, 1 xfailed, 0 failed.**
- **Affected-set gate — 13 test paths reachable from `create_credit_adjustment` / `create_refund_adjustment`** (all of `tests/services/credit/`, `tests/api/credit_adjustments/`, `tests/api/credit_accounts/`, `tests/api/gift_process/`, plus gift service, purchase-delete, customer-credit-summary, charge-pay-using-credits, the recharge-credits payment gateway, refund service, credit-expiration job, credits-limit-redemption monitors, and `test_issue_credit_node.py`): **2227 passed, 1 xfailed, 4 skipped** (path set widened to include `tests/services/currency/`, `test_credit_accounts_schema.py` and `tests/utils/`). The 3 failures in `tests/utils/test_auths.py` are pre-existing Jinja `TemplateNotFound` errors, reproduced identically on a pristine `origin/stage` worktree.

Covered: all six clauses; both exemptions; every rejection reason individually; rate assertions arriving via `transaction_currency_details` *and* directly in `data`, including the precedence between them; `Decimal`/`str`/`float`/differently-scaled rate equality; float opening amounts; NULL `initial_value`; zero-amount and debit pass-through; missing and `None` `adj_type`; a stale-replica pin; a caller's uncommitted debit surviving the guard; and the API-level 422 body.

Two notes on test strength, since they were earned the hard way:

- The concurrency test originally used `time.sleep`, which `tests/conftest.py:247` patches to a no-op repo-wide — so it ran sequentially and would have passed against a guard with no lock at all. It now uses an unpatched wait and discriminates on whether the second thread got past clause 2 while the first held the row lock, which is deterministic whether or not locking works. Verified `xfailed` on 5 consecutive full-suite runs and 5 in isolation, never XPASS.
- Two session-isolation tests can't rely on data visibility: `config/test.json` points the primary and replica credit profiles at the **same** database, and AUTOCOMMIT commits every flush. Both now assert on **mechanism** instead, and each was verified to fail against the actual regression it guards.

**Coverage stat diff:** not included. CI cannot produce one pre-merge (`coverage py` is gated on `commit_on_feature_branch`), and a local measurement is available on request.

## Review Feedback Addressed

### Round 1 — 27 review notes (`ca9104de13`)

All non-blocking. Applied as code changes:

| Feedback | Change |
| --- | --- |
| Docstrings and comments carry review-transcript analysis | Trimmed throughout `credit.py`. The deliberate-non-change blocks in `credit_adjustments_controller.py` and `credit_adjustments_schema.py` are removed outright. |
| "What's all this clause stuff / what is a reason category" | Dropped the clause numbering from prose; the log facet is now `single_rate_guard_reason` (it holds a reason string, not a number) and `reason_category` has a one-line definition where it is set. |
| `_rate_details_disagree_with_pin` reads inverted | Renamed to `_rate_details_match_pin`, returning True when they match. |
| Are the statsd counters useful? | Replaced. The six `single_rate_guard.total` increments are gone; the two allowed exemptions now log at INFO and rejections already logged at WARNING. Counter-tag tests removed with them. |
| Should the Decimal coercion helper live in a utility file? | Moved to `utils/numbers.to_comparable_decimal`. |
| The `checkout_charge_controller` fix targets pre-existing breakage | Reverted out of this MR. The guard can still mask an original exception during checkout cleanup; that is pre-existing and tracked separately. |
| Tests reference tickets and plan numbers | Removed from test docstrings and the section header. |

**Deferred — "keep 6dp accuracy everywhere."** The clause-4 widening stays for now. `credit_adjustment.amount` is `DECIMAL(12,6)`, so the column could hold it, but the downstream is not 6dp-tolerant: `CurrencyConversionService.format_and_convert_currency_with_rate` ends in `round(Decimal(amount), 2)` so every conversion is forcibly 2dp, and the non-multi-currency redemption branch in `charge_pay.py` assigns `transaction_amount = min(remaining_amount, available_balance)` — a 6dp balance would flow unrounded into a charged amount. `PriceField` also serializes at 2 places. Making the ledger 6dp is a plan `02` change with a real blast radius, not a fix inside this MR.

### Round 2 — team code-comment standard (`9f91db2563`)

Comments only, no behavior change, applied against the standard from [kai !207](https://gitlab.rechargeapps.net/engineering/kai/-/merge_requests/207) (`plugins/kai/references/code-comments.md`).

| Violation | Fix |
| --- | --- |
| Four section banners in the guard test section | Removed |
| Invented "clause 2/3/5" vocabulary, 12 places | Replaced with the method names it stood for, in docstrings and assertion messages. It had already been dropped from `credit.py`, so the tests were naming something that no longer existed. |
| Stale cross-file citations (`credit.py:1750`, `:1287-1292`, `database.py:929-935`) | Dropped; cite symbols instead |
| Local-only doc reference, temporal framing | Removed |
| Three-line inline comments | Trimmed to two |

Multi-line comments covering thread and mock wiring in the test files are deliberately kept — the standard makes test code more permissive for exactly that, and the rot rules (no ticket refs, no flag refs, no "currently") still hold there. Source docstrings are also unchanged: the standard caps *inline* comments, while doc comments state intent and are encouraged.

### Round 3 — utility coverage (`d605996a1c`)

`to_comparable_decimal` had no direct tests. Added 31 cases: numeric equality across Decimal/int/string, the float-through-`str()` behavior the helper exists for, scale independence, the `bool` rejection, every non-comparable input, and never-raises.

Writing them surfaced a defect: **`NaN` and `Infinity` survived the coercion** and reached callers as a Decimal, contradicting the docstring's promise of `None`. Both are now rejected. Every guard call site already failed closed on them by accident — `Decimal("Infinity") == Decimal("1.10")` is False, and the reversal cap treats infinity as exceeding any debit — but that was luck rather than design.

### Reviewer guidance on the diff

Ten inline notes are posted on the diff itself, so the non-obvious decisions are explained where they live rather than here: why a `FOR UPDATE` that takes no real lock is still correct, why clause 4 accepts two amounts, why the reversal cap bounds a running total instead of demanding exact equality, why `reference_id` is normalized in Python (with the prod `EXPLAIN` numbers), why the guard is called on the grant path, and why gift issuance gets its own handler.

Each of the three test files also carries a summary note at the top of its diff, listing every test added or modified in one line each — start there if you want to scan the coverage rather than read it.