# Field catalogs

Per-type field sets, what inspection can settle, and how to ask for what it cannot.

The cores below are fixed by the logic spec — they are product decisions, not implementation
detail. When a repo template applies, its sections seed the field list and these cores are
*additive*: a template can add requirements, never subtract them. See
`template-resolution.md`.

**Read the inspection column before the question column.** Anything the repo can answer is not
asked. That is the whole point.

---

## Bug

**Core:** `current_behavior`, `expected_behavior`, `steps_to_reproduce`, `environment`
**Optional:** `stack_trace`, `frequency`, `regression_range`, `workaround`

Inspection typically resolves `environment` and often `regression_range`. The rest are usually
`reported` — they are what the reporter saw, and you were not there.

| Field | Inspection strategy | Ask, if inspection can't settle it |
|---|---|---|
| `current_behavior` | Reproduce it at `run` depth; at `read` depth, read the code path the description implicates | "What happens — the exact symptom, not the diagnosis?" |
| `expected_behavior` | Read the docs, the tests, or the docstring for the stated contract; cite it as `source` | "What did you expect instead?" |
| `steps_to_reproduce` | Rarely inspectable. A failing test that exercises the path is the exception | "What did you do, in order, right before it happened?" |
| `environment` | **Usually resolvable.** Read `pyproject.toml` / `package.json` / lockfiles for versions; `python3 -V`, `git rev-parse HEAD` | "Which version, and on what OS/runtime?" |
| `stack_trace` | If the user pasted one, it is `reported`. Never reconstruct one | "Do you have the traceback?" |
| `frequency` | Not inspectable | "Every time, or intermittently?" |
| `regression_range` | **Often resolvable.** `git log` between the last known-good version and now, narrowed to the implicated path | "Did this used to work? Which version last did?" |
| `workaround` | Not inspectable | "Is there something you're doing to get around it?" |

**`missing` is acceptable on every one of these**, including `steps_to_reproduce`. Maintainers say
they prefer an honest "intermittent; observed 3× over two weeks with no identified trigger" to a
fabricated recipe. The reason is itself diagnostic.

---

## Feature

**Core:** `problem`, `who_benefits`, `current_behavior`, `acceptance_criteria`
**Optional:** `value_or_impact`, `constraints`, `out_of_scope`, `prior_art`

This is the type where inspection helps least. A feature session is closer to a pure interview, and
the edge over a web form narrows to two things: you verify the capability doesn't already exist and
wasn't already rejected, and you refuse to emit without a testable criterion. Both are worth
having. Don't pretend the session is doing more than that.

| Field | Inspection strategy | Ask, if inspection can't settle it |
|---|---|---|
| `problem` | Not inspectable — and **non-waivable** | "What can't you do today, and what does that cost you?" State it as a problem, not a solution. If the user answers with a solution, ask what it would let them do |
| `who_benefits` | Not inspectable — irreducibly human | "Who hits this, and how often?" |
| `current_behavior` | **Normally a negative observation.** Grep for the capability; read the module that would own it. Record what you searched as the `source` so a reader can judge the search | "Is there an existing way you're working around this?" |
| `acceptance_criteria` | Not inspectable — and **non-waivable** | "How would we know it's done? Give me one case: given…, when…, then…" |
| `value_or_impact` | Not inspectable | "What changes for you once this exists?" |
| `constraints` | **Partially resolvable.** Language-version floors, declared platform support, architectural boundaries — all in config and structure | "Anything it has to keep working with?" |
| `out_of_scope` | Not inspectable | "Anything adjacent you specifically *don't* want?" |
| `prior_art` | **Partially resolvable.** Does a similar mechanism already exist in-repo? Is there a `DECISIONS`/ADR entry on it? | "Have you seen this done elsewhere?" |

`problem` and `acceptance_criteria` are **non-waivable**: they cannot be resolved by marking them
`missing`. If either can't be established, the session halts rather than emitting. A feature
request with no stated problem and no testable criterion is a wish, and filing it wastes the
maintainer attention this skill exists to protect.

---

## Code-change

**Core:** `scope`, `why_now`, `blast_radius`
**Optional:** `migration`, `rollback`, `test_plan`, `perf_impact`

The type where inspection buys the most question budget — the affected modules and their callers
are discoverable, so two of three core fields are substantially resolvable.

| Field | Inspection strategy | Ask, if inspection can't settle it |
|---|---|---|
| `scope` | **Substantially resolvable.** Read the modules the description names and list them concretely | "Which parts are in scope — and which are you deliberately leaving alone?" |
| `why_now` | Not inspectable. Sometimes hinted by a blocking issue or a version floor | "What makes this the right moment?" |
| `blast_radius` | **Substantially resolvable.** Grep for callers/importers of the touched symbols; check whether the surface is public | "Anything downstream you know of that we can't see from here?" |
| `migration` | Partially — is there existing migration machinery? | "Do existing users need to do anything?" |
| `rollback` | Partially — is the change behind a flag, or a one-way door? | "How do we back this out?" |
| `test_plan` | **Resolvable.** Read the existing test files covering the touched paths | "Anything a test can't cover that you'd want checked by hand?" |
| `perf_impact` | Only at `run` depth, and only with a benchmark that already exists | "Is throughput or latency a concern here?" |

---

## Wording rules

These apply to every question above.

- **One question per turn** where the answer shapes the next one. Batch only genuinely independent
  fields.
- **Ask for the observation, not the diagnosis.** "What happened?" beats "What's the bug?" — the
  latter invites a theory, and a theory recorded as `reported` is the entry point for invented
  specificity.
- **Never suggest the answer inside the question.** "Is it a Unicode problem?" gets you agreement,
  not evidence.
- **When you inspected first, say so.** "I see `pyproject.toml` pins 3.9 — is that where you're
  hitting it?" is a better question than "What version?", and it shows the work.
- **Terseness ceiling.** Roughly one to three sentences per field. `steps_to_reproduce` and
  `stack_trace` are the payload and are exempt; everything else that runs long is padding. This is
  a constraint on what you write into a field's `value`, not something the renderer enforces.
