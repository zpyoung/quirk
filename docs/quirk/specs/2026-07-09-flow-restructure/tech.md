# Tech spec — restructure the quirk flow into logic spec + tech spec

**Status:** Draft (awaiting user skim; auto-review pending)
**For agents.** This is the code-anchored implementation map for the change described in [`logic.md`](./logic.md). It contains **pointers, not pasted prose** — exact files, line anchors, and per-unit change contracts. The implementer authors the actual replacement text; this document says *where*, *what must be true after*, and *what not to touch*. Every work unit back-links the logic-spec section that justifies it (see [Traceability](#traceability)).

**Executor calibration:** author it for a fresh subagent with zero conversation history. Each work unit is self-contained: it carries its own anchors and acceptance. All line numbers are against the working tree at authoring time — **re-verify each anchor against the live file before editing** (grep the quoted current text; if it moved, trust the text over the number). tech.md is a map, never the territory.

**No-Code convention (inherited):** this spec reuses `writing-plans`' tagged-exception markers — `CONTRACT:` (a literal string that other text must match exactly, e.g. a new path or digraph label), `COMMAND:` (verbatim shell), `SCHEMA:` (file/section shape). Any other fenced block is descriptive context, not code to paste. See `skills/writing-plans/SKILL.md:49-58` (**DO-NOT-CHANGE**, see fences).

---

## Architecture

The restructure is entirely Markdown-skill edits — no runtime code. Fourteen files change across five clusters (the exploring-ideas row is four files, plus the deleted asset); five files are audited-no-change (recorded so coverage is explicit, not silently skipped).

| Cluster | Files | Nature |
|---|---|---|
| A. Logic-spec producer | `skills/brainstorming/SKILL.md` (+ delete one asset) | Re-purpose output → `logic.md`; new subfolder path; re-scope content; keep pre-approval exploration |
| B. Tech-spec rubric (new) | `skills/writing-tech-spec/SKILL.md`, `skills/writing-tech-spec/tech-spec-reviewer-prompt.md` | New execution-invoked rubric + its reviewer |
| C. Planner amendment | `skills/writing-plans/SKILL.md`, `skills/writing-plans/plan-document-reviewer-prompt.md` | Consume `tech.md`; header fields → pointers |
| D. Execution wiring | `skills/executing-plans/SKILL.md`, `skills/subagent-driven-development/SKILL.md` | Conditional pre-plan step invoking cluster B |
| E. Cross-references | `skills/using-git-worktrees/SKILL.md`, `skills/exploring-ideas/{SKILL.md, references/interaction-model.md, exploration-artifact-template.md, evals/evals.json}`, `README.md` | Flow-label + path + version updates |
| — Audited, no change | `skills/using-quirk/SKILL.md`, `skills/adhd/SKILL.md`, `commands/explore.md`, `skills/requesting-code-review/SKILL.md`, `skills/finishing-a-development-branch/SKILL.md` | Make no pipeline-shape/design-doc claims (verified) |

**Data-flow contract the edits must preserve:** `brainstorming` → writes `logic.md` → **user approves** → an execution skill runs → *(conditional)* `writing-tech-spec` rubric authors `tech.md` → `writing-plans` rubric builds the in-context task list consuming `tech.md` → execute. Implements [logic §Data flow](./logic.md#data-flow).

---

## Shared rules (referenced by the work units)

### R1 — Path convention
`CONTRACT:` per-topic subfolder, sibling files:
```
docs/quirk/specs/YYYY-MM-DD-<topic>/logic.md
docs/quirk/specs/YYYY-MM-DD-<topic>/tech.md
```
Multi-subsystem work = N sibling `YYYY-MM-DD-<topic>/` folders, each its own pair. Replaces the flat `docs/quirk/specs/YYYY-MM-DD-<topic>-design.md`. The `docs/quirk/explorations/` and `docs/quirk/plans/` trees are unchanged (out of scope). Implements [logic §Decisions Locked → Structure](./logic.md#decisions-locked).

### R2 — Complexity tier (when `tech.md` is authored)
`writing-tech-spec` runs **only if** at least one holds; otherwise execution skips straight to planning from `logic.md`:
- execution spans **more than one session**, OR
- the work **crosses a subsystem boundary**, OR
- it touches **≳3 source files**, OR
- the **user asks** for a tech spec.
Below the line, the pipeline is `brainstorm → logic → build`. Implements [logic §Behavior → Small change](./logic.md#behavior--scenarios) and [logic §Decisions Locked → Structure](./logic.md#decisions-locked).

### R3 — Ownership + sync + traceability (the two templates)
- `logic.md` **owns** why + behavior; **may** name file-level structure when that structure is the user-facing decision. `tech.md` **owns** where + contracts.
- Each may summarize the other in ≤1 line and link across; no duplicated paragraphs.
- Every `tech.md` technical section **back-links** a `logic.md#anchor`. Links must resolve.
- Any change to a locked decision amends `logic.md` **first**, as a dated entry in the logic spec's Amendments log (the `**Amendments:**` list under `## Status & amendments`) — never a silent `tech.md` edit. Implements [logic §Key decisions → ownership+sync](./logic.md#key-decisions--rationale).

### R4 — Feasibility escalation
While authoring `tech.md`, if the codebase contradicts a `logic.md` **Decisions Locked** entry or its conceptual model: **STOP**, present the conflict to the user, and record the resolution as a dated entry in `logic.md`'s Amendments log before continuing. Never resolve unilaterally in `tech.md`. Implements [logic §Behavior → Feasibility conflict](./logic.md#behavior--scenarios).

---

## Work units

### CU-1 — `brainstorming` produces `logic.md`
**Files:** `skills/brainstorming/SKILL.md` (333 lines); **delete** `skills/brainstorming/spec-document-reviewer-prompt.md` (orphaned — `grep -rn spec-document-reviewer skills/` returns zero hits).

**Contract — after the edit:**
- **C1.1 Path + naming.** The two occurrences of the flat design path become the R1 subfolder `logic.md` path.
  - `skills/brainstorming/SKILL.md:32` (checklist step 9) — anchor current text `` `docs/quirk/specs/YYYY-MM-DD-<topic>-design.md` `` → R1 `logic.md`.
  - `skills/brainstorming/SKILL.md:274` ("Write the validated design (spec) to …") — same substitution. Rename the artifact term "design doc / spec" → "logic spec" in steps 9 (`:32`) and the Documentation section (`:274`, `:281` "Commit the design document").
  - Also update the two prose occurrences of "design doc": `:118` ("The design doc's 'Industry Insights' section") and `:247` ("before writing the design doc") → "logic spec."
- **C1.2 Digraph labels** (`:39-73`). Update node/edge labels: `:51` `"Write design doc"` → `"Write logic spec"`; the **three** edges referencing that node (`:67` `"User approves design?" → "Write design doc"`, `:68`, `:70`) follow the rename. `:52` `"Spec self-review"`, `:53` `"User reviews spec?"`, `:54` `"Invoke execution skill\n(plans in context)"` keep their meaning (the terminal is still an execution skill) — **do not** add a tech-spec node here (tech authoring is execution-owned, not a brainstorming stage). Preserve literal `\n` escapes.
- **C1.3 Content re-scope.** `:254` ("Cover: architecture, components, data flow, error handling, testing") → the logic spec covers **conceptual model, data flow (prose), key decisions & rationale, behavior & scenarios, scope & non-goals, glossary**; precise architecture/components/error-handling/testing move to `tech.md`. `logic.md` **may** name file-level structure when it is the user-facing decision (R3). Add a **Glossary** section, a `Status` line, and an `Amendments` log (a `**Amendments:**` label under a `## Status & amendments` section) to the documented section list at `:277-280` (alongside Decisions Locked / Industry Insights / Deferred Ideas).
- **C1.4 Keep pre-approval exploration.** The Step-1 "Explore project context" and the codebase-context research (the skill's existing exploration behavior) **must remain** — `logic.md` is first-contact-grounded before approval. `SCHEMA:` do not remove any existing exploration step.
- **C1.5 Terminal handoff.** `:35` (step 12), `:75`, `:302-303` already hand to an execution skill "which builds the plan in context." Amend the prose to note the execution skill **first authors a tech spec when the work warrants it (R2), then plans** — without turning tech-spec authoring into a brainstorming step. Keep "do NOT write a separate plan document first" intact.
- **C1.6 User review gate.** `:293-298` keeps its *semantics* (mandatory approval; wait for response) — only the announcement wording at `:296` ("Spec written and committed to `<path>`…") is reworded to name the **logic spec** and set the expectation that a tech spec may follow at execution (see global fence 4's exemption). `:283-291` Spec Self-Review label → "Logic-spec self-review"; keep the checklist mirrors consistent (`:33` "Spec self-review", `:34` "User reviews written spec").
- **C1.7 Delete orphaned asset** and confirm no new dangling references (`grep -rn spec-document-reviewer skills/` stays empty).

**Acceptance:**
- `grep -rn "specs/.*-design.md" skills/brainstorming/` returns nothing; the R1 `logic.md` path appears at the two anchors.
- No occurrence of "design doc" as the produced artifact remains in `SKILL.md` (the term is "logic spec").
- `skills/brainstorming/spec-document-reviewer-prompt.md` no longer exists; grep for `spec-document-reviewer` is empty repo-wide.
- The pre-approval exploration steps and the mandatory user-approval gate are still present.

---

### CU-2 — new rubric skill `writing-tech-spec`
**Files:** create `skills/writing-tech-spec/SKILL.md`.

**Contract — the SKILL.md must contain (author the prose; these are the required elements, not text to paste):**
- **C2.1 Frontmatter.** `SCHEMA:`
  ```
  name: writing-tech-spec
  description: The rubric the execution skills run in-context — only when the work warrants it — to author the code-anchored tech spec from the approved logic spec, before planning.
  ```
- **C2.2 "How this skill is used" blockquote** mirroring `skills/writing-plans/SKILL.md:10-15`: authoring the tech spec is **not** a user-facing stage; the execution skills invoke it as a pre-planning sub-phase, gated on R2; this rubric defines *what a good tech spec contains*, the calling skill owns *when* it runs.
- **C2.3 Complexity-tier gate** = R2 verbatim (the skip condition).
- **C2.4 Deep-dive method.** Dispatch parallel `Explore` subagents to gather precise anchors (paths, signatures, symbols, existing tests, stable regions) from the live codebase before writing. This is the source of "heavy code reference."
- **C2.5 `tech.md` template** — required sections: header (`Status`, back-links to `logic.md`); Architecture (real files); Code references (absolute paths, signatures, symbols to create/modify); Contracts & interfaces (preconditions/postconditions/invariants/errors); Data models/schemas; **DO-NOT-CHANGE fences** (each cites a reason + is re-verified at plan-build); Always/Ask/Never constraints; Testing strategy (which test files, coverage, acceptance — not test bodies); Non-goals. Implements [logic §Glossary → Tech spec](./logic.md#glossary).
- **C2.6 Pointers-not-code rule** — reuse the `writing-plans` tagged-exception markers (`CONTRACT:/SCHEMA:/COMMAND:/REGEX:/CONFIG:/PSEUDOCODE (justified, ≤3 lines):` — the full six from `writing-plans/SKILL.md:53-58`, none dropped); **no pasted implementations or full test bodies**.
- **C2.7 Ownership + traceability** = R3; **Feasibility escalation** = R4.
- **C2.8 Where `tech.md` lives** = R1 sibling `tech.md`. Announce line, matching `writing-plans:23` style.
- **C2.9 After authoring:** dispatch the CU-3 reviewer; apply fixes inline; offer an **optional** user skim (not a gate); then hand to `writing-plans` for planning. Implements [logic §Key decisions → review gates](./logic.md#key-decisions--rationale).

**Acceptance:** the skill is discoverable (valid frontmatter); an execution skill can invoke it by name; when invoked it produces a `tech.md` at the R1 path with every required section and zero pasted implementations. (The R2 skip is enforced by the callers CU-5/CU-6 and verified by T5, not by this skill's own artifact.)

---

### CU-3 — tech-spec reviewer prompt
**Files:** create `skills/writing-tech-spec/tech-spec-reviewer-prompt.md`, mirroring `skills/writing-plans/plan-document-reviewer-prompt.md` (60 lines: dispatch metadata `:7-12` + fenced Task-tool prompt + check table `:27-34` + output contract `:51`).

**Contract — the reviewer's check table must cover:**
- **Pointer precision** — every path/signature/symbol named is real and resolvable in the tree.
- **Fidelity** — every `logic.md` Decisions-Locked entry is implemented; **none silently reinterpreted** (R4). 
- **Traceability** — every technical section back-links a `logic.md#anchor`; all links resolve (R3).
- **No-Code** — no pasted implementations/test bodies; only tagged exceptions.
- **Completeness** — contracts state pre/post/invariants/errors; each DO-NOT-CHANGE fence cites a reason.
- **Buildability** — a zero-context subagent could act on it.
Output contract mirrors `plan-document-reviewer-prompt.md:51` — `**Status:** Approved | Issues Found`. Dispatch: inline-paste `tech.md` + `logic.md` (reviewer reads no file), automatic before planning. Implements [logic §Decisions Locked → Gates & safety](./logic.md#decisions-locked).

**Acceptance:** dispatching the prompt on a sample `tech.md` yields a `Status:` line and flags a deliberately-broken cross-link and a deliberately-reinterpreted decision.

---

### CU-4 — `writing-plans` consumes `tech.md`
**Files:** `skills/writing-plans/SKILL.md` (275 lines), `skills/writing-plans/plan-document-reviewer-prompt.md` (60 lines).

**Contract — after the edit:**
- **C4.1 Input naming.** Where planning names its upstream input as "a spec / the spec / requirements," it becomes "**the tech spec (`tech.md`) when present, else the logic spec / requirements**." Anchors: `:3` (frontmatter description "turns a spec or requirements into a task breakdown"), `:78` (Scope Check "If the spec covers multiple independent subsystems…"), `:248` and `:250` (Self-Review "look at the spec" / "Spec coverage"), `:262` (Self-Review closing "spec requirement").
- **C4.2 Header fields → pointers.** The mandatory Plan Document Header (`:127-153`) fields that `tech.md` now owns — `Architecture:` (`:142`), `Alternatives considered:` (`:144`), `Tech Stack:` (`:146`), `Constraints:` (`:148`), `Cross-cutting:` (`:150`) — become **one-line pointers into `tech.md` sections when a tech spec exists** (e.g. "Architecture: see `tech.md#architecture`"), authored in full only when there is no tech spec. `Goal`/`Goals-Non-Goals`/`Status` stay inline. This kills the triple-statement of architecture. Implements [logic §Key decisions → why amend writing-plans](./logic.md#key-decisions--rationale).
- **C4.3 Contract excerpting.** Add an instruction that when a task depends on a `tech.md` contract, the orchestrator **excerpts that contract inline into the task text at dispatch** — because subagents never read files (`skills/subagent-driven-development/SKILL.md:150-151`, `:482`). Single source (`tech.md`), pasted last-moment. Implements [logic §Behavior → Substantial feature](./logic.md#behavior--scenarios).
- **C4.4 Reviewer input.** In `plan-document-reviewer-prompt.md`, all upstream-input references — `:5` ("matches the spec"), `:11` ("Paste the spec text"), `:23` ("Spec for reference: [PASTE SPEC TEXT OR SPEC_FILE_PATH]"), `:30` ("Plan covers spec requirements"), `:42` ("missing requirements from the spec") → reference the tech spec when present, else logic spec.
- **DO-NOT-CHANGE:** the No-Code Rule (`:39-65`), the "Default: in context, not a file" plan-lives-in-context default (`:29-37`), the Calibrate-to-Executor branch (`:67-74`), and the task template's red-green-commit rhythm (`:163-223`). These are load-bearing invariants the amendment must not weaken.

**Acceptance:** the frontmatter (`:3`) and input-naming anchors (`:78`, `:248`, `:250`, `:262`) name "the tech spec (`tech.md`) when present, else the logic spec / requirements"; the header example renders `tech.md`-owned fields as `see tech.md#…` pointers; `sed -n '39,65p'` of the No-Code Rule diffs empty against the pre-edit file (byte-identical).

---

### CU-5 — `executing-plans` conditional pre-plan step
**Files:** `skills/executing-plans/SKILL.md` (77 lines).

**Contract:**
- **C5.1 Insert a new step** immediately above `:21` (`### Step 1: Build (or load) the plan, then review`). Because this file uses `Step 1/2/3` (no `Step 0`), name it `CONTRACT:` `### Step 0: Author the tech spec (only when complexity warrants)`. Body: apply R2; if met, invoke the `writing-tech-spec` rubric (CU-2) → `tech.md` + CU-3 review + optional skim + R4 escalation; else note "no tech spec — plan from the logic spec" and continue.
- **C5.2 Consume `tech.md`.** In Step 1 (`:22-24`) note the plan is built from `tech.md` when present (else logic spec / handed-off plan). Update the Integration bullet `:76` to mention `writing-tech-spec` as the optional pre-plan rubric.
- **DO-NOT-CHANGE:** the plan-document reviewer dispatch (`:25-27`) and "No human approval gate."

**Acceptance:** Step 0 precedes Step 1; a small-tier run visibly skips it; a large-tier run authors `tech.md` before planning.

---

### CU-6 — `subagent-driven-development` conditional pre-plan step
**Files:** `skills/subagent-driven-development/SKILL.md` (551 lines).

**Contract:**
- **C6.1 Insert a new step** immediately above `:127` (`### Step 0a: Build the plan in context`), after `### Step 0: Runtime selection` (`:125`). Name it `CONTRACT:` `### Step 0a-pre: Author the tech spec (only when complexity warrants)` (fits the `Step 0 → 0a → 0a-review → 0b → 0c` family). Body: R2 gate → CU-2 rubric → CU-3 review → optional skim → R4 escalation, else continue.
- **C6.2 Consume `tech.md`.** Step 0a (`:132`) notes the breakdown is drafted from `tech.md` when present. Update the upstream-input line `:34-36` ("You need a spec or requirements to plan from") → "tech spec when present, else logic spec / requirements."
- **C6.3 Keep cross-references consistent.** The narrative naming Step 0a as "the first phase" at `:35`, `:540`, and the example workflow `:366-368` should acknowledge the optional `Step 0a-pre` precedes it. `CONTRACT:` the "subagents never read a plan file / paste inline" invariant (`:150-151`, `:482`) is the reason CU-4's C4.3 excerpting exists — **do not weaken it**.
- **DO-NOT-CHANGE:** the wave computation (`Step 0b`), mode selection (`Step 0c`), the per-task review chain, the plan-document reviewer dispatch (`:141-146`), and **both digraphs** (`:16-32`, `:77-117`) — intentionally untouched (Step 0a-pre is prose-only; do not add digraph nodes).

**Acceptance:** `Step 0a-pre` renders before `Step 0a`; the "first phase" references still parse; the paste-inline invariant text is unchanged.

---

### CU-7 — cross-reference updates
**Files & exact edits:**
- **C7.1** `skills/using-git-worktrees/SKILL.md:212` — `- **brainstorming** (Phase 4) - REQUIRED when design is approved and implementation follows` → gate wording references the **logic spec** approval ("when the logic spec is approved").
- **C7.2** `exploring-ideas` family — replace the literal pipeline string `quirk:brainstorming → writing-plans` with `CONTRACT:` the new shape `quirk:brainstorming → an execution skill (which authors a tech spec when warranted, then plans in context)`:
  - `skills/exploring-ideas/references/interaction-model.md:139`
  - `skills/exploring-ideas/exploration-artifact-template.md:71`
  - `skills/exploring-ideas/evals/evals.json:55`
  - `skills/exploring-ideas/evals/evals.json:31` — "brainstorming (creative work that converges to a spec)" → "converges to a **logic spec**."
  - `skills/exploring-ideas/SKILL.md:47`, `:184` already say "brainstorming → execution (which plans in context)"; add "authors a tech spec when warranted, then" for consistency. The many "not a spec" gate lines are **not** touched (they are the exploration invariant, not pipeline-shape).
- **C7.3** `README.md` — `:52` heading `### Design + spec` → `### Logic spec + tech spec`; `:54` example path `docs/specs/2026-05-04-typed-artifacts-design.md` → describe the R1 convention (leave the old file in place as historical; point the example at the new shape); `:9` skill-area line ("brainstorming, … plan writing") → reflect logic-spec/tech-spec framing and **20 → 21 skills** (CU-2 adds one). `:5` version bump is **deferred** (see Non-goals).

**Acceptance:** `grep -rnE 'brainstorming.*(→|->).*writing-plans' skills/` returns nothing (backtick-proof — the old flat pattern missed the backticked `` `quirk:brainstorming` → `writing-plans` `` at `:139`/`:71`); `grep -rn "when design is approved" skills/` returns nothing; README describes the two-file convention and the skill count 21.

---

### CU-8 — audited, no change (coverage record)
Verified to make **no** pipeline-shape or design-doc claims; intentionally untouched:
- `skills/using-quirk/SKILL.md` — the plan-mode gate references `brainstorming` only, not a design/plan artifact.
- `skills/adhd/SKILL.md` — `SOURCE-SPEC.md` mention is attribution, not pipeline.
- `commands/explore.md` — handoff target `quirk:brainstorming` remains valid.
- `skills/requesting-code-review/SKILL.md:61` — `docs/quirk/plans/…` example references the unchanged plans tree.
- `skills/finishing-a-development-branch/SKILL.md` — records no doc `Status` today; `logic.md` Data flow was softened to match (Status set as work completes; lifecycle automation deferred), so this skill is untouched here.

---

## DO-NOT-CHANGE fences (global invariants)

Each cites its reason; re-verify at plan-build:
1. **No-Code Rule** — `skills/writing-plans/SKILL.md:39-65`. Reason: pasted code anchors implementers and ages instantly; the tech spec is code-anchored via *pointers*, which does not relax this. ([logic §Key decisions → precise pointers](./logic.md#key-decisions--rationale))
2. **Plan lives in context** — `skills/writing-plans/SKILL.md:29-37`. Reason: the task list is execution state; this restructure keeps tasks in-context. ([logic §Key decisions → seam](./logic.md#key-decisions--rationale))
3. **Subagents paste task text inline, never read files** — `skills/subagent-driven-development/SKILL.md:150-151`, `:482`. Reason: it is why CU-4 C4.3 excerpts contracts at dispatch.
4. **Mandatory user-approval gate on the human doc** — the *semantics* of `skills/brainstorming/SKILL.md:293-298` (a hard gate: wait for the user; proceed only on approval). Reason: the logic spec is where human understanding is confirmed. **Exemption:** the announcement *wording* at `:296` may be reworded per CU-1 C1.6 — the gate's behavior must not weaken, but its prose may. ([logic §Key decisions → review gates](./logic.md#key-decisions--rationale))
5. **Per-task review chain + plan-document reviewer** — unchanged in both execution skills. Reason: out of scope.

## Always / Ask / Never

- **Always** re-verify a quoted line anchor against the live file before editing (numbers drift; text is the contract). Always keep `logic.md` ↔ `tech.md` cross-links resolvable.
- **Ask** (escalate, R4) before resolving any codebase conflict with a `logic.md` Decisions-Locked entry.
- **Never** paste runnable implementations/test bodies into `tech.md`. Never weaken a DO-NOT-CHANGE fence. Never rename the `brainstorming` skill. Never restructure the `docs/quirk/explorations/` or `docs/quirk/plans/` trees.

## Testing / verification strategy

No unit tests (Markdown edits). Verification is mechanical + eval-based:
- **T1 grep audits** (the CU acceptance greps above), run as a batch: no residual `-design.md` produced-artifact path; no `brainstorming → writing-plans` string; no `when design is approved`; `spec-document-reviewer` empty repo-wide.
- **T2 link resolution** — every `./logic.md#anchor` in `tech.md` and every `tech.md#…` pointer in an amended plan header resolves to a real heading.
- **T3 skills load** — `writing-tech-spec` frontmatter is valid and the skill is listed; the two execution skills reference it without a broken relative path.
- **T4 exploring-ideas evals** — re-run/update `skills/exploring-ideas/evals/evals.json` expectations changed by C7.2 (`:31`, `:55`) so they assert the new flow string.
- **T5 dry-run trace** — one small-tier task (skips `tech.md`) and one large-tier task (authors `tech.md`, review fires, feasibility path reachable) behave per R2/R4.

## Non-goals
- No version bump here (README `:5`) — done at release via `releasing-quirk` (`5.9.0 → 5.10.0`).
- No auto-generation of `tech.md` from `logic.md`; no doc-sync tooling. ([logic §Deferred Ideas](./logic.md#deferred-ideas))
- No migration of existing `*-design.md` specs; no restructuring of the explorations/plans trees.
- No rename of the `brainstorming` skill.

## Traceability

| Work unit | logic.md section |
|---|---|
| CU-1 (logic producer, path, re-scope) | Problem & purpose; Data flow; Decisions Locked → Structure |
| CU-2 (tech-spec rubric) | Conceptual model; Glossary → Tech spec; Key decisions → topology |
| CU-3 (tech reviewer) | Decisions Locked → Gates & safety |
| CU-4 (writing-plans consumes) | Key decisions → why amend writing-plans; Behavior → Substantial feature |
| CU-5 / CU-6 (execution wiring, R2 gate) | Behavior → Small change / Substantial feature; Decisions Locked → Optional tier |
| CU-7 (cross-refs) | Scope & non-goals |
| R3 / R4 (ownership+sync, feasibility) | Key decisions → ownership+sync; Behavior → Feasibility conflict |

## Status & amendments
**Status:** Draft — authored ahead of execution to dogfood the format (this change spans 10 files, clearing the R2 tier). Auto-review (CU-3-style) pending. **Amendments:** _(none yet)_
