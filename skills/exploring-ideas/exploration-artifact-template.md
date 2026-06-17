# Exploration Artifact Template

Synthesize the session into this structure and save to
`docs/quirk/explorations/YYYY-MM-DD-<topic>.md`. Adapt section weight to emphasis
(research-heavy → richer Findings; ideation-heavy → richer Idea landscape), but keep
EVERY section present. The banner is mandatory and must be the first line.

**Hard rules:**
- No "Decisions Locked", requirements, acceptance criteria, or implementation steps.
- No winner declared. Preserve tensions; do not resolve them.
- Every idea direction is insight-paired. Every factual claim is sourced (or marked unverified).

---

```markdown
> 🧭 EXPLORATION — not a spec. No locked decisions; nothing here is build-ready.

# Exploring: <topic>

**Date**: YYYY-MM-DD · **Emphasis**: research-heavy | blended | ideation-heavy · **Intensity**: 0.x (Grounded | Exploratory | Bold | Radical)

## Framing
The question or goal, and how it was scoped (depth, recency, constraints, what it serves).

## What was explored
- Facets / sub-questions investigated (research)
- Directions generated (brainstorm)
- Anything deliberately left out of scope

## Findings / Idea landscape
Cited findings grouped by theme (research) and/or clustered idea directions (brainstorm).
NO winner declared. Each idea direction is insight-paired:

### Direction: <name>
<the idea — one or two lines>
*why this might actually work:* <one-line grounded insight>
*surfaced by:* <technique>  ·  *sits at intensity:* <Grounded…Radical>

### Direction: <name>
…

(For research-heavy sessions, lead with themed findings instead:)
### Theme: <name>
- <finding> — <source>
- <finding> — <source>

## Tensions & trade-offs
Where findings or directions conflict. State the tension; do not pick a side.
- <A> pulls toward X, <B> pulls toward Y because …

## Challenge notes
For the strongest directions/findings: steelman → counter-argument → what would disprove it.
- **<direction>** — steelman: … · strongest counter: … · would be disproven if: …

## Open questions & gaps
What's still unknown or worth exploring next. Include any coverage the research couldn't reach.

## Sources
- <claim/finding> — <URL or provenance>
- <claim/finding> — <URL or provenance>
- (mark "(offline — unverified)" for anything not source-backed)

---
*Exploration only. To build a direction: invoke `quirk:brainstorming` → `writing-plans`.*
```
