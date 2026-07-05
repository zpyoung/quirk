# Activation Testing

**Load this when:** a skill isn't firing when it should (or fires when it shouldn't), or before shipping any skill you want to trigger reliably.

## Why this is a separate discipline

A skill has two independent failure modes. This file is about the first one — **activation**: the model never invokes the skill, so the body never runs. It is fixed in the `description`, not the body. (The second mode, execution, is about whether the body is followed once loaded — that's the SKILL.md body and its type-scoped tests.)

Activation is the single most common real-world skill failure: a well-written body is wasted if the skill never fires. Test for it explicitly.

## The description is the trigger

The model decides whether to invoke a skill from its `name` + `description` alone. So the description must:

- State **both what the skill does and when to use it** — not only "when to use". (Anthropic's own skill-creator recommends making descriptions a little "pushy" because models tend to *under*-trigger.)
- Front-load the **trigger phrases a user would actually type** (symptoms, file types, error phrasings, synonyms).
- Be specific. Vague descriptions ("helps with documents") lose to specific ones.
- Optionally include a short **"not for X"** clause to bound the trigger surface and reduce false positives.

Keep it terse enough to be scannable, assertive enough to fire. These are not in tension: specific + trigger-forward + assertive is the target.

## The should-trigger / should-not-trigger test

Before shipping, write a small labeled set and check activation by observation:

1. Write ~5 prompts that **should** invoke the skill (varied phrasings a real user would type).
2. Write ~3 prompts that are **near-misses** and should **not** invoke it.
3. Run each in a fresh session and record whether the skill fired.
4. Rewrite the description toward the phrasings that missed; re-run. Iterate a few rounds.
5. To avoid overfitting to your own examples, hold back a couple of should-trigger prompts you don't tune against, and confirm they fire too.

This is the activation analogue of RED-GREEN: watch it fail to fire, fix the description, watch it fire — without breaking the should-not cases.

## Tooling

Anthropic's official `skill-creator` ships a description-optimization loop (a labeled trigger set, a train/held-out split, repeated runs, iterate) — a good reference if you want to automate this. Community fire-rate auditors that parse session logs can tell you which of your installed skills actually fire vs sit dormant. Prefer measuring over guessing.

## The over-triggering side

More assertive descriptions raise activation but can also cause false positives — a skill firing on unrelated prompts wastes tokens and derails tasks. If you have many skills, tightly-scoped single-purpose descriptions compete less and trigger more predictably than one broad description. Test both directions: fires when it should, stays quiet when it shouldn't.
