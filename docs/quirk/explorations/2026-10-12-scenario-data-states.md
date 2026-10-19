> 🧭 EXPLORATION — not a spec. No locked decisions; nothing here is build-ready.

# Exploring: data-state examples for logic-spec scenarios

**Date**: 2026-10-12

## Framing

A logic-spec scenario states a rule as Given / When / Then. That's precise enough for the person who wrote it, but a reader still has to picture the records and run the numbers in their head. A data-state example does that work for them: it shows the records before the scenario, each step with its intermediate values, and the records after.

This came out of a real review. After a subscription-discount logic spec was approved, its 68 scenarios were exported to a spreadsheet and three data-state columns were added by hand. Writing them surfaced four questions the approved Given / When / Then had skipped over. One example: once a "first 3 charges" discount runs out, does it stay attached to the subscription or get removed? Reviewers also found the examples much faster to check than the prose.

The question for brainstorming is whether, and how, the logic-spec flow should produce these examples itself.

## What a data-state example is

Three parts, attached to one scenario:

- **Data before:** the records the scenario touches, with only the values that matter to it.
- **Walkthrough:** numbered steps from the When, showing each intermediate value.
- **Data after:** the same records once the scenario finishes. This is the Then written as data.

### Example: two percentage discounts compound

Scenario: *Given a $100 line with a 10% and a 15% line discount, when the charge is calculated, then the line nets $76.50.*

| Data before | Walkthrough | Data after |
|---|---|---|
| **Charge 1**<br>Coffee line: $100.00, quantity 1<br>Line discount "Loyalty": 10% off<br>Line discount "Winback": 15% off | 1. "Loyalty": $100.00 × 0.90 = $90.00<br>2. "Winback": $90.00 × 0.85 = $76.50 | **Charge 1**<br>Coffee line: $76.50<br>"Loyalty" took $10.00<br>"Winback" took $13.50 |

### Example: a limited discount runs out

Scenario: *Given a subscription with a line discount limited to the first 3 charges, when three charges have processed and the next one is generated, then the fourth charge doesn't include it.*

| Data before | Walkthrough | Data after |
|---|---|---|
| **Subscription**<br>Line discount "Welcome": 10%* off, first 3 charges<br>Uses left: 3 | 1. Charge 1 processes → uses left 2<br>2. Charge 2 processes → uses left 1<br>3. Charge 3 processes → uses left 0<br>4. Charge 4 is generated | **Charge 4**: Coffee line has no line discounts<br>**Subscription**: "Welcome" uses left 0<br>[ASK: does "Welcome" stay on the subscription once its uses run out, or get removed?] |

### Example: one scenario, two branches

Scenario: *Given a shared discount definition at 10%, when the merchant edits it to 15%, then the edit is ignored once the definition has been used, and allowed while it hasn't.*

| Data before | Walkthrough | Data after |
|---|---|---|
| **Discount definition** "Loyalty": 10% off<br>(a) used 4* times<br>(b) never used | 1. The merchant changes "Loyalty" to 15%<br>(a) The request succeeds, but the change is ignored<br>(b) The change is saved | (a) "Loyalty" stays 10%<br>(b) "Loyalty" is 15%; queued charges pick it up on their next regen |

## Conventions that made them readable

The first draft used IDs (`C1 line A D1 10% amount 4.00`). Reviewers found it hard to follow, so the second draft switched to these conventions:

- **Records are named in full:** "Subscription", "Charge 2 (queued)", "Discount definition".
- **Lines are named after a product:** "Coffee line", not "line A".
- **Discounts have titles:** "Loyalty", "Sorry", "Welcome". The same title is reused for the same kind of discount across scenarios.
- **Every number has a label:** `"Winback": $90.00 × 0.85 = $76.50` and `"Loyalty" took $10.00`, not bare figures.
- **Steps say who acts:** "The customer skips Charge 2", "An API client tries to add…".
- **Invented numbers are marked `*`.** Where the scenario doesn't give a value, one is picked to make the example concrete, and the mark says it isn't part of the rule. Product names and discount titles are always illustrative.
- **Branches are labelled (a), (b)** when one scenario covers several outcomes.
- **`[ASK: …]` marks a gap,** a detail the scenario doesn't settle that the example can't show without guessing.
- **Not every scenario changes data over time.** For API-shape, webhook and feature-flag scenarios, the walkthrough is the request and *Data after* is the response or payload.

In the spreadsheet, colour carried part of the meaning: records in blue bold, step numbers in purple, results in green bold, rejections in red, illustrative values in grey italic, and `[ASK]` in underlined amber. *Data before* had a grey background and *Data after* a green one.

## What they were good for

- **Finding gaps.** Writing *Data after* forces a concrete answer. Four of the 68 scenarios had a question the prose hadn't answered:
  - what happens to an expired discount;
  - what happens to a discount left off because the currency changed;
  - the format of a "created by" field;
  - a timing mechanism that had been deferred.
- **Checking arithmetic.** Calculation scenarios (stacking, rounding, clamping, tax bases, currency conversion) became easy to verify line by line.
- **Onboarding readers.** People who weren't in the review could follow a scenario without the surrounding prose.

## Costs and risks seen

- **Invented values can read as spec.** The `*` mark and the "names are illustrative" note are what keep this from happening. Without them, a reader could take an example value as a requirement.
- **Field names leak in.** It's tempting to write `uses_remaining` or `source_type`, but at logic-spec stage those names aren't decided. The examples worked better in plain words.
- **Effort is uneven.** Calculation scenarios almost write themselves from the Given / Then. Integration scenarios (external payloads, sync timing) took real effort and some could only be partly worked.
- **They can drift.** When a scenario is rewritten during review, its example has to be rewritten too, or it contradicts the rule.

## Questions for brainstorming

- **When are they written?** Options include alongside each scenario at stage 1, only after scenarios are approved, or on request.
- **Who writes them, and how are they checked?** Is a wrong example a scenario dispute, or something separate?
- **Every scenario, or only some?** Possible cut-offs: calculation and state-change scenarios only, or any scenario where the reviewer asks.
- **Where do they live?** Options include a field on each scenario in `logic.json`, a rendered block in `logic.md`, or a view in the review page.
- **How are `[ASK]` gaps routed?** Should a gap become a reviewer question, a blind spot, or a new scenario?
- **What happens on rewrite?** How does an example stay in sync when its scenario is rewritten or reopened?
- **How does the review page render them?** Does the colour coding carry over, and does an example count toward approving the scenario?
