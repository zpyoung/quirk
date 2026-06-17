# Contrarian Inversion

## When to Use
Reach for this when the exploration keeps circling the same consensus answer and every idea sounds like a variation of what already exists in the space. It's especially useful when "best practice" is treated as settled and unquestioned. Use it to break out of a crowded design space where everyone is optimizing along the same axis.

## The Method
1. State the dogma plainly: the one assumption every serious player in this space treats as obviously true.
2. Argue the literal opposite as if you had to ship it — no irony, no hedging.
3. Build the contrarian case only from things that are actually true (constraints, costs, second-order effects), not from contrarianism for its own sake.
4. Stress-test it: where does the opposite collapse, and where does it quietly hold?
5. Find the specific edge case or segment where the contrarian take genuinely wins — that narrow context is your wedge.
6. Design the idea for that wedge first, ignoring the mainstream case entirely.

## Example
Dogma: "A code editor must be fast and responsive; latency is the enemy."
Inversion: "What if the editor were deliberately slow to act?"
Building the case: instant autocomplete and auto-apply train developers to accept changes they never read; speed optimizes for keystrokes, not comprehension.
The wedge: for AI-generated edits in high-stakes code, a forced review pause is a feature, not a regression.
Result: an "intentional friction" mode that holds AI diffs in a staging buffer with a mandatory diff-read step before apply — slower per edit, far fewer silently-merged regressions. The slowness is the product.

## Why It Works
Consensus assumptions act as invisible walls: the whole space optimizes inside them, so the unexplored ideas all live outside. Seriously inverting the dogma forces a search in the region everyone else has pre-pruned, and grounding the case in real constraints keeps it from being mere provocation. This is inversion (via negativa) — you find the good idea by first asking how the obvious one fails.
