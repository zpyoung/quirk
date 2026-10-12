# Scenario Examples

The shared conventions for the optional data-state example on a logic-spec scenario. Both rubrics, [logic-spec.md](logic-spec.md) and [interactive-logic-spec.md](interactive-logic-spec.md), follow this one copy. It follows the approved [Conventions](../../docs/quirk/specs/2026-10-12-scenario-data-states/logic.md#conventions), [What an example is](../../docs/quirk/specs/2026-10-12-scenario-data-states/logic.md#what-an-example-is), [5](../../docs/quirk/specs/2026-10-12-scenario-data-states/logic.md#5-an-example-changes-with-its-scenario), and [8](../../docs/quirk/specs/2026-10-12-scenario-data-states/logic.md#8-later-stages-take-their-contract-from-the-then) contracts.

## What an example is

An example is an optional part of one scenario that shows its data, and the Then stays the contract. It has three parts:

- **Data before** lists the records the scenario touches, with only the values that matter to it.
- **Walkthrough** gives numbered steps from the When. Each step says who acts and shows the intermediate value.
- **Data after** shows the same records once the scenario finishes. It is the Then written as data.

The example is a checked restatement of the Then. Approving a scenario means the reviewer checked that the two agree, and when they disagree the Then stands and the example is fixed. Anything the example needs that the Then doesn't settle becomes a gap (`[ASK]`) for the reviewer, so an example never quietly sets policy.

## When to write one

Write an example wherever the scenario has data to show, in the same pass as the scenario itself. A scenario with nothing to show (a naming rule, a placement rule) carries none. Request/response scenarios (API shape, webhooks, CLI output) keep the same three labels: the walkthrough is the request or command, and Data after is the response or output.

## Conventions

The marks (`✓`, `✗`, `*`, `[ASK]`, `(a)`) are defined under [Mark syntax](#mark-syntax).

- Records are named in full and in bold: **Subscription**, **Charge 2 (queued)**, **Discount definition**.
- Lines are named after a product ("Coffee line"), never "line A".
- A title names a kind of thing ("Loyalty", "Welcome") and is reused for the same kind across scenarios. Each example states the values it needs, so one title can carry different values in different scenarios. There is no spec-level cast list.
- Every number has a label: `"Winback": $90.00 × 0.85 = $76.50`, `"Loyalty" took $10.00`.
- Steps say who acts: "The customer skips Charge 2", "An API client tries to add…".
- Product names and titles are always illustrative.
- Plain words only. Field and column names belong to the tech spec.

## Mark syntax

The marks are plain text in the source. The review page colours them, and `logic.md` keeps them as written.

- `**bold**` marks a record.
- `✓` marks a result and `✗` marks a rejection. Each mark covers the phrase up to the next `;` or the end of the line.
- A trailing `*` marks an invented value, picked to make the example concrete and not part of the rule, as in `$100.00*`.
- `[ASK: <question>]` marks a gap: something the scenario doesn't settle that the example can't show without guessing. Write `ASK` capitalised, with a colon and a space before the question, and the question cannot contain square brackets. The page and the renderer reject any other spelling as a malformed marker.
- `(a)` and `(b)` label branches when one scenario covers several outcomes.

**Never use single-asterisk emphasis inside an example.** A trailing `*` must never pair with an opener, so use plain words for emphasis.

## Where an example lives

In `logic.json`, an example is three typed parts on the scenario's `example` field, holding marked-up markdown: a `before` string, a `steps` list with one string per step, and an `after` string. In a markdown spec, and in the `logic.md` the renderer generates, the same text appears as three labelled sub-bullets under the scenario:

```markdown
1. **SC-15**
   - **Given** a $100 line with a 10% and a 15% line discount
   - **When** the charge is calculated
   - **Then** the line nets $76.50
   - **Data before:** **Charge 1**: Coffee line $100.00; "Loyalty" 10% off; "Winback" 15% off
   - **Walkthrough:**
     1. "Loyalty": $100.00 × 0.90 = $90.00
     2. "Winback": $90.00 × 0.85 = $76.50
   - **Data after:** **Charge 1**: ✓ Coffee line $76.50; "Loyalty" took $10.00; "Winback" took $13.50
```

A line break inside one part ends the line with two trailing spaces, because a lone newline collapses to a space on render.

## Keeping an example in sync

An example changes in the same edit as its scenario. When an edit rewrites the Then, whether it answers an `[ASK]`, takes a reviewer's update request, or lands as a post-approval amendment, rewrite the example in that edit too. The rewrite removes the `[ASK]` it answered. A Then and an example that were edited separately drift apart, and the reviewer approved the pair.

## Self-review check

Before the review gate, check that every example agrees with its Then, and that each open `[ASK]` is a question the design didn't already answer. When the design already answers it, put the answer in the Then and rewrite the example, so a reviewer is only asked what is genuinely open.

## Downstream stages

Requirements derive from the scenario text alone, and a value marked `*` is never an expected value. Claude ignores the example when it derives requirements, so a fix to an example after approval goes through the scenario's own amendment or reopen path.
