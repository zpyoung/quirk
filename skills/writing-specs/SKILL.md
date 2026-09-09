---
name: writing-specs
description: The two-document spec rubric — what a good logic spec (logic.md) and tech spec (tech.md) contain, and which stage owns which. Brainstorming runs the logic-spec half after design approval; the execution skills run the tech-spec half in-context when the complexity gate fires, before planning.
---

# Writing Specs

Two documents, one pipeline. The **logic spec** is human-facing and approved; the **tech spec** is
agent-facing and gated on complexity. This hub owns what they share — the pipeline, who writes which,
the ownership line between them, and where they live. The rubrics themselves live one level down.

**The pipeline:**

```
brainstorming → logic.md → user approves → execution skill → (complexity gate) tech.md
    → quirk:writing-plans → execute
```

## Which document, which rubric

| Document | Invoked by | When | Rubric |
|----------|-----------|------|--------|
| `logic.md` | `quirk:brainstorming` | after the design is approved | [logic-spec.md](logic-spec.md) |
| `tech.md` | `quirk:executing-plans`, `quirk:subagent-driven-development` | only when the complexity-tier gate fires | [tech-spec.md](tech-spec.md) |

Read the one rubric your stage needs — not both.

## Ownership

The logic spec owns *why* and *behavior* (and may name file-level structure when that structure is
itself the user-facing decision). `tech.md` owns *where* and *contracts*. Each may summarize the
other in one line and link across — **never duplicate a paragraph.**

Any change to a decision the logic spec already locked amends the **logic spec first** — a dated
entry in its Amendments log — never a silent edit to `tech.md`.

## Where the specs live

`CONTRACT:` `tech.md` is always authored as a **sibling of the actual `logic.md`** — in whatever
directory the logic spec was actually saved to, even when a user preference overrode the default
location. The layout below is the **default example**, not a hard-coded path:

```
docs/quirk/specs/YYYY-MM-DD-<topic>/logic.md
docs/quirk/specs/YYYY-MM-DD-<topic>/tech.md
```

Multi-subsystem work gets N sibling `<topic>` folders, each its own `logic.md` + `tech.md` pair; a
later sibling's `tech.md` may reference an earlier one's contracts, but always by full path — a bare
`tech.md#…` pointer resolves against the wrong folder the moment it's copied anywhere else (a plan
header, a task excerpt).
