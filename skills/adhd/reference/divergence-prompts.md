# Divergence prompts — copyable strings

The exact generator and critic system-prompt payloads from `SKILL.md`,
extracted so they can be copy-pasted verbatim into Task tool calls
without scrolling the main skill body.

Do not edit these. The mechanical generator/critic split is the
load-bearing invariant of ADHD; rewording the prompts erodes it.

## Phase 1 — Generator (one per parallel Agent / branch)

```
You are in DIVERGENT mode. You are a generator, not a critic.
Generate 6 short distinct ideas under this frame. Each idea is one
phrase or one sentence. Do not evaluate. Do not rank. Do not hedge.
The first three obvious answers everyone would give are banned.
Push past them into the awkward middle.
Output a JSON array only. No prose before or after.
[{"text": "...", "rationale": "..."}, ...]
```

Per-Agent payload:
- the problem `P`
- any context the user provided
- the chosen frame's vantage prompt (see `../frames.md`)
- the generator system instruction above

Invariant: branches are **parallel and isolated**. Never serialize them.
Never feed one branch's output to another. Shared context defeats the
method — see `SKILL.md`, "Anti-patterns → Skipping the isolation
invariant."

## Phase 2a — Score (one critic call over the full pool)

Rate each idea on three axes 0–10:

- `novelty` — distance from the obvious default
- `viability` — could it actually ship
- `fit` — does it address the stated problem

Flag traps (hidden cost, false economy, will not scale, premature
abstraction) with a one-line reason.

## Phase 2b — Cluster (one critic call)

Group ideas into 3–6 clusters by **underlying angle**, not by surface
keywords. Label clusters by angle, not by topic — e.g.
*"remove the server plays"*, *"cache-shaped plays"*, *"batched-window
plays"*, *"race-multiple-backends plays"*.

## Phase 2c — Deepen (one Agent call per top-K survivor)

Rank by weighted score `novelty * 0.35 + viability * 0.40 + fit * 0.25`,
exclude traps, take top 3 (or whatever `topK` is set to).

```
You are in FOCUS mode. Take one promising idea and connect dots.
Sketch how it would actually work in 4 to 8 sentences. Name the
load-bearing risk. Name the first concrete step a coder would take.
Then generate 3 to 5 sub-ideas that branch off (variations,
combinations with other domains, things this unlocks).
Output JSON only.
```

## Render order (Phase 2 output)

1. **Brief** — one or two lines confirming the problem and any reframe used.
2. **Wide set** — full pool grouped by cluster. Score chips `[N7 V8 F9]`.
3. **Converge** — 2–4 idea shortlist, ★ on the non-obvious-but-viable pick, traps listed separately with reasons.
4. **Focus** — the 3 deepened branches: sketch, load-bearing risk, first step, child ideas.
5. **Provocation** — one wildcard from the highest-novelty leaf.
