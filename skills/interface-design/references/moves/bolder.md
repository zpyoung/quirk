# Move: bolder

Raise one part of an existing screen to the conviction the rest of it already implies. Bold means more decisive, not more decorated.

## When to use

- "Make this section bolder", "this feels flat", "give the header more presence".
- One area opts out of strengths its neighbors already use: full-strength type, a clear hierarchy, the signature element.

If a direction decision is still open and the user says "bolder", that is a request for a new direction. Go to Build instead. This move refines a screen whose look is already settled.

Ask which section is the target and what must stay untouched, unless it is obvious.

## Read first

1. `.quirk/design/system.md` if it exists. It is the vocabulary you amplify in: type scale, depth, spacing, the one accent, the signature.
2. The target and its neighbors. Note what the neighbors do that the target doesn't.

## Procedure

1. **Diagnose why it reads flat.** A flat section usually skips the system's strongest moves: the large type step, the structural device that carries meaning, the signature, the density contrast. List which ones it skips.
2. **Make one decisive move.** Bring the target up to the expression level the rest of the screen already reaches, using the system's own tokens. Examples: promote the key figure to the top type step, give the primary action the full accent treatment, tighten the hierarchy so one item clearly leads.
3. **Quiet the surroundings.** If every element gets louder, the section gets flatter. Lower the weight of competing items so the one move reads.
4. **Give it its own rhythm.** The target should be a peak in the scroll or the layout, a change in density or pace, not more of the same.
5. **Don't reach for effects.** Gradients, glows, bigger shadows and extra color are the reflex. They are the opposite of bold in a restrained product UI. The accent stays singular, for action and state.
6. **Don't expand the system.** No new color, font, radius, shadow or primitive unless the user asks. If the system truly can't express the direction, name the exact addition and the job it would do, then ask.
7. **Run the skeleton test.** Blank the copy and look at the structure. Does hierarchy alone say what the section is and why it matters? If it only works with the words back, the boldness is in the text size, not the design.

## Preserve

- Everything outside the named target, byte for byte where you can.
- Copy and every claim in it. Bolder never rewrites facts; if the move needs evidence the screen lacks, ask.
- Behavior of anything that drives an action: links, buttons, shortcuts and their states.
- The incumbent identity. The result should be unmistakably the same product, only more sure of itself.

## Verify

- The diff touches only the target.
- No new color, font or system primitive appeared.
- Actions in the section still work the same way, including focus and hover states.
- The accent still marks only action and state.
- Check the section at desktop and mobile widths, and in dark mode if the product has one.
- Squint at the screen: the target is the first thing the eye lands on, and nothing else lost its place.

## Update system.md

If you changed a token or pattern, such as a larger heading step or a revised primary button, offer once to update `.quirk/design/system.md`. Create the directory if it is missing.
