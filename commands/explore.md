---
description: Deep research or brainstorm a topic WITHOUT producing a spec — yields a cited briefing / idea-landscape. Optional intensity via --wild 0.1–1.0 and involvement via --involve low|medium|high.
---

Invoke the `quirk:exploring-ideas` skill to explore the following, with NO spec, requirements, or implementation as output:

$ARGUMENTS

Notes:
- If `$ARGUMENTS` contains `--wild <0.1–1.0>` (or a bare decimal), use it as the intensity; otherwise default to `0.5`. Bare numbers map to `--wild` only — never to `--involve`.
- If `$ARGUMENTS` contains `--involve <low|medium|high>` (aliases `lo`/`med`/`hi`), use it as the involvement level; otherwise default to `medium`. It is changeable mid-session: "check in less" drops a level, "check in more" raises one.
  - **low** — today's behavior: light scoping + handoff only, no checkpoints.
  - **medium** (default) — adds a plan-preview checkpoint and an idea-landscape co-creation gate (react / go-deeper / add-your-own; no ranking).
  - **high** — also adds a post-research checkpoint and a pre-save artifact review, plus per-direction depth prompts.
- Checkpoints auto-skip when the run is headless/non-interactive; the would-be decisions are logged in the artifact.
- Detect emphasis (research-heavy vs ideation-heavy) from the wording; confirm only if genuinely ambiguous.
- Follow the skill exactly: light scoping → research loop and/or divergent pass → challenge pass → auto-save the exploration artifact to `docs/quirk/explorations/` → offer (never perform) the handoff to `quirk:brainstorming`.
