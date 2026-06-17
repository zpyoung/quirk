# Radical Simplification

## When to Use
Reach for this when a proposed solution has grown into a multi-stage architecture, a config matrix, or a pipeline with many moving parts — and a quiet instinct says it might be overbuilt. It is especially useful mid-exploration, when the design keeps accumulating special cases instead of converging. Use it to test whether the complexity is load-bearing or just defensive.

## The Method
1. Write down the problem in its most elaborate current form — every stage, service, flag, and edge case the design touches.
2. For each layer, ask: "What real need does this exist to satisfy?" Name the need, not the mechanism.
3. Delete the layer and check whether that named need actually breaks. If it survives, the layer was scaffolding — leave it out.
4. Repeat until removing one more piece would genuinely fail a real requirement; that residue is the structural core.
5. Restate the whole problem as the simplest framing that still serves that core, then check it against the original constraints you set aside.

## Example
A team designs content moderation as a four-stage pipeline: ML toxicity scoring, a rules engine, a human review queue, and an appeals workflow — weeks of integration ahead.
Stripping layers, they ask what each stage really serves. Toxicity scoring exists to keep bad content from dominating. The rules engine encodes the same goal as brittle keyword lists. The queue exists because nobody trusts the automation.
The structural core: surface good content, bury bad content. Reframed, that is a ranking problem, not a gatekeeping one.
Result: ship community upvoting first. Quality rises by selection, the moderation queue shrinks to clear abuse only, and three of four stages never get built.

## Why It Works
Complexity accretes one reasonable decision at a time, so no single step looks removable from inside the design — each layer is justified locally even when the whole is bloated. Forcing every layer to defend a concrete need, rather than its own mechanism, exposes the ones that only protect other layers. This is first-principles reduction: by returning to the irreducible requirement, you often find the simplest framing reclassifies the problem entirely.
