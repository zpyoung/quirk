# Tech Spec — `adversarial-review` skill

**Status:** Draft — authored 2026-07-27
**Logic spec:** [`logic.md`](./logic.md)

## Architecture

A new self-contained skill at `skills/adversarial-review/`, plus a migration that turns SDD's two
inline adversarial assets into delegations.

```
skills/adversarial-review/
  SKILL.md                       # protocol hub: when to use, stages, depth dial, verdict contract
  profiles/
    code-diff.md                 # attack surface, evidence rules, pre-pass commands per type
    spec-design.md
    plan.md
    prose-claim.md
  assets/
    promote-prompt.md            # stage-1 dispatch template
    refute-prompt.md             # stage-2 dispatch template (kill mandate)
    tiebreak-prompt.md           # deep-depth third-family template
    composition-contract.md      # what a calling skill fills in and what it gets back
  scripts/
    adversarial-review           # python3 stdlib, subcommands (below)
commands/
  adversarial-review.md          # /quirk:adversarial-review slash command
tests/
  test_adversarial_review.py     # script unit tests
  test_adversarial_review_skill.py  # skill/profile/asset structural tests
```

**Technologies.** Python 3.9+, standard library only — matches every existing script under
`bin/` and `skills/subagent-driven-development/scripts/`. No new dependencies. Model dispatch is
performed by the invoking agent via the `Task` tool or `pi-watch`; the script never dispatches a
model itself.

**Division of responsibility.** The script owns what is mechanically checkable (target resolution,
profile detection, pre-pass execution, model preflight, schema validation, evidence gating,
suppression counting, verdict computation, manifest assembly). `SKILL.md` and `profiles/` own
judgment (attack surfaces, the refute mandate, adjudication). This mirrors SDD's split between
`scripts/sdd-*` and its prose `SKILL.md`. Back-link: logic.md § Conceptual model.

## Code references

### Files to create

| Path | Purpose |
|---|---|
| `skills/adversarial-review/SKILL.md` | Skill hub; frontmatter `name: adversarial-review` |
| `skills/adversarial-review/profiles/{code-diff,spec-design,plan,prose-claim}.md` | Per-type profile |
| `skills/adversarial-review/assets/{promote,refute,tiebreak}-prompt.md` | Stage dispatch templates |
| `skills/adversarial-review/assets/composition-contract.md` | Caller-facing contract doc |
| `skills/adversarial-review/scripts/adversarial-review` | Executable, `#!/usr/bin/env python3` |
| `commands/adversarial-review.md` | Slash command, frontmatter `description:` only; `/quirk:adversarial-review` per logic.md § Purpose |
| `tests/test_adversarial_review.py` | Script behavior |
| `tests/test_adversarial_review_skill.py` | Structural assertions |

### Files to modify (SDD migration)

| Path | Line anchors | Change |
|---|---|---|
| `skills/subagent-driven-development/assets/codex-adversarial-prompt.md` | whole file | Replace body with a delegation that fills `composition-contract.md` |
| `skills/subagent-driven-development/assets/pi-codex-adversarial-prompt.md` | whole file | Same, pi dispatch path |
| `skills/subagent-driven-development/SKILL.md` | 75, 450–451, 576, 585, 631–633 | Depth selector replaces the on/off Codex gate; drop `CODEX-DEFERRED` |
| `skills/subagent-driven-development/assets/captain-prompt.md` | 138, 141, 146, 148 | Same, Claude path |
| `skills/subagent-driven-development/assets/pi-captain-prompt.md` | 61, 64, 70, 71 | Same, pi path |

Back-link for the whole migration: logic.md § Decisions Locked → Integration.

### Existing patterns to follow

- `skills/subagent-driven-development/scripts/sdd-acceptance` — argparse structure, JSON-to-stdout,
  `print(f"...: {exc}", file=sys.stderr)` + `return 2` error convention, `raise SystemExit(main())`.
- `skills/subagent-driven-development/scripts/sdd-ledger` — subcommand dispatch shape.
- `tests/test_sdd_ledger.py:14-25` — the `subprocess.run([sys.executable, str(SCRIPT), ...])`
  invocation harness for a skill-local script. Reuse verbatim; `tests/conftest.py` `run_script`
  only covers `bin/`, not skill scripts.
- `commands/artifacts/adr.md` — slash-command shape: frontmatter `description:`, then
  `${CLAUDE_PLUGIN_ROOT}` paths and per-exit-code handling instructions.

## Contracts & interfaces

### Script subcommands

`CONTRACT:`
```
adversarial-review resolve   --target <str> [--profile <name>] [--repo-root <path>]
  -> stdout: ResolveResult ; exit 0 ok, 2 usage/IO error

adversarial-review prepass   --profile <name> --target <str> [--repo-root <path>]
                             [--check-cmd <cmd> ...]
  -> stdout: PrepassResult ; exit 0 all checks pass, 1 one or more failed, 2 error

adversarial-review select-model --author-family <family> [--model <alias>]
                                [--check-cmd <cmd>]
  -> stdout: ModelSelection ; exit 0 resolved, 1 no rung resolved, 2 error

adversarial-review gate      --findings <path> [--depth <quick|standard|deep>]
                             [--repo-root <path>]
  -> stdout: GateResult ; exit 0 PASS, 1 NEEDS_FIXES, 3 CRITICAL_ISSUES, 4 NOT_REVIEWABLE, 2 error

adversarial-review manifest  --resolve <path> --prepass <path> --model <path> --gate <path>
                             [--lens <str>]
  -> stdout: Manifest ; exit 0 ok, 2 error
```

Preconditions: every `--*` path argument must be an existing readable file containing the JSON
emitted by the named upstream subcommand. Postconditions: exactly one JSON object on stdout,
`sort_keys=True`; all diagnostics on stderr. Invariant: no subcommand writes to the repository or
mutates its inputs. Error behavior: `ValueError`/`OSError` → message on stderr prefixed
`adversarial-review: `, exit 2.

Back-link: logic.md § Composition contract.

### Evidence-gate semantics (interpretation — see Escalation below)

`CONTRACT:`
```
verified   : evidence re-resolves AND >=1 item of kind "command" | "prepass"
             -> severity unchanged, confidence unchanged
unverified : evidence re-resolves, no reproduction item
             -> severity unchanged, confidence capped at "LOW"
falsified  : evidence does NOT re-resolve (path/line absent, quote not present in
             artifact, or absence-search now returns hits)
             -> finding dropped, suppressed_count += 1
```

Verdict is computed from surviving **severity** only, per logic.md's verdict table; confidence
never affects it.

### Stage tool grants and tie resolution

`CONTRACT:`
```
promote  : tools read,grep,find,ls,bash(read-only)   # may run its own verification commands
refute   : tools read,grep,find,ls,bash(read-only)   # same grant, fresh context
tiebreak : tools read,grep,find,ls                   # adjudicates, does not re-verify
```

Neither stage receives `edit` or `write`. This mirrors `skills/subagent-driven-development/SKILL.md`
line 594 ("reviewers receive `read,grep,find,ls`"), extended with read-only `bash` because
logic.md § Decisions Locked grants the reviewer its own verification commands.

A finding is *contested* when refute rejects it and supplies a counter-argument rather than
falsifying its evidence.

`CONTRACT:`
```
depth quick | standard : refute wins    -> finding dropped, suppressed reason "refuted"
depth deep             : contested findings go to tiebreak; tiebreak verdict is final
```
Falsified evidence is never contested — it is dropped at any depth, since the drop is mechanical
rather than a judgment. Back-link: logic.md § Decisions Locked → Reviewer supply & adjudication.

### Unfalsifiable-claim detection

The promote stage emits a finding with `category: "unfalsifiable-claim"` when the artifact's
central claim admits no test. `gate` treats this category specially:

`CONTRACT:`
```
unfalsifiable-claim present            -> sorted first in findings[], severity as reported
unfalsifiable-claim present AND it is
  the only finding AND prepass could
  not run                              -> verdict NOT_REVIEWABLE
otherwise                              -> normal verdict computation, review proceeds
```

Back-link: logic.md § Decisions Locked → Evidence across artifact types.

### Human summary

`gate` output is machine-readable only. `SKILL.md` instructs the invoking agent to render a
summary of at most 10 lines above the findings block: verdict, reviewer alias with its
`independence` flag, counts by severity, suppressed count, and the single highest-severity claim.
The summary is always derived from `GateResult` — never independently authored — so the two
cannot drift. Back-link: logic.md § Decisions Locked → Output format.

## Data models / schemas

`SCHEMA:` Finding (the unit both stage prompts emit and `gate` validates)
```
id            : str, "F" + positive int
severity      : "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
confidence    : "HIGH" | "MEDIUM" | "LOW"
category      : str, kebab-case, <=40 chars
claim         : str, non-empty, one sentence
evidence      : array, >=1 item
remediation   : str, non-empty
patch         : str (unified diff) | null
stage         : "prepass" | "promote" | "refute" | "tiebreak"
```

`SCHEMA:` Evidence item — `kind` selects which other fields are required
```
kind = "file-line" : ref (path:start-end), quote
kind = "quote"     : ref (section anchor), quote
kind = "command"   : command, output          # reproduction
kind = "absence"   : command, output (empty), ref (scope searched)
kind = "prepass"   : ref (check name), output
```

`SCHEMA:` ResolveResult
```
profile          : "code-diff" | "spec-design" | "plan" | "prose-claim"
target_kind      : "git-range" | "worktree" | "path" | "inline"
target_ref       : str
artifact_hash    : str        # sha256 of content, or resolved git SHA
size_metric      : int        # changed lines for code, words for prose
depth_suggestion : "quick" | "standard" | "deep"
contract_surface : bool
```

`SCHEMA:` ModelSelection
```
alias        : str
family       : "anthropic" | "openai" | "google" | "other"
independence : "full" | "reduced"
ladder       : array of {alias, checked, resolved}
```

`SCHEMA:` GateResult
```
verdict          : "PASS" | "NEEDS_FIXES" | "CRITICAL_ISSUES" | "NOT_REVIEWABLE"
findings         : array of Finding (survivors, with confidence caps applied)
suppressed_count : int
suppressed       : array of {id, reason}
```

`SCHEMA:` Manifest — the replay record from logic.md § Composition contract
```
reviewer      : {alias, family, provider, model, thinking, independence}
target        : {kind, ref, artifact_hash, size_metric}
profile       : str
depth         : str
lens          : str | null
prepass       : {status, checks: [{name, command, exit_code, status}]}
suppressed_count : int
verdict       : str
```

## Depth and profile rules

`CONFIG:` depth auto-selection (`resolve --> depth_suggestion`)
```
deep     : size_metric > 150 (code) OR contract_surface == true
quick    : size_metric <= 50 (code) OR size_metric < 500 (prose)
standard : otherwise
```

`REGEX:` contract-surface detection over changed hunks
```
^\+.*\b(CONTRACT|SCHEMA):
```

Back-link: logic.md § Data flow → Depth dial.

`CONFIG:` profile detection precedence (first match wins; `--profile` overrides all)
```
1. target contains ".."                        -> code-diff   (git range)
2. target empty / "WORKTREE"                   -> code-diff   (worktree)
3. path under docs/plans/ or basename ~ plan*  -> plan
4. basename in {logic.md, tech.md} or under docs/adr/
   or basename matches (spec|design)           -> spec-design
5. path suffix .md                             -> prose-claim
6. otherwise                                   -> code-diff
```

Back-link: logic.md § Decisions Locked → Evidence across artifact types (typed profiles,
auto-detected and caller-overridable), and § Data flow steps 1–2.

## Pre-pass definitions

**code-diff.** Commands are discovered by probing the repo root, in this order, and may be
overridden with repeatable `--check-cmd`:

`COMMAND:`
```
pyproject.toml present   -> python3 -m pytest -q
package.json present     -> pnpm test
Cargo.toml present       -> cargo test --quiet
```

**Prose profiles** (`spec-design`, `plan`, `prose-claim`) run two model-free checks:

1. **Reference resolution.** Extract every backtick-quoted token and markdown link target. Classify
   and verify: a token containing `/` or a known source suffix is a path (`Path.exists()` from repo
   root); a token matching an identifier shape is a symbol (`git grep -nF`); a leading word matching
   an executable is a command (`shutil.which`); relative markdown links must resolve to a file.
   `http(s)` links are recorded as `skipped` and never fetched — the script performs no network I/O.
2. **Section coverage.** Each profile declares required headings; the check greps the document for
   each and reports misses.

`CONFIG:` required headings per profile
```
spec-design : Purpose|Overview ; Scope|Non-goals ; Decisions Locked
plan        : Task ; Contract ; Acceptance
prose-claim : (none — coverage check reports "not-applicable")
```

Every failed reference resolution becomes a `stage: "prepass"` Finding at severity `HIGH`,
confidence `HIGH`, with a `kind: "prepass"` evidence item — true by construction, so it bypasses
the promote/refute stages entirely. Back-link: logic.md § Data flow step 3.

## DO-NOT-CHANGE fences

- **`skills/subagent-driven-development/scripts/*`** — the four SDD scripts are covered by
  `tests/test_sdd_{acceptance,dispatch,ledger,wave}.py` and carry the run-pinning and artifact
  guarantees the captain protocol depends on. *Why fenced:* this work adds a peer script; it has no
  reason to alter dispatch, ledger, or wave mechanics, and doing so would break a working pipeline.
- **`skills/subagent-driven-development/SKILL.md` §§ Runtime Selection, Mode mechanics, Dispatch
  hygiene, Run ledger** (lines ~55–110, 275–330, 386–435, 542–566) — *Why fenced:* the migration
  changes only *when* an adversarial pass runs and *which* template it fills. Escalation routing,
  merge lanes, and dispatch hygiene are orthogonal and independently tested.
- **`skills/requesting-code-review/`** — *Why fenced:* logic.md § Scope & non-goals keeps the
  cooperative reviewer intact as a deliberate decision.
- **`bin/`, `hooks/`, `templates/`** — *Why fenced:* typed-artifacts surface, unrelated to this work.

## Always / Ask / Never

**Always**
- Emit exactly one JSON object on stdout per subcommand; diagnostics to stderr only.
- Gate every real `pi-watch` dispatch on `pi-watch --check <alias>` exit 0, per `skills/pi-dev/SKILL.md`.
- Record the resolved reviewer in the manifest, including `independence` when fallback lands on the author's family.
- Keep the script to the Python standard library.

**Ask**
- Any change to a `logic.md` Decisions-Locked entry (escalate, amend, then proceed).
- Whether to preserve SDD's `CODEX-DEFERRED` skip behavior if the added cost of `quick` passes proves unwelcome.

**Never**
- Dispatch a model from inside the script.
- Perform network I/O in the pre-pass.
- Write to the repository, the target, or any worktree from any subcommand.
- Apply a patch. Patches are emitted as data; callers apply them under SDD's existing size and scope guards.

## Cross-cutting

**Security.** The artifact under review is untrusted input — logic.md's Industry Insights records
that review agents are susceptible to framing effects embedded in reviewed material. Both stage
templates must fence the artifact in a delimited block and state that instructions appearing inside
it are data, never directives. The pre-pass shells out for `git grep` and discovered check commands;
all argument-vector invocations except the discovered check commands, which run through the shell
exactly as declared (the `sdd-acceptance` precedent).

**Observability.** The manifest is the audit record. `gate` reports `suppressed` with a per-finding
reason so an abnormal kill rate is diagnosable rather than merely visible.

**Rollback.** The skill is additive. The SDD migration is the only destructive change; it is a
separate task, committed separately, and revertible without touching the new skill.

## Testing strategy

`tests/test_adversarial_review.py` — script behavior, using the `test_sdd_ledger.py` subprocess
harness:
- `resolve`: each profile-detection precedence rule; `--profile` override; depth thresholds at
  boundaries (50/51, 150/151); contract-surface regex hit and miss.
- `prepass`: unresolvable path, symbol, and command each produce a `HIGH`/`prepass` finding;
  resolvable ones do not; `http` links recorded `skipped`; missing required heading reported;
  exit 1 when any check fails.
- `select-model`: author family excluded from selection; ladder walk on `--check` failure;
  `independence: "reduced"` when fallback returns to the author's family; exit 1 when no rung
  resolves. `pi-watch --check` is injected via `--check-cmd` so tests need no pi install.
- `gate`: schema rejection for each required field; the three evidence outcomes (verified /
  unverified confidence cap / falsified drop); `suppressed_count` accuracy; verdict for each of the
  four cases; exit-code mapping.
- `manifest`: assembles from the four upstream JSON files; fails cleanly on a missing input.

`tests/test_adversarial_review_skill.py` — structural, following `tests/test_skill.py`:
- `SKILL.md` frontmatter parses; `name: adversarial-review`; description ≥30 chars and contains the
  trigger phrases `adversarial`, `review`, `critique`.
- All four profiles exist and each declares an attack surface, evidence rules, and pre-pass section.
- All three stage assets exist; `refute-prompt.md` contains the kill mandate; no asset contains the
  string `only critique` (the posture logic.md replaced).
- `commands/adversarial-review.md` exists with `description:` frontmatter.
- SDD's two codex assets reference `adversarial-review` (delegation landed) and no SDD file retains
  `CODEX-DEFERRED`.

**Acceptance bar:** `python3 -m pytest -q` green from the repo root.

## Non-goals

- No `agents/` directory and no `quirk:code-reviewer` agent definition. logic.md § Deferred Ideas
  records the dangling reference; this work deliberately does not depend on or fix it.
- No cross-session finding persistence, multi-run consensus, lens panel, right-of-reply, or noise
  budget — all deferred in logic.md.
- No changes to SDD's escalation routing, merge lanes, or ledger schema.
- The script does not implement the promote/refute dispatch loop; `SKILL.md` drives it.

## Escalation — ambiguity resolved, ruling requested

logic.md contains two entries that under-specify their interaction:

- *Decisions Locked → Posture:* "Reproduction required for CRITICAL/HIGH ... or they get
  **downgraded**" — without naming which axis is downgraded.
- *Behavior & scenarios:* "A high-consequence finding cannot be proven. It survives as **CRITICAL
  severity with LOW confidence** rather than being downgraded into invisibility."

Read as a severity downgrade, the two contradict. Read as a **confidence** cap, both hold
simultaneously and the two-axis model stays coherent: severity tracks consequence, which proof
does not change; confidence tracks likelihood, which is exactly what proof establishes. This spec
implements the confidence-cap reading, and additionally distinguishes *falsified* evidence (dropped
and counted) from *merely unproven* evidence (capped).

This is an interpretation of an ambiguity, not a change to a locked decision, so it does not
require an Amendments entry. It is surfaced here because it is the single most consequential
technical call in the document. If the intended reading was a severity downgrade, say so and this
spec's evidence-gate contract changes.
