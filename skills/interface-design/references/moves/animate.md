# Move: animate

Add motion that explains state, relationship or continuity. In product UI, motion is feedback, not decoration.

## When to use

- "Add transitions", "this feels abrupt", "the panel just pops in", "animate this".
- A state change, reorder, open or close that the user can't follow.
- A control that gives no acknowledgment when pressed.

Ask only about a performance constraint you can't infer, such as a low-end target device.

## Read first

1. `.quirk/design/system.md` if it exists. Reuse its motion durations and easing; don't add a second set.
2. The existing motion in the target: transitions, keyframes, the project's motion library.
3. Native target: read `surfaces/ios.md` or `surfaces/android.md` and follow its motion section, including Reduce Motion. Skip the web guidance below.

## Procedure

1. **Find the job.** Motion earns its place only when it does one of these:
   - acknowledges an action;
   - makes a state change or spatial relationship legible (a row removed, a panel opened from a button);
   - keeps continuity through navigation or layout change;
   - directs attention to something that just changed.

   Don't animate a static area because it exists.
2. **Write a three-line plan before coding.** Continuity (what changes need explaining), feedback (which controls need acknowledging), budget (which effects cost something and how often they run). Skip the plan for a one-control change.
3. **Pick the smallest change that makes cause and result clear.** Opacity, a short translate, a color change, a size change on an element the user just acted on. Reach for shared-element motion or view transitions only when continuity across states is the point. One idea per interaction; don't stack techniques.
4. **Time it for product use.** Product motion stays in 150-250 ms and conveys state only. Go outside that range only when the user explicitly asks.

   | Duration | Use |
   |---|---|
   | 150 ms | press and hover feedback, exits |
   | 200 ms | state change, menu, popover, tab switch |
   | 250 ms | overlay or panel that travels a long way |

   Exit faster than enter, both inside the range. Use ease-out for arrivals, such as `cubic-bezier(0.16, 1, 0.3, 1)`. No bounce or elastic curves by reflex. Long feedback reads as latency. Stagger a list only when it appears as a list, and cap the total delay at about 200 ms.
5. **Implement with the stack you have.** CSS transitions for state, keyframes for bounded sequences, the Web Animations API or the existing library for interruption and dynamic values. Don't add a dependency for an effect CSS can do.
6. **Name properties.** Never `transition: all`. Don't animate `width`, `height`, `top`, `left` or margins; use transforms, FLIP or grid-row tricks. Keep blur, filter and shadow work in small regions. Set `will-change` only during a known animation.
7. **Keep content visible by default.** If the script fails or the animation never starts, the UI must still show everything.
8. **Add a reduced-motion path.** Every web animation gets a `prefers-reduced-motion` alternative. Drop spatial movement and keep opacity, color and state changes that carry meaning. Reduced motion means fewer, gentler animations, not none; confirmation feedback must stay legible.
9. **Stop loops.** Nonessential loops pause when offscreen or hidden. Respect autoplay and sound preferences.

If the user asks for one authored moment, such as a first-run reveal, keep it to one, make it skippable, and keep it out of the repeated path.

## Preserve

- Layout, copy, color and component structure. Motion is added; nothing else changes.
- Existing motion that already works. Retime it to the system's durations only if it is off-system.
- Focus order and keyboard behavior. An animation never delays focus or input.

## Verify

- Each animation answers "what does this tell the user?" If removing it loses nothing, remove it.
- Durations sit in the 150-250 ms product range, with exits quicker than entrances.
- Interrupt it: click twice fast, reverse mid-way, navigate away. The state stays correct.
- Repeated use stays pleasant on the hundredth pass.
- With `prefers-reduced-motion` on, movement is gone and state changes are still visible.
- Keyboard and touch paths work. Profile expensive effects on the target device and viewport.
- Run the detector over the changed files. `motion-transition-all`, `motion-layout-property` and `motion-no-reduced-motion` should be clear.

## Update system.md

If you introduced a duration, easing curve or motion pattern, offer once to record it under Patterns in `.quirk/design/system.md`. Create the directory if it is missing.
