# Stream Dump

## When to Use
Reach for this when you can sense there's something interesting in a problem but the obvious framings keep producing obvious answers. It's most useful early, before you've committed to a direction, or when a session has stalled on the first two or three safe ideas. Use it when the real constraint is your own editing — you keep filtering thoughts before they're fully formed.

## The Method
1. Set a timer for 8-10 minutes and write everything about the problem in one continuous stream — context, frustrations, half-thoughts, tangents — without organizing, ranking, or stopping to judge.
2. Keep your hand moving past the point where you feel done; the first ideas are the cached ones, so push until you've written at least five or six distinct things.
3. When the stream runs dry, stop and walk away from it briefly so you re-read with fresh eyes rather than as the author.
4. Re-read and mark every aside, parenthetical, or tangent — the lines you wrote almost by accident, not the ones you meant to make.
5. Pull the most surprising marked line out on its own and treat it as a candidate idea: state it as a concrete change and ask what it would take to be true.

## Example
A team is trying to speed up a slow CI pipeline. The stream starts with the safe ideas: parallelize test shards, cache dependencies, upgrade runners. Six paragraphs in, an aside slips out: "honestly half these tests only matter when someone touches the billing module, but we run all 4,000 on every commit." That throwaway line was the real idea. It reframes the goal from "run the same suite faster" to "run only the tests a given diff can actually affect." The team builds change-based test selection keyed to a dependency graph, and median CI time drops 70% — far more than any amount of parallelization would have, because most of the work was never necessary.

## Why It Works
Premature judgment is the enemy of novel ideas; by separating generation from evaluation, you let unguarded associations surface that an internal editor would have killed mid-sentence. The genuinely interesting thought rarely arrives as a headline — it leaks out as an aside, because asides bypass the part of you that's performing competence. This is the free-writing / stream-of-consciousness root of ideation: volume and unfiltered flow first, selection second.
