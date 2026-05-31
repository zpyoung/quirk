# When to use ADHD (and when not to)

[← back to README](../README.md)

## Use it for

- Architecture & design decisions (storage layer, sharding, auth model, queue topology, retry strategy)
- API / SDK / CLI surface design
- Fuzzy debugging — generate *hypothesis classes* you haven't considered
- Migration & refactor planning
- Naming — functions, products, services, env vars
- Code review widening — what could go wrong here, beyond the checklist
- Strategy, positioning, pricing — anywhere you'd say *"give me a few ways to…"*
- **Inside agent loops** at decision points where the cost of premature convergence is high

## Don't use it for

- Lookup questions
- Bug fixes with a known root cause
- Anything where the right answer is one Google away
- Inner-loop / tight latency / per-keystroke use
- Single-correct-answer problems

> One-sentence test: *If a junior would Google it and find the answer, baseline wins. If a senior would say "hm, let me think about this differently for a minute" — that's the moment ADHD replaces.*

## Why it shines on creative and interdisciplinary work

Creative and cross-domain work is exactly the regime where premature convergence costs the most.

- The right answer is often **not in any one domain's playbook** — you need to *transplant* a mechanism. ADHD's cross-domain frames (biology, logistics, game design, markets) do this on purpose.
- The textbook answer is usually a **trap** — it looks right because it's familiar. ADHD's separate critic pass flags traps with named reasons, not just "could be risky."
- The interesting ideas live in the **awkward middle** — past the first 3, before the absurd. Single-pass generation never gets there because each token is biased by the previous one. Parallel isolated branches do.
- You don't always know **what good looks like** yet. ADHD's cluster pass surfaces the *shape* of the design space so you can argue at the angle level, not idea-by-idea.

In one line: **ADHD is what to reach for the moment a single-pass agent would give you a competent, forgettable answer.**

## Cost & speed

Honest numbers. A default run is roughly:

- N parallel divergence calls (default 5; can be increased)
- 1 scoring call
- 1 clustering call
- K deepen calls (default 3)

≈ **10 LLM calls per run**, 5–10× a single-shot baseline. Latency depends on concurrency; 30–90s wall clock is typical.

Frame it as: **$0.30 to widen a $50k architecture decision.** Don't run it on every keystroke. Run it at decision points.

> Note: the per-run cost depends on your base context. Inside a Claude Code session with a large `CLAUDE.md` + tool context, each of the N branches re-loads that base substrate, so real token cost is closer to `N × (base + branch)`. See [issue #8](https://github.com/UditAkhourii/adhd/issues/8).
