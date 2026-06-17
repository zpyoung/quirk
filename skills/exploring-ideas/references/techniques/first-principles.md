# First Principles

## When to Use
Reach for this when an idea space feels locked in by convention — "this is just how authentication works," "everyone uses a queue here," "the framework requires it." It is the right move when you suspect the real constraint is inherited practice rather than physics, cost, or a hard requirement. Use it to break out of incremental variations on an existing design and reach a genuinely different solution.

## The Method
1. State the goal as an outcome, stripped of any implementation: what must be true for the user or system, with no mention of current tools or patterns.
2. List every assumption baked into the present approach, then label each as a hard constraint (law of physics, contract, budget, regulation) or an inherited convention.
3. Discard every item labeled convention. Keep only the irreducible truths and genuine constraints.
4. Rebuild a solution using only the kept items, asking "what is the simplest thing that satisfies these and nothing more?"
5. Reintroduce discarded conventions one at a time, only where the rebuilt design genuinely needs them — and justify each readmission.

## Example
A team needs to show "items near me" in a mobile app. The ordinary approach: store lat/long, on each request run a geospatial query against PostGIS, add read replicas as traffic grows. Decomposed to fundamentals — the goal is "return the ~50 nearest items in under 100ms"; the hard constraints are item count (low millions) and the precision users actually perceive (a few hundred meters). The convention being discarded: that proximity must be computed live per request. Rebuilt from there, they precompute each item's geohash prefix and bucket items by cell. A "nearby" lookup becomes a key fetch on a handful of neighboring cells — no spatial index, no replicas, sub-millisecond, and trivially cacheable.

## Why It Works
Most design space is occupied by analogy: we copy the shape of solutions we have seen rather than reason from the problem itself. First-principles reasoning, rooted in Aristotle and revived in physics, forces a separation between what is necessarily true and what is merely customary — and the customary layer is usually where the unnecessary cost and complexity hide. Removing it exposes solution paths that the analogical mind never lists because they do not resemble anything familiar.
