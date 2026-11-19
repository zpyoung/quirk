# Move: clarify

Rewrite unclear interface text so users know what happened, what matters and what to do next.

## When to use

- "The copy is confusing", "rewrite these error messages", "label this better", "the empty state doesn't help".
- Vague buttons, jargon, generic errors, placeholders doing a label's job, inconsistent terms.

Ask about audience knowledge and emotional state only if the product context doesn't show them. Ask before changing a factual claim, legal wording or a term that may be domain-specific.

## Read first

1. `.quirk/design/system.md` if it exists, for the product's voice and terminology.
2. The whole interaction path, not isolated strings: the screens before and after, the error, the empty state, the success state.

## Procedure

1. **Audit the language.** Mark ambiguous nouns and verbs, internal jargon, vague outcomes, missing consequences or recovery, inconsistent terms, repeated headings and helper text, and text that will break at narrow widths or in translation.
2. **Set the hierarchy for each state.** Decide the one fact the user needs now, the action available next, any context that changes the decision, and the right tone. Say each idea once. If the heading explains the state, the intro adds something new or goes.
3. **Rewrite by function.**
   - **Actions:** a specific verb and object when the outcome isn't obvious, naming what will happen, not the gesture. One noun and verb per concept across the product. For destructive actions, name the object and the consequence. Prefer undo to confirmation when recovery is safe. When you must confirm, name the action on the button, never Yes, No, OK or Submit.
   - **Forms:** persistent labels, with placeholders as examples only. State format and eligibility before submission. Explain why you ask only when it isn't obvious. Validation says what to fix and how, without blame, next to the field.
   - **Errors:** say what failed, why if known and useful, and how to recover. No internal codes as the main message. Don't promise a cause or fix the system can't know. For payment, privacy, deletion and blocked work, be warm and serious, never jokey.
   - **Loading:** name the real operation. Show determinate progress when you have it and never invent it.
   - **Empty states:** separate first use, no results, active filters, no permission and failure. Explain the state and give the next useful action.
   - **Success:** confirm the outcome. Mention a next step only if it changes what the user should do. Routine success is brief.
   - **Help text:** answer the question the user has instead of restating the control. Link text makes sense out of context.
4. **Keep voice steady and tone adaptive.** Plain language, without flattening terms the audience knows. Don't vary words for style; one concept gets one word.
5. **Write for translation and assistive tech.**
   - Complete messages, not concatenated fragments. Keep variables and plurals structured so translators can reorder them.
   - Leave room for expansion instead of abbreviating.
   - Alt text conveys the image's information; decorative images get empty alt.
   - Accessible names match visible labels. Never carry meaning by color, punctuation or an icon alone.
6. **Record terms.** When inconsistency spans the product, add a short glossary to the response, and to system.md if the user wants it kept.

## Preserve

- Factual meaning, legal meaning, product terminology and brand voice.
- Layout, styling and behavior. Change strings and the text-bearing markup only.
- Strings outside the target path. Report inconsistencies elsewhere; don't sweep them.
- Existing i18n keys and message structure. Edit values, don't rename keys unless asked.

## Verify

- Read the flow in order as someone with no hidden product knowledge. Is each state actionable?
- Check long names, translation expansion, plurals and dynamic values.
- Check at the narrowest target width and at 200% zoom.
- Screen-reader names and announced state changes still match what's shown.
- Tone fits the consequence of the moment.
- The final copy is as short as it can be without losing meaning or recovery.

## Update system.md

If you settled a term, a voice rule, or a message pattern such as the standard error format, offer once to add it under Patterns in `.quirk/design/system.md`. Create the directory if it is missing.
