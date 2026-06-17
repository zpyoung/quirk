# Analogical Transfer

## When to Use
Reach for this when the current problem feels unprecedented or when every solution on the table is a variation of the same obvious approach. It works best when you can name the underlying mechanic of the problem (routing, matching, decay, contention, trust) but the domain-native solutions have stalled. Borrowing structure from a field that has already solved the same mechanic breaks the local maximum.

## The Method
1. State the problem as an abstract mechanic, stripping domain nouns: not "users abandon carts," but "high-intent actors drop off when a decision has too many open variables."
2. Brainstorm 3-5 unrelated domains that face that same mechanic at scale: biology, logistics, sports, finance, ecology, board games, traffic systems.
3. Pick the domain with the most mature, battle-tested solution and study how it actually works mechanically, not metaphorically.
4. Extract the core mechanism as a transferable rule, separate from its original implementation details.
5. Map each element of that mechanism onto a concrete part of your system, and note where the analogy breaks.
6. Keep only the mappings that survive the break; turn them into a candidate design.

## Example
A team building a job queue kept losing throughput because a few slow tasks blocked thousands of fast ones behind them. The default fixes (bigger workers, more partitions) only deferred the stall. They restated it as "shared lane congestion from mixed-speed traffic" and looked at highway design. Highways solve this with dedicated express and local lanes plus metered on-ramps, not wider roads. They added latency-class lanes (sub-second, seconds, minutes) with separate worker pools and an admission limiter on the slow lane. P99 latency on fast jobs dropped by an order of magnitude without adding capacity, because the slow tasks could no longer occupy the express lane.

## Why It Works
Analogical reasoning lets you import a fully evolved solution instead of re-deriving one from scratch under the blind spots of your own field. Because the source domain carries no emotional or political baggage from your codebase, it surfaces moves that feel obvious there but were invisible here. This is the engine behind biomimicry and structural analogy: matching deep relational structure, not surface features, is what produces transferable insight rather than a hollow metaphor.
