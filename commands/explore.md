---
description: Deep research or brainstorm a topic WITHOUT producing a spec — yields a cited briefing / idea-landscape. Optional intensity via --wild 0.1–1.0.
---

Invoke the `quirk:exploring-ideas` skill to explore the following, with NO spec, requirements, or implementation as output:

$ARGUMENTS

Notes:
- If `$ARGUMENTS` contains `--wild <0.1–1.0>` (or a bare decimal), use it as the intensity; otherwise default to `0.5`.
- Detect emphasis (research-heavy vs ideation-heavy) from the wording; confirm only if genuinely ambiguous.
- Follow the skill exactly: light scoping → research loop and/or divergent pass → challenge pass → auto-save the exploration artifact to `docs/quirk/explorations/` → offer (never perform) the handoff to `quirk:brainstorming`.
