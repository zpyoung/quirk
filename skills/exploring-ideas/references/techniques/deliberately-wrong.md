# Deliberately Wrong

## When to Use
Reach for this when the session keeps producing sensible, predictable ideas and you suspect your own reality-check filter is killing options before they're examined. It's most useful when a domain has hardened "everyone knows" assumptions that nobody has questioned in years. Use it to break a stall, not to polish a near-final idea.

## The Method
1. Name the load-bearing assumption you're treating as obviously true ("our system must be reliable," "users want fewer steps").
2. Invert or corrupt it into a deliberately dumb provocation: "What if X, but [the stupid version]?"
3. Set a 60-second timer and take the provocation completely seriously — no laughing it off, no "but obviously not."
4. Trace the concrete consequences: what would you build, change, or measure if this were the actual goal?
5. Extract the salvageable principle — the real insight hiding inside the joke — and restate it as a usable idea.
6. Repeat with a different corrupted assumption if the first yields nothing.

## Example
A team building a payments service holds the assumption "our software must be reliable." The deliberately wrong twist: "What if our software was intentionally unreliable?" Taken seriously for 60 seconds, this means deliberately killing processes, dropping connections, and injecting latency in production. Following that thread lands on chaos engineering: you can't claim reliability you've never stress-tested, so you engineer controlled failure to expose hidden coupling and weak fallbacks. The "dumb" idea is now Netflix's Chaos Monkey — a standard resilience practice, not a joke.

## Why It Works
Sensible ideas trigger immediate self-censorship; an obviously absurd premise slips past that filter because the brain doesn't bother defending against something it has already dismissed. Forcing 60 seconds of serious follow-through converts the provocation into a movement away from the assumption rather than a verdict on it. This is de Bono's provocation operation ("po"): a deliberately unreasonable statement used not for its truth but for the new directions it forces you to consider.
