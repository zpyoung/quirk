# Writing the Logic Spec

The rubric `quirk:brainstorming` follows once the user has approved the design: what `logic.md`
contains, how to self-review it, and the review gate that must pass before implementation starts.

A logic spec is the **approved, human-facing record of what is being built and why** — the document
the user read and signed off on. It is never silently overridden downstream.

**Where it lives:** see [Where the specs live](SKILL.md#where-the-specs-live).

## Writing it

- Write the validated design (logic spec) to `docs/quirk/specs/YYYY-MM-DD-<topic>/logic.md`
  - (User preferences for spec location override this default)
- Use elements-of-style:writing-clearly-and-concisely skill if available
- Cover: conceptual model, data flow (prose), key decisions & rationale, behavior & scenarios, scope
  & non-goals, glossary — precise architecture, components, error handling, and testing belong in
  the tech spec authored later at execution when warranted (see [tech-spec.md](tech-spec.md)); name
  file-level structure here only when it is itself the user-facing decision
- Include these sections, in addition to the coverage above:
  - **Decisions Locked** — the gray-area decisions confirmed during drill-in (one bullet per locked decision, grouped by area)
  - **Industry Insights** — distilled key findings from research agents, with source URLs; mark "(offline mode — validation pending)" if research was skipped
  - **Deferred Ideas** — anything captured by the Scope Creep Guard (or "None — discussion stayed within scope")
  - **Glossary** — terms and definitions a reader needs to follow the spec
  - **Status** — one line recording the spec's current state (e.g. "Draft", "Approved", "Tech spec: requested")
  - **Amendments** — under a `## Status & amendments` heading, a dated `**Amendments:**` log entry for any change to a locked decision made after approval
- Commit the logic spec to git

## Logic-spec self-review

After writing the logic spec, look at it with fresh eyes:

1. **Placeholder scan:** Any "TBD", "TODO", incomplete sections, or vague requirements? Fix them.
2. **Internal consistency:** Do any sections contradict each other? Does the architecture match the feature descriptions?
3. **Scope check:** Is this focused enough for a single implementation plan, or does it need decomposition?
4. **Ambiguity check:** Could any requirement be interpreted two different ways? If so, pick one and make it explicit.

Fix any issues inline. No need to re-review — just fix and move on.

## User Review Gate

After the spec review loop passes, ask the user to review the written spec before proceeding:

> "Logic spec written and committed to `<path>`. Please review it and let me know if you want to make any changes before we move to implementation — for larger work, the execution skill may first author a tech spec from it."

Wait for the user's response. If they request changes, make them and re-run the spec review loop.
Only proceed once the user approves.

**Tech-spec request capture.** If the user's approval also asks for a tech spec, record
`Tech spec: requested` in the logic spec's `Status` line and commit that update before handing off
to the execution skill — this is what lets [tech-spec.md](tech-spec.md)'s complexity-tier gate read
the request later without re-asking.
