# Data-state examples for logic-spec scenarios

**Status:** Approved. Tech spec: requested

Logic-spec scenarios can carry a data-state example: the records before, a step-by-step walkthrough,
and the records after. It applies to both spec formats and the interactive review page. Source
exploration: [2026-10-12-scenario-data-states.md](../../explorations/2026-10-12-scenario-data-states.md).

## Conceptual model

A scenario's Given / When / Then is precise enough for its author, but a reader still has to picture
the records and run the numbers in their head. An example does that work for them. Writing one also
forces a concrete answer to anything the scenario left open. When this was tried by hand on an approved
68-scenario spec, the examples turned up four questions the approved scenarios had never answered.

### What an example is

An example is an optional part of one scenario, in three parts:

- **Data before** lists the records the scenario touches, with only the values that matter to it.
- **Walkthrough** gives numbered steps from the When. Each step says who acts and shows the intermediate value.
- **Data after** shows the same records once the scenario finishes. It is the Then written as data.

Request/response scenarios (API shape, webhooks, CLI output) keep the same three labels. The
walkthrough is the request or command, and Data after is the response or output.

**The Then is the contract; the example is a checked restatement of it.** Approving a scenario means
the reviewer checked that its example agrees with the Then. When they disagree, the Then stands and
the example is fixed. Anything the example would need that the Then doesn't settle becomes a gap for
the reviewer, so an example never quietly sets policy.

### Conventions

These rules come from the hand trial, where a first draft written with IDs (`C1 line A D1 10%`) was
hard to follow. Both rubrics follow one shared copy of them.

- Records are named in full and in bold: **Subscription**, **Charge 2 (queued)**, **Discount definition**.
- Lines are named after a product ("Coffee line"), never "line A".
- A title names a kind of thing ("Loyalty", "Welcome") and is reused for the same kind across
  scenarios. Each example states the values it needs, so one title can carry different values in
  different scenarios. There is no spec-level cast list.
- Every number has a label: `"Winback": $90.00 × 0.85 = $76.50`, `"Loyalty" took $10.00`.
- Steps say who acts: "The customer skips Charge 2", "An API client tries to add…".
- `✓` marks a result and `✗` marks a rejection.
- A trailing `*` marks an invented value, picked to make the example concrete. It is not part of the rule.
  Product names and titles are always illustrative.
- `(a)`, `(b)` label branches when one scenario covers several outcomes.
- `[ASK: …]` marks a gap: something the scenario doesn't settle that the example can't show without guessing.
- Plain words only. Field and column names belong to the tech spec.

On the review page the marks map to colour. Records are blue bold, step numbers purple, `✓` phrases
green bold, `✗` phrases red, `*` values grey italic, and `[ASK]` amber underlined. Data before sits
on a grey background and Data after on a green one. In `logic.md` the marks stay plain text.

### Where an example lives

In `logic.json`, an example is three typed parts holding marked-up markdown: a `before` string, a
`steps` list with one string per step, and an `after` string. In a markdown spec, and in the
`logic.md` the renderer generates, the same text appears as three labelled sub-bullets under the
scenario:

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

## Data flow

**Markdown specs.**

1. Claude writes `logic.md`, giving each scenario with data to show an example in the same pass.
2. Self-review checks that every example agrees with its Then, and that each open `[ASK]` is a question
   the design didn't already answer.
3. At the review gate Claude lists every open `[ASK]` with its scenario.
4. Each answer goes into the scenario's Then, or becomes a new scenario. Claude rewrites the example
   to match, which removes the `[ASK]`.
5. The user approves. Later amendments rewrite an example in the same amendment as its scenario.

**Interactive specs.**

1. Claude writes stage-1 `logic.json` with an example on each scenario that has data to show.
2. On the page, rows carry an Example token, plus an Open question token while an `[ASK]` is open.
   Clicking any row opens the focus dialog, which shows the example in three columns.
3. The reviewer decides each scenario. An open `[ASK]` or a wrong example is answered through Update.
   Picking a different outcome on a scenario with an example also becomes an update. Claude rewrites
   the Then and the example together, and the scenario returns for a fresh decision.
4. The stage-1 fold refuses while an approved scenario's example has an open `[ASK]`. Otherwise it
   pins each scenario's hash, and the hash covers the example.
5. Derivation reads scenarios only. Fixing an example after the stage-1 sign-off goes through the
   existing scenario dispute, reopen, and re-approve path.
6. The final fold generates `logic.md` with the same sub-bullets as a markdown spec.

## Behavior & scenarios

Scenarios that walk through review state changing carry an example in the format this spec defines.

### 1. Claude writes an example for every scenario with data to show

1. **1.1**
   - **Given** a scenario that computes or changes records
   - **When** Claude writes the spec, in either format
   - **Then** the scenario carries an example, written in the same pass as its Given / When / Then
2. **1.2**
   - **Given** a scenario with a concrete input and output, such as an API request or a CLI command
   - **When** Claude writes it
   - **Then** its example keeps the three labels, with the request or command as the walkthrough and
     the response or output as Data after
3. **1.3**
   - **Given** a scenario with nothing to show, such as a prose behavior or a visibility rule
   - **When** Claude writes it
   - **Then** it has no example and no note explaining the absence

### 2. Examples follow the shared conventions

1. **2.1**
   - **Given** a value the scenario doesn't state, such as a discount's percentage
   - **When** Claude needs one to make the example concrete
   - **Then** it picks one and marks it `*`
2. **2.2**
   - **Given** a choice the Then doesn't settle, such as the rounding point, whether discounts
     compound or add, or whether records the example doesn't list stay unchanged
   - **When** the walkthrough would need that choice
   - **Then** Claude writes an `[ASK]` instead of choosing
3. **2.3**
   - **Given** a scenario that covers several outcomes
   - **When** Claude writes its example
   - **Then** the outcomes are labelled `(a)`, `(b)` in every part that differs
4. **2.4**
   - **Given** a concept with an obvious column name, such as remaining uses
   - **When** Claude writes it into an example
   - **Then** it uses plain words ("Uses left"), never the field name

### 3. The Then is the contract

1. **3.1**
   - **Given** an example that disagrees with its Then
   - **When** Claude or the reviewer notices
   - **Then** the Then stands and the example is rewritten to match it
2. **3.2**
   - **Given** a reviewer who spots a wrong example on the page
   - **When** they want it fixed
   - **Then** they use Update, and stage 1 can't be signed until Claude rewrites the example

### 4. An open gap blocks its scenario until the answer is in the Then

1. **4.1**
   - **Given** a stage-1 scenario whose example has an open `[ASK]`
   - **When** the reviewer opens it in the focus dialog
   - **Then** Approve is unavailable, the row shows an Open question token, and Update and Drop still work
   - **Data before:** **Scenario SC-14**: example Data after ends "[ASK: does "Welcome" stay on the
     subscription once its uses run out?]"; **Review state**: SC-14 undecided
   - **Walkthrough:**
     1. The reviewer opens SC-14 → ✗ Approve is unavailable
     2. The reviewer chooses Update and writes "It gets removed once uses hit 0"
   - **Data after:** **Review state**: ✓ SC-14 has an update request; stage 1 can't be signed while it's open
2. **4.2**
   - **Given** a reviewer who answered an `[ASK]` through Update
   - **When** Claude processes the export
   - **Then** the answer goes into the Then (or a new scenario), the example is rewritten without the
     `[ASK]`, and the scenario returns for a fresh decision
   - **Data before:** **Scenario SC-14**: Then "the fourth charge doesn't include it"; example ends with
     the `[ASK]`; **Review state**: SC-14 update "It gets removed once uses hit 0"
   - **Walkthrough:**
     1. Claude reads SC-14's update from the export
     2. Claude rewrites SC-14's Then and its Data after
     3. Claude re-renders with the export as the prior review
   - **Data after:** **Scenario SC-14**: Then "the fourth charge doesn't include it, and "Welcome" is
     removed from the subscription"; Data after "✓ **Subscription**: no "Welcome" discount", no `[ASK]`;
     **Review state**: ✓ SC-14 undecided, its update request cleared
3. **4.3**
   - **Given** a signed stage-1 export that approves a scenario whose example still has an open `[ASK]`
   - **When** Claude runs the stage-1 fold
   - **Then** the fold refuses and names the scenario
4. **4.4**
   - **Given** a dropped scenario whose example has an open `[ASK]`
   - **When** stage 1 is signed and folded
   - **Then** nothing blocks, because a dropped scenario isn't part of the contract
5. **4.5**
   - **Given** a markdown spec with open `[ASK]`s
   - **When** Claude reaches the user review gate
   - **Then** it lists each `[ASK]` with its scenario, and the answers go into the Thens before approval

### 5. An example changes with its scenario

1. **5.1**
   - **Given** a stage-1 scenario the reviewer has approved but not yet signed
   - **When** Claude edits only its example and re-renders
   - **Then** the scenario's decision clears and it returns for a fresh decision
   - **Data before:** **Scenario SC-15**: approved; walkthrough step 1 reads "$100.00 × 0.90 = $90.00"
   - **Walkthrough:**
     1. Claude corrects a label in SC-15's walkthrough step 1 and re-renders with the prior review
     2. The reviewer reloads the page
   - **Data after:** **Review state**: ✓ SC-15 undecided and marked as changed since review;
     **Scenario SC-15**: Then unchanged
2. **5.2**
   - **Given** a scenario with an example
   - **When** the reviewer picks one of Claude's alternative outcomes or writes their own
   - **Then** the scenario becomes an update request to rewrite the example for that outcome, and it
     can't be approved until Claude rewrites the Then and the example together
   - **Data before:** **Scenario SC-15**: Then "the line nets $76.50"; alternative "the line nets
     $75.00"; walkthrough compounds the discounts; **Review state**: SC-15 undecided
   - **Walkthrough:**
     1. The reviewer picks "the line nets $75.00" → ✓ SC-15 gets an update request to rewrite its example
     2. The reviewer tries to approve → ✗ Approve is unavailable while the update is open
     3. Claude rewrites SC-15's Then and walkthrough: $100.00 × (1 − 0.10 − 0.15) = $75.00
   - **Data after:** **Scenario SC-15**: Then "the line nets $75.00"; walkthrough adds the discounts;
     **Review state**: SC-15 undecided, awaiting a fresh decision
3. **5.3**
   - **Given** a scenario without an example
   - **When** the reviewer picks an alternative outcome
   - **Then** they can approve it directly, as they can today
4. **5.4**
   - **Given** a signed stage 1
   - **When** an example turns out to be wrong
   - **Then** fixing it goes through a scenario dispute, which reopens the scenario until the reviewer
     re-approves it
5. **5.5**
   - **Given** an approved spec in either format
   - **When** an amendment changes a scenario
   - **Then** the same amendment rewrites that scenario's example
6. **5.6**
   - **Given** a spec Claude has just written or revised
   - **When** Claude runs self-review
   - **Then** it checks that every example agrees with its Then, and that each open `[ASK]` is a question
     the design didn't already answer

### 6. The review page shows examples in the focus dialog

1. **6.1**
   - **Given** a scenario with an example
   - **When** the scenarios table renders
   - **Then** its row shows an Example token, plus an amber Open question token while an `[ASK]` is
     open, and never the example itself
2. **6.2**
   - **Given** any scenario row, in either stage
   - **When** the reviewer clicks it
   - **Then** the focus dialog opens on that scenario, with Previous and Next across that behavior's
     scenarios, while "Review undecided" keeps its own queue
3. **6.3**
   - **Given** a scenario with an example open in the focus dialog
   - **When** it renders
   - **Then** Data before, Walkthrough and Data after appear as three columns in the full palette,
     stacking on narrow screens, and the dialog widens to fit them

### 7. `logic.md` shows examples as labelled sub-bullets

1. **7.1**
   - **Given** a scenario with an example, in a hand-written or generated `logic.md`
   - **When** the spec is read
   - **Then** the example appears after the Then (and any alternatives) as **Data before**,
     **Walkthrough** as a numbered list, and **Data after**, with `✓`, `✗`, `*` and `[ASK]` as plain text

### 8. Later stages take their contract from the Then

1. **8.1**
   - **Given** an approved scenario with an example
   - **When** Claude derives stage-2 requirements
   - **Then** it derives from the scenario alone, and `derivedFrom` names scenarios only
2. **8.2**
   - **Given** a `*` value in an approved example
   - **When** an execution agent writes tests
   - **Then** it may use the value as test input, but an expected value always comes from the Then
3. **8.3**
   - **Given** the logic-spec rubrics
   - **When** they describe examples
   - **Then** they say nothing about turning examples into tests

### 9. Specs without examples are unchanged

1. **9.1**
   - **Given** an existing signed v2 spec whose scenarios have no examples
   - **When** it is validated and re-rendered after this change
   - **Then** validation passes, its stage-1 pin still matches, and `logic.md` is byte-identical
   - **Data before:** **Spec**: stage 1 signed; 40* scenarios, none with an example;
     **Stage-1 pin**: one hash per scenario
   - **Walkthrough:**
     1. The maintainer runs `validate` → ✓ passes
     2. The maintainer runs `render` → `logic.md` rewritten
   - **Data after:** **Stage-1 pin**: ✓ matches every scenario; **logic.md**: ✓ byte-identical to before
2. **9.2**
   - **Given** a v1 spec
   - **When** it is validated or rendered
   - **Then** it behaves exactly as today

## Key decisions & rationale

- **The Then stays the contract.** If examples bound the spec, every invented value would become a
  requirement. That was the main risk the hand trial reported. Keeping rules and examples as
  separate tiers matches Example Mapping. The example's job is to expose a gap, and the Then
  absorbs the answer.
- **The example is hashed with its scenario.** Approval covers the example, so a pinned approval can
  never sit next to an example the reviewer didn't see. Specs without examples keep their hashes
  because an absent part changes nothing.
- **Gaps block before approval.** In the trial, examples were written after approval, so each question
  they found needed an amendment. Writing them with the scenarios and blocking on `[ASK]` moves that
  discovery into review.
- **The focus dialog is the only place examples show.** The table stays as scannable as it is today.
  Any row opens the dialog, so approved scenarios and stage 2 keep access.
- **The roles live in plain-text marks.** The full palette needs results and rejections marked, and
  `✓`/`✗` read naturally in raw `logic.md`. The same text then works in both formats.
- **Three typed parts with markdown values.** This was chosen over one markdown blob, which parses
  fragilely, and over fully structured records, where deep nesting hurts authoring accuracy and markdown
  specs couldn't share the format. See Industry Insights.

**Success looks like this.** An interactive fixture spec built from the exploration's three examples
renders correctly in the focus dialog and in `logic.md`. Its open `[ASK]` blocks approval, and picking a
different outcome sends the scenario back. Existing specs re-render with byte-identical `logic.md`, and
their stage-1 pins hold.

## Scope & non-goals

In scope: both logic-spec rubrics and the shared conventions they link to, the interactive spec's
scenario shape, validation, hashing and fold checks, generated `logic.md`, and the review page's table
tokens and focus dialog.

Out of scope:

- Backfilling examples into existing specs. An owner can add them later through an amendment.
- An automatic checker that recomputes walkthrough arithmetic. The reviewer and self-review check the numbers.
- Spreadsheet or CSV export of scenarios and examples.
- v1 `logic.json` specs.
- A defined cast list, or a check that a title keeps the same values across scenarios.
- Any rubric guidance on turning examples into tests.
- Showing examples in the scenarios table rows.

## Decisions Locked

**Coverage & timing**
- Both formats get examples, with the same three parts and one shared set of conventions.
- A scenario gets an example wherever there's data to show, meaning it computes or changes records or
  has a concrete input and output. Other scenarios are skipped without comment.
- Examples are written with the scenarios, before the first review.
- A reviewer asks for an example through a scenario comment. There is no new control.

**Review semantics & gaps**
- The example is a checked restatement and the Then is the contract.
- A wrong example is flagged through Update, which blocks sign-off.
- A choice the Then never stated becomes an `[ASK]`.
- An open `[ASK]` blocks its scenario until answered, and the answer goes into the Then. Markdown
  specs list open `[ASK]`s at the review gate.

**Drift on rewrite**
- The example is hashed with its scenario, so after the stage-1 sign-off a fix goes through reopen.
- Picking a different outcome on a scenario with an example sends it back for Claude to rewrite the example.
- Both rubrics get a sync rule (rewrite the example in the same edit, amendments included) and a
  self-review check.

**Rendering**
- On the page, examples appear only in the focus dialog, and any scenario row opens it.
- Inside the dialog the example is three columns: before, walkthrough, after.
- The full spreadsheet palette carries over.
- `✓` marks a result and `✗` marks a rejection.
- `logic.md` shows the example as labelled sub-bullets.
- Rows show an Example token and an Open question token, and the dialog widens for three columns.
  Both were proposed in the design and approved with it.

**Downstream use**
- Requirements derive from the scenario alone.
- A `*` value may seed test inputs but is never an expected value.
- The rubric says nothing about turning examples into tests.

**Shared cast**
- Recurring names are a writing convention, defined nowhere.
- A title names a kind of thing, not its values.

**Format & approach**
- The three labels stay fixed, including for request/response scenarios.
- Storage uses three typed parts holding marked-up markdown (approach A).
- Success is a fixture spec plus a no-regression check.
- The out-of-scope list was approved with the design.

## Industry Insights

Research ran through WebSearch and WebFetch. The Brave search skills were unavailable in this session.

- Example Mapping keeps rules, examples and open questions as separate tiers: rules on blue cards,
  examples on green, questions on red. That matches Then, example and `[ASK]`.
  [Cucumber: Example Mapping](https://www.cucumber.io/docs/bdd/example-mapping)
- Gherkin's `Rule` keyword groups illustrating scenarios under one business rule. It's the closest
  built-in split between a rule and its examples. [Cucumber: Gherkin reference](https://www.cucumber.io/docs/gherkin/reference),
  [Gherkin rules](https://cucumber.io/blog/bdd/gherkin-rules/)
- Incidental detail hides what an example tests, and UI or element detail makes specs brittle. Hence
  "only values that matter" and the no-field-names rule.
  [Cucumber anti-patterns part 1](https://cucumber.io/blog/bdd/cucumber-antipatterns-part-one/),
  [part 2](https://cucumber.io/blog/bdd/cucumber-anti-patterns-part-two/)
- A stale example can pass while encoding a rule the business has dropped, so a rule change needs a
  human review of its examples in the same change. This is why the example is hashed with its scenario.
  [qaskills: BDD living documentation](https://qaskills.sh/blog/bdd-living-documentation-reports)
- No source found prescribes a marker for illustrative versus binding example values. The `*`
  convention is this project's own.
- Markdown inside generated strings often breaks at its boundaries: 38% of valid outputs in one
  benchmark. Typed fields, as in GitHub issue forms, move the contract into the schema. This argues
  against one markdown blob. [LatentMD](https://arxiv.org/abs/2609.06993),
  [GitHub issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
- Deeply nested JSON lowers extraction accuracy: strict scores under 60% at 5–7 levels, and string
  lists score worst. This argues against fully structured records.
  [DeepJSONEval](https://arxiv.org/abs/2509.25922)
- A trailing `*` can pair with an earlier emphasis opener under CommonMark's flanking rules, so the
  renderer and page need an agreed escape for it. [CommonMark spec](https://spec.commonmark.org/0.31.2/)

## Deferred Ideas

- Use approved examples as test seeds. This would be a writing-plans change.
- Spreadsheet or CSV export of scenarios with their examples.
- A warning when one title carries different values across scenarios, if that drift shows up in practice.
- Show examples when brainstorming presents scenarios during design, before the spec is written.
- `[tech-spec]` The escape rule for a trailing `*` against markdown emphasis, in both the page and the renderer.
- `[tech-spec]` The exact patterns the page uses to detect each mark for colouring.
- `[tech-spec]` Validator errors for near-miss `[ASK]` forms, such as `[ASK]` with no colon or `ASK:`.
- `[tech-spec]` The wording of the automatic update request when a reviewer picks a different outcome.
- `[tech-spec]` How wide the focus dialog gets for a scenario with an example.

## Glossary

| Term | Definition |
|---|---|
| Data-state example | A scenario's optional Data before / Walkthrough / Data after. |
| Checked restatement | The example's role: data that must agree with the Then and never overrides it. |
| Invented value | A value marked `*` and picked to make an example concrete. It is not part of the rule. |
| Gap | An `[ASK: …]`: something the scenario doesn't settle that the example can't show without guessing. |
| Shared conventions | The single set of example-writing rules that both logic-spec rubrics link to. |
| Data to show | A scenario that computes or changes records, or has a concrete input and output. |

## Status & amendments

**Status:** Approved. Tech spec: requested

**Amendments:** none yet.
