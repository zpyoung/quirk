# Divergent Ideation (source skill)

This is the original skill spec that `connect-dots` operationalizes as a runnable
tree-of-thought engine. Kept here for reference and as the authoritative description
of the divergence/convergence loop the engine implements.

---

This skill widens the search before it narrows. The default failure mode in idea generation is premature convergence: latching onto the first plausible answer and polishing it. That produces competent, forgettable output. The goal here is to generate a genuinely broad and weird candidate set first, then converge with judgment. Breadth is cheap; a missed idea is expensive.

A note on what this is and isn't: this does not change how the model reasons at a low level. It changes strategy — where attention goes, how long divergence runs before convergence, and what counts as "enough" ideas. Treat it as a deliberate mode, not a personality.

## The core loop

Run two distinct phases. Keep them separate. Mixing them is what kills idea quality, because the critic strangles the generator.

**Phase 1 — Diverge** (generate, no judging). Produce a large set of candidates fast. Suspend evaluation entirely. Bad, obvious, and absurd ideas are all welcome here because they seed better ones. Aim for quantity and variety, not quality. Do not stop at the first 3 — the first 3 are almost always the obvious ones everyone already thought of. Push past the obvious into the awkward middle where the interesting ideas live.

**Phase 2 — Converge** (select with judgment). Now bring the critic back. Cluster the candidates, kill the dead ones, and surface the few worth pursuing. Be honest about tradeoffs. This is where builder-judgment applies: which of these could actually ship, which is most non-obvious-but-viable, which is a trap.

The split matters because the two modes use opposite postures. Divergence rewards "yes, and." Convergence rewards "no, because." Doing them at once gives you neither.

## Techniques to force breadth

Don't free-associate randomly — that drifts toward the familiar. Use structured prompts to push attention into corners it wouldn't naturally go. Pick a few per session; don't grind through all of them.

- **Vary the frame.** Re-ask the question from radically different vantage points: how would a hardware person solve this software problem? A regulator? A 10-year-old? A competitor trying to make it fail?
- **Cross-domain transplant.** Take the mechanism from a distant field and force-fit it. Biology, logistics, game design, immune systems, ant colonies, futures markets, speedrunning.
- **Invert it.** Ask the opposite question. Instead of "how do we get users to stay," ask "how would we drive every user away" — then negate the answers.
- **Push to extremes.** $0 budget / infinite budget. 1 hour / 10 years. Extremes break the anchoring on the reasonable middle.
- **Remove the load-bearing assumption.** Name the thing everyone treats as fixed and ask what becomes possible if it's gone.
- **Combine two unrelated candidates.** Take ideas #3 and #11 from the list and ask what their hybrid looks like.

## Output shape

- **Brief.** One or two lines confirming the problem, including any reframe.
- **The wide set.** Generous list of candidates, grouped into rough clusters labelled by their underlying angle.
- **The converge.** 2–4 most promising, with reasons. Name the most interesting non-obvious one explicitly. Flag traps.
- **One provocation.** A single wild-card idea or open question.

## Anti-patterns

- Convergence disguised as divergence (10 minor variations of one idea).
- Weird-for-weird's-sake with no convergence.
- Walls of equally-weighted prose hiding the good ideas.
- Refusing to commit. After diverging, take a position.
