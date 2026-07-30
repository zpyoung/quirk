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

Anchors below are against `52f5865`, which rewrote SDD's control plane and deleted every file the
original migration targeted.

| Path | Line anchors | Change |
|---|---|---|
| `skills/subagent-driven-development/SKILL.md` | 230–259 (Step 8: Review) | Replace the direct `pi-watch` dispatch with a per-lens invocation of this skill; keep rounds and the checkpoint/final distinction; **adapt** the retry-then-block rule (see below) |
| `skills/subagent-driven-development/SKILL.md` | 261–277 (Step 9: Adjudicate and fix) | Consume structured `GateResult` instead of parsing reviewer text blocks; SDD keeps stable-ID assignment and dismissed carry-forward |
| `skills/subagent-driven-development/assets/reviewer-prompt.md` | whole file | Becomes the `code-diff` profile's lens definitions plus a delegation header; its severity rubric and `LOCATION`/`EVIDENCE` requirement migrate into `profiles/code-diff.md` rather than being rewritten |

**Not modified:** `assets/fixer-prompt.md` and `assets/implementer-prompt.md` are untouched — the
delegation replaces how findings are *produced*, not how they are fixed.

Back-link: logic.md § Decisions Locked → Integration, and § Status & amendments → Amendment 1.

### The crashed-vs-clean signal must be re-expressed, not preserved

`SKILL.md:253-258` currently distinguishes a reviewer that *found nothing* (emits `NO_FINDINGS`)
from one that *crashed* (produces no output), because SDD parses raw `pi-watch` stdout and silence
is otherwise ambiguous. Delegation changes the mechanism, so a verbatim copy of that paragraph
would describe a parsing problem that no longer exists.

`CONTRACT:` the equivalent signal under delegation
```
gate exit 0/1/3  + valid GateResult JSON  -> review completed; verdict is authoritative
  (PASS with zero findings IS the NO_FINDINGS case — a real, clean review)
gate exit 1/3    + contested_count > 0    -> mid-flight, not completed; the tiebreak stage
                                             never ran. Adjudicate, do not fix.
gate exit 4      + valid GateResult JSON  -> NOT_REVIEWABLE; never a pass
gate exit 2, non-JSON stdout, or no
  stdout at all                           -> the run FAILED; retry once, then walk the
                                             ladder, then block the round
```

SDD's operational rule is unchanged in substance and must survive rewording: a repeatedly-empty
reviewer is evidence the reviewer is broken, not evidence the branch is clean. What changes is
that "empty" is now a decidable condition (exit code plus JSON validity) rather than an inference
from silence. Back-link: logic.md § Composition contract.

### Delegation contract additions

Amendment 1 adds two fields the original design lacked, both required for SDD's round loop:

`SCHEMA:` added to the input contract
```
dismissed : array of {id, claim, ruling_reason}
            # findings the caller already rejected this run; the promote stage
            # must not re-report one without new evidence, and the refute stage
            # kills any that reappear without it
```

`CONTRACT:` finding-ID stability
```
caller supplies dismissed[].id  -> those IDs are reserved; a re-report reuses its
                                   original ID, never a fresh one
caller supplies no ids          -> gate assigns F1..Fn in severity order
ids are stable within a run, not across runs   # the manifest's artifact_hash
                                               # is what identifies a run
```

Back-link: logic.md § Decisions Locked → Integration.

**Depth under delegation.** The original `quick`-pass reading is moot: `52f5865` removed SDD's
per-task Codex gate and `CODEX-DEFERRED` entirely, and Amendment 1 retargets the integration at
Step 8, which is branch-level. SDD's checkpoint review is one round over a wave diff and its final
loop repeats over the run diff — both large enough that the depth table will select `standard` or
`deep` on size alone. SDD passes `--depth` explicitly rather than relying on auto-selection, so
delegation never silently downgrades a branch-level review to `quick`; `resolve`'s
`depth_suggestion` is advisory to a caller that omits it.

### Existing patterns to follow

`52f5865` deleted all four `scripts/sdd-*` and their tests, so the Python precedent this spec
originally cited is gone. The surviving in-repo models:

- `bin/artifact_append.py`, `bin/adr_create.py` — argparse structure, `print(f"...: {exc}",
  file=sys.stderr)` + non-zero return error convention, `raise SystemExit(main())`. These are the
  remaining stdlib-only script precedent.
- `tests/conftest.py:35-42` (`run_script`) — the `subprocess.run([sys.executable, ...])` harness.
  It resolves against `bin/` only, so this work adds a sibling helper for a skill-local script
  path rather than reusing it directly. **No test in the repo currently exercises a skill-local
  script** — `tests/test_sdd_{acceptance,dispatch,ledger,wave}.py` were all deleted — so this
  establishes the pattern rather than following one.
- `commands/artifacts/adr.md` — slash-command shape: frontmatter `description:`, then
  `${CLAUDE_PLUGIN_ROOT}` paths and per-exit-code handling instructions.
- `skills/pi-dev/scripts/pi-watch/` — precedent that a skill may own an executable with its own
  `package.json`; confirms `skills/<name>/scripts/` is a sanctioned location.

## Contracts & interfaces

### Script subcommands

`CONTRACT:`
```
adversarial-review resolve   --target <str> [--profile <name>] [--repo-root <path>]
                             [--diff-file <path>]
  -> stdout: ResolveResult ; exit 0 ok, 2 usage/IO error
  # --diff-file reads the diff from a file instead of invoking git. Testing seam,
  #   mirroring select-model's --check-cmd: depth thresholds and contract-surface
  #   detection are verifiable without constructing real git history.

adversarial-review prepass   --profile <name> --target <str> --resolve <path>
                             [--repo-root <path>] [--diff-file <path>]
                             [--check-cmd <cmd> ...]
  -> stdout: PrepassResult ; exit 0 all checks pass, 1 one or more failed, 2 error
  # --resolve anchors the pre-pass to the run. Both this and select-model sat outside
  #   the chain, which made them swappable for a file from an earlier run: a pre-pass
  #   captured while the suite was green turned a failing suite into PASS. The result
  #   also records observed_artifact_hash, derived independently rather than copied,
  #   so gate can reject a pre-pass that ran against different content.

adversarial-review select-model --author-family <family> --resolve <path>
                                [--model <alias>] [--check-cmd <cmd>]
  -> stdout: ModelSelection ; exit 0 resolved, 1 no rung resolved, 2 error

adversarial-review gate      --findings <path> --model <path> --prepass <path>
                             --resolve <path> [--depth <quick|standard|deep>]
                             [--repo-root <path>] [--no-verify-artifact]
  -> stdout: GateResult ; exit 0 PASS, 1 NEEDS_FIXES, 3 CRITICAL_ISSUES, 4 NOT_REVIEWABLE, 2 error
  # --resolve names the run and artifact. The chain proves the inputs agree with each
  #   other; run ids are random, so an intact bundle from an earlier round agrees with
  #   itself. gate re-hashes the target against resolve's hash to refuse that — the only
  #   check that separates this review from a replay, and the only one covering quick,
  #   where the reviewer hand-writes its report and there is no findings chain.
  # --no-verify-artifact for a target with no tree behind it. It disables that check.

adversarial-review manifest  --resolve <path> --prepass <path> --model <path> --gate <path>
                             [--lens <str>] [--no-verify-artifact]
  -> stdout: Manifest ; exit 0 ok, 2 error
  # Re-hashing is the default. It was --verify-artifact, opt-in, which meant the guard
  #   against recording a stale run was one most callers would never pass. The old flag
  #   is still accepted and ignored so documented invocations keep working.
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
             -> severity unchanged; confidence capped at "LOW" ONLY when
                severity is CRITICAL or HIGH
falsified  : evidence does NOT re-resolve (path/line absent, quote not present in
             artifact, or absence-search now returns hits)
             -> finding dropped, suppressed_count += 1
```

The confidence cap is scoped to CRITICAL/HIGH because that is exactly where logic.md § Decisions
Locked → Posture requires reproduction; below it, "reasoned argument permitted" means the
reviewer's own confidence judgment stands unmodified. Applying the cap uniformly would flatten the
confidence axis for every MEDIUM and LOW finding and silently re-impose a proof requirement the
logic spec declined to make.

Verdict is computed from surviving **severity** only, per logic.md's verdict table; confidence
never affects it.

### Stage tool grants and tie resolution

`CONTRACT:`
```
promote  : tools read,grep,find,ls,bash(read-only)   # may run its own verification commands
refute   : tools read,grep,find,ls,bash(read-only)   # same grant, fresh context
tiebreak : tools read,grep,find,ls                   # adjudicates, does not re-verify
```

Neither stage receives `edit` or `write`.

The read-only `bash` grant is a **deliberate divergence from SDD**, which as of `52f5865`
(SKILL.md:251-252) gives its reviewers `read,grep,find,ls` only and states the reason: *"`pi` has
no sandbox — a reviewer with `bash` or `write` has full filesystem access."* logic.md § Status &
amendments → Amendment 2 records the user's decision to keep `bash` on both dispatch paths, and
the risk accepted in doing so.

Implementation consequences of that ruling:
- The stage templates must state the read-only constraint explicitly, since on the `pi` path it is
  the *only* thing constraining the reviewer — prompt text, not enforcement.
- `profiles/*.md` must not declare a pre-pass command that would also be a plausible thing for a
  reviewer to re-run destructively; keep pre-pass commands and reviewer guidance in separate
  sections so the templates never read as an invitation to mutate.
- When SDD delegates Step 8, the reviewer it dispatches through this skill will hold a broader tool
  grant than the one SDD's own prompt specifies. That is intended per Amendment 2, and
  `assets/composition-contract.md` must say so plainly so it is not mistaken for a bug.

A finding is *contested* when refute rejects it and supplies a counter-argument rather than
falsifying its evidence.

`gate` reads this from each finding's `disposition` field — it has no other way to know a refuter
rejected something, and inferring it from `stage` alone is impossible because both survivors and
casualties carry `stage: "refute"`.

`CONTRACT:`
```
disposition "refuted",   any depth       -> dropped, suppressed reason "refuted"
disposition "contested", quick|standard  -> dropped, suppressed reason "refuted"
                                            (refute wins; there is no tiebreak below deep)
disposition "contested", deep            -> withheld from findings[], emitted in
                                            contested[] for the caller to route to
                                            the tiebreak stage; not counted as suppressed;
                                            escalates the verdict on presence, so a
                                            pending contest is never PASS and never
                                            exits 0 whatever its severity
disposition "standing" or absent         -> retained, subject to the evidence gate
```

Falsified evidence is never contested — it is dropped at any depth, since the drop is mechanical
rather than a judgment. Back-link: logic.md § Decisions Locked → Reviewer supply & adjudication.

### `gate` merges the pre-pass findings itself

`gate` already requires `--prepass`, so it appends `PrepassResult.findings` to the findings under
adjudication rather than requiring the caller to pre-merge them. Leaving the merge to the caller
would make forgetting it a silent loss of the only findings that are true by construction. Pre-pass
findings carry `disposition: "standing"` and bypass the reproduction requirement — a `kind:
"prepass"` evidence item already satisfies it.

### `quick` depth is one dispatch, not two

logic.md § Data flow → Depth dial defines `quick` as "single pass with self-refute in the same
dispatch." It is a distinct pipeline shape, not merely a cheaper `standard`:

| | `quick` | `standard` / `deep` |
|---|---|---|
| Dispatches | 1 | 2 (+1 at `deep`) |
| Refute context | Same context, second section of one reply | Fresh context, separate dispatch |
| Independence | Reduced — self-refutation is subject to the same self-recognition bias the two-stage protocol exists to defeat | Full |
| `Finding.stage` | `"promote"` for surviving items; self-refuted items are emitted under `suppressed` with stage `"promote"` | `"promote"` / `"refute"` as dispatched |

`assets/promote-prompt.md` carries a `quick`-mode section instructing the reviewer to produce its
candidate list, then refute its own list under the kill mandate, and emit only survivors plus a
suppressed list. There is no `refute-prompt.md` dispatch at `quick`.

Because `quick` cannot deliver structural independence, `GateResult` carries it forward: a `quick`
run sets `manifest.reviewer.independence = "reduced"` regardless of model family, so a `PASS` from
a `quick` pass is never read as equivalent to a `standard` one. Back-link: logic.md § Data flow →
Depth dial, and § Decisions Locked → Reviewer supply & adjudication.

### Unfalsifiable-claim detection

The promote stage emits a finding with `category: "unfalsifiable-claim"` when the artifact's
central claim admits no test. `gate` treats this category specially:

`CONTRACT:`
```
unfalsifiable-claim present  -> sorted first in findings[], severity as reported;
                                review proceeds and the verdict is computed normally
```

Back-link: logic.md § Decisions Locked → Evidence across artifact types.

### `NOT_REVIEWABLE` — both disjuncts

logic.md's verdict table makes `NOT_REVIEWABLE` a two-branch condition. `gate` therefore requires
`--model` and `--prepass` in addition to `--findings`; without them the ladder-exhausted branch is
unreachable and an unreviewed artifact would emit `PASS`, which logic.md § Composition contract
forbids in terms.

`CONTRACT:`
```
NOT_REVIEWABLE if:
    model.resolved == false                       # no ladder rung resolved
  OR (prepass.status == "could-not-run"
      AND any finding.category == "unfalsifiable-claim")
evaluated BEFORE severity-based verdict computation; it takes precedence over
PASS, NEEDS_FIXES, and CRITICAL_ISSUES.
```

`gate` exits 2 if `--model` or `--prepass` is absent — a missing input must fail loudly rather
than silently collapse to the severity path. Back-link: logic.md § Composition contract.

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
disposition   : "standing" | "refuted" | "contested"
                # Stamped by the stage that last judged the finding, and the only
                # way `gate` can know a refuter rejected it. Absent = "standing".
                #   standing  — no stage has rejected it
                #   refuted   — the refute stage falsified or rejected it outright
                #   contested — the refute stage disagrees on judgment, not evidence
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
target_kind      : "git-range" | "worktree" | "path"
target_ref       : str
artifact_hash    : str        # sha256 of content, or resolved git SHA
size_metric      : int        # changed lines for code, words for prose
depth_suggestion : "quick" | "standard" | "deep"
contract_surface : bool
untracked_paths  : array of str
                   # The untracked files that were part of the artifact when it was
                   #   captured; empty for path and git-range targets. Later stages scan
                   #   exactly this set rather than rescanning, because the review writes
                   #   into the tree as it runs — the pre-pass runs the repo's own test
                   #   command, and `cargo test` leaves a Cargo.lock that stock cargo
                   #   scaffolding does not gitignore. Rescanning refused honest first
                   #   reviews of ordinary projects. A file that appeared after resolve
                   #   was never reviewed, so the verdict says nothing about it.
diff_file        : str | null  # absolute path when --diff-file was used, else null
                   # Every later stage re-derives artifact_hash to prove it is judging
                   #   the artifact resolve identified. Without this record they would
                   #   re-run git for a review that never came from git, and compare the
                   #   result to a hash git never produced — refusing every honest run
                   #   of the detached-diff seam.
chain            : ChainLink   # step "resolve", predecessor null; mints the run id
```

`SCHEMA:` PrepassResult
```
status : "pass" | "fail" | "could-not-run"
         # could-not-run = no check was executable at all (no discovered command
         #   for code-diff; unreadable target for prose). Distinct from "fail",
         #   which means checks ran and something did not pass.
checks : array of {name, command, exit_code, status, output}
findings : array of Finding   # stage "prepass", severity HIGH, confidence HIGH
observed_artifact_hash : str | null
         # The hash of what the pre-pass actually read, derived the same way resolve
         #   derives its own rather than copied from the chain — copying would prove
         #   nothing. gate refuses a mismatch. Null only when status is could-not-run:
         #   an unreadable artifact cannot be hashed, and failing hard there would turn
         #   the input to NOT_REVIEWABLE into a crash.
chain  : ChainLink            # step "prepass", predecessor resolve
```

`SCHEMA:` ModelSelection
```
resolved     : bool           # false when no ladder rung resolved; drives NOT_REVIEWABLE
alias        : str | null     # null when resolved == false
family       : "anthropic" | "openai" | "google" | "other" | null
provider     : str | null
model        : str | null
thinking     : str | null
independence : "full" | "reduced"
ladder       : array of {alias, checked, resolved}
```

`SCHEMA:` GateResult
```
verdict          : "PASS" | "NEEDS_FIXES" | "CRITICAL_ISSUES" | "NOT_REVIEWABLE"
findings         : array of Finding (survivors, with confidence caps applied)
suppressed_count : int
suppressed       : array of {id, reason}
depth            : "quick" | "standard" | "deep"
                   # Echoed from --depth so `manifest` records the depth actually
                   # used, not resolve's advisory depth_suggestion. SDD overrides
                   # --depth explicitly, so deriving it from ResolveResult would
                   # silently record the wrong value.
contested        : array of Finding
                   # Non-empty only at deep depth: findings the caller must route
                   # to the tiebreak stage. Empty at quick/standard, where refute
                   # wins outright.
unreviewed_paths : array of str
                   # Untracked files present now that were absent when the artifact was
                   #   captured. They do not refuse the run — most are the review's own
                   #   check output — but a PASS that stopped short of real new work has
                   #   to say so, so they are reported and carried into the manifest.
contested_count  : int
                   # len(contested). A caller reading blocking_count alone sees a
                   # non-PASS verdict beside zero blocking findings, since a pending
                   # contest escalates from contested[] and is withheld from findings[].
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

**Where profile data lives (clarified at plan-build, 2026-07-27).** The script does **not** parse
`profiles/*.md`. The pre-pass command discovery table and the required-headings table below are
internal `CONFIG` in `scripts/adversarial-review`, keyed by profile name; `profiles/*.md` carry
only model-facing prose (attack surface, evidence rules, lens definitions) consumed by the stage
templates. This keeps the script hermetically testable with no markdown-parsing dependency, and
means a profile's prose can change without touching script behavior or its tests.

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

Every failed reference resolution becomes a `stage: "prepass"` Finding with a `kind: "prepass"`
evidence item, bypassing the promote/refute stages. Severity and confidence are **calibrated to
how decidable the failure actually is** (revised 2026-07-27 after dogfooding — see below):

`CONFIG:` prepass finding calibration
```
path/symbol unresolved, profile prose-claim   -> HIGH severity,   HIGH confidence
path/symbol unresolved, profile spec-design
                        or plan               -> MEDIUM severity, LOW confidence
command not on PATH, any profile              -> MEDIUM severity, LOW confidence
```

**Why not uniformly HIGH/HIGH.** Running this check against this repo's own `tech.md` produced 40
findings, nearly all false positives; tightening classification (document-relative resolution,
line-anchor stripping, rejecting globs/placeholders/shebangs/prose) reduced it to 20, and the
remainder proved semantic rather than mechanical. A spec-design or plan document names files that
do not exist *yet* — that is its job — and no heuristic separates "stale reference" from "planned
artifact." Asserting HIGH confidence on an undecidable question is how a check earns the 70–90%
ignore rate recorded in logic.md § Industry Insights. The claim text must state the ambiguity
rather than hide it. `prose-claim` documents describe current state, so the original calibration
holds there. Command-vs-prose is undecidable in every profile.

Back-link: logic.md § Data flow step 3, and § Decisions Locked → Output format (severity is
consequence, confidence is likelihood — this is that model doing its job).

## DO-NOT-CHANGE fences

- **`skills/subagent-driven-development/SKILL.md` Steps 1–7 (lines 77–229), Step 10 (279–297),
  and Failure routing (298–316)** — *Why fenced:* Amendment 1 delegates only the *production* of
  findings in Step 8. Preflight, decomposition, waves, dispatch, audit/commit/merge, the build/test
  gate, the five-round exit cap, and worker failure routing are orthogonal to how a review is
  performed, and this control plane is one commit old and unproven — widening the blast radius is
  how a delegation becomes a rewrite.
- **`skills/subagent-driven-development/assets/{fixer,implementer}-prompt.md`** — *Why fenced:*
  the delegation changes how findings are produced, never how they are fixed or how work is built.
- **SDD's severity rubric and `LOCATION`/`EVIDENCE` requirement** (currently
  `assets/reviewer-prompt.md`) — *Why fenced:* these are migrated verbatim into
  `profiles/code-diff.md`, not redesigned. They already match this spec's evidence gate, and
  silently re-tuning them would change SDD's exit-gate behavior, which reads those labels.
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
- Any widening of the Step 8 delegation into SDD's fenced steps (see DO-NOT-CHANGE fences).
- Whether SDD's checkpoint review should use a cheaper depth than its final loop, once real
  round-latency numbers exist.

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
exactly as declared, so a profile can name a real project build/test invocation without this spec
having to model every shell form.

**Observability.** The manifest is the audit record. `gate` reports `suppressed` with a per-finding
reason so an abnormal kill rate is diagnosable rather than merely visible.

**Rollback.** The skill is additive. The SDD migration is the only destructive change; it is a
separate task, committed separately, and revertible without touching the new skill.

## Testing strategy

`tests/test_adversarial_review.py` — script behavior. It defines its own `subprocess.run(
[sys.executable, str(SCRIPT), ...])` helper resolving `SCRIPT` to
`skills/adversarial-review/scripts/adversarial-review`, since `conftest.py`'s `run_script` is
`bin/`-only and no skill-local-script harness survives in the repo:
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
- Delegation landed: `skills/subagent-driven-development/SKILL.md` Step 8 references
  `adversarial-review`, and its inline `pi-watch --provider openai-codex` reviewer dispatch is
  gone.
- Migration fidelity: every severity tier in SDD's rubric (`CRITICAL`/`HIGH`/`MEDIUM`/`LOW`) and
  the `NO_FINDINGS` token survive in `profiles/code-diff.md`, so SDD's exit gate keeps reading the
  labels it expects.

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

- *Data flow, step 7* (logic.md:70–71): "A CRITICAL or HIGH finding lacking a reproduction is
  **downgraded**" — without naming which axis is downgraded. (The companion bullet at *Decisions
  Locked → Posture*, logic.md:154, states the reproduction requirement itself but does not use the
  word "downgraded"; the ambiguity lives in the Data flow wording.)
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
