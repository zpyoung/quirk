# Move: delight

Add character at the few moments that earn it. Delight in product UI is a useful response, a humane word or a considered detail, never a layer of whimsy.

## When to use

- "It feels sterile", "add some personality", "make completion feel good", "the empty state is dull".
- First use, completion, recovery from an error, or mastery moments with no acknowledgment.

Ask only if the product's emotional range or the stakes can't be inferred from the code and copy.

## Read first

1. `.quirk/design/system.md` if it exists, for the direction and feel it records.
2. The target, the product's existing voice, how often users hit this moment, and their emotional state when they do.

## Procedure

1. **Find the moment.** Look for effort worth acknowledging, waiting that could inform, an empty or first-use state that could orient, an error that needs empathy, an interaction whose response could carry the product's character, or a real capability users might enjoy finding. Don't celebrate an ordinary click.
2. **State one thesis.** One sentence: what should the user feel, and why does that belong to this product? Pick the smallest thing that delivers it:
   - a distinctive response to a meaningful action;
   - product-specific wording that clarifies and carries voice;
   - a short transition with a recognizable material feel;
   - a small illustration, sound or haptic grounded in the product's domain;
   - a discovery that reveals real utility.
3. **Build for the moment.**
   - **Success:** match the response to the effort. A milestone can expand. A routine save should just feel certain.
   - **Waiting:** show truthful progress or useful context. Never fake work or delay completion for a flourish.
   - **Empty and first use:** make the next action clear before adding personality.
   - **Error and recovery:** lead with the problem and the way out. Warmth helps. Jokes never touch loss, money, privacy or blocked work.
   - **Repeat use:** it must still feel right the hundredth time. Variation is fine only when it stays predictable.
   - **Discovery:** reward curiosity without hiding required functions.
4. **Write in the product's language.** Generic whimsy is worse than neutral clarity.
5. **Keep it restrained.** In product UI, motion is 150-250 ms and conveys state. Don't add a second accent color. If the moment needs authored motion, apply the animate move's rules for timing and reduced motion.

## Preserve

- The primary task's speed and clarity. A flourish never delays, blocks or hides it.
- Platform conventions and accessibility: screen readers, keyboard, touch, localization.
- Factual claims. Don't add statements the product hasn't made.
- Everything outside the moment you chose.

Don't add sound without consent. Don't make anything mandatory, unskippable or tiring on repeat. Don't add a dependency or asset weight out of proportion to the moment. Stop nonessential loops when the page is hidden.

## Verify

- The moment is specific enough that a neighboring product couldn't use it unchanged.
- It improves comprehension, confidence or emotional recovery.
- The interface is just as fast and obvious with the flourish stripped.
- Repetition doesn't turn charm into friction.
- Muted, keyboard, touch, reduced-motion and translated paths all work.
- It reads as this product, not a generic delight treatment.

## Update system.md

If you introduced a reusable pattern, such as a success acknowledgment or empty-state voice, offer once to record it under Patterns in `.quirk/design/system.md`. Create the directory if it is missing.
