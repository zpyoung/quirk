# Essential Coverage and the Fast-Track

The coverage gate's reference: what must be established before design begins, and the one way a
user may skip the rest.

This list exists to **generate questions**. It is never written into `logic.md` as a section, a
checklist, or a score. A checklist the model is later measured against gets padded; one that can
only emit questions to a human cannot be.

## The Essential six

Reverse-engineered from what `logic.md`'s required sections cannot be written non-vacuously
without. **This list is original** — it is not taken from research. Published completeness
frameworks all assume a bounded domain with a predefined element set, and no evidence exists for
applying one to open-ended design work. It is grounded in a document that already exists, not in
an experiment.

| Essential item | The question it answers | Section it feeds |
|---|---|---|
| **Purpose** | Why is this being built — what changes if it exists? | Conceptual model |
| **Consumers** | Who or what uses it, and in what context? | Behavior & scenarios |
| **Success criteria** | How do we know it works? | Key decisions |
| **Hard constraints** | What cannot change — imposed, not chosen? | Key decisions, Scope |
| **Scope boundary** | What is deliberately excluded? | Scope & non-goals |
| **Primary behavior** | What is the main path through it? | Behavior & scenarios |

Everything else is **Default-able**: it has a defensible recommended default that may be taken and
logged rather than asked.

**Judge coverage by substance, not by whether a question was asked.** An item is covered when the
answer is established well enough to write its section without inventing anything — whether it came
from the user's original request, an answered question, or the existing codebase. Re-asking what the
user already told you is its own failure.

## Running the coverage gate

After clarifying questions, before proposing approaches:

1. Walk the six. For each, ask: *could I write its section right now without inventing anything?*
2. For every item where the answer is no, that gap becomes a question.
3. Ask the gaps, batched, under the normal per-question rules.
4. When all six are covered, proceed. Say nothing if the gate passes clean — a silent pass is the
   normal case, and announcing it every run is noise.

Under the altitude rule, every gate question is observable-level by construction: all six items are
about what the thing does and for whom, never how it is built.

## The fast-track

**What it is.** The user electing to accept recommended defaults for everything still open, so
design can start now.

**When it is legal.** Only once all six Essential items are covered. Below that, the fast-track is
declined — name the specific items still open, ask them, and do not skip. Declining is not refusing
the user's instruction; it is reporting which decisions cannot be made on their behalf, and then
asking them so the instruction can be honored.

**What happens when it fires.**

1. Every remaining Default-able item resolves to its recommended default.
2. Each resolved item is recorded in Decisions Locked as `<decision> — assumed — fast-tracked`.
3. Design proceeds immediately.

The tag is what makes this safe. An assumed decision that reads identically to an approved one is
exactly what Decisions Locked exists to prevent.

**How it is triggered.** A recognized free-text steer — "enough, design it", "go with your
recommendations", "stop asking and build it", or a clear paraphrase. Recognize the intent, not a
literal string.

**What it is never.** Never an option inside an `AskUserQuestion` call. That would consume one of
only four slots, and it would put a delegation option in front of the user on every call — which
the Checkpoint Rules forbid.

## The line this does not cross

The Checkpoint Rules forbid the skill *offering* to decide. They do not constrain the user
*electing* to accept stated defaults. The skill may never propose "you decide"; the user may always
say "use your recommendations." The `assumed — fast-tracked` tag keeps the result auditable either
way.
