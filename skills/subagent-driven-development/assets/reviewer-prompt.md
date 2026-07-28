# Adversarial Reviewer Prompt — delegated

This file no longer stages a reviewer. Step 8 delegates the review to **quirk:adversarial-review**,
one invocation per lens. Nothing here is substituted into a prompt.

Everything this file used to carry is still in force — it moved rather than changed:

| Was here | Now lives in |
| --- | --- |
| The severity rubric (`CRITICAL` / `HIGH` / `MEDIUM` / `LOW`) | `skills/adversarial-review/profiles/code-diff.md` — migrated verbatim, because Step 10's exit gate reads these labels and re-tuning them would move when the loop terminates |
| The `LOCATION` and `EVIDENCE` requirement | same file, expressed as the `evidence[].ref` and `evidence[].quote` fields the gate re-resolves against the tree |
| The three lens definitions | same file |
| The `NO_FINDINGS` token, and that silence is not the same signal | same file, plus the exit-code table in Step 8 |
| The dispatch invocation and the review protocol | `skills/adversarial-review/SKILL.md` |

**The interface is `skills/adversarial-review/assets/composition-contract.md`** — what Step 8 passes
in, what Step 9 gets back, and how to read a verdict. Read that, not this.

Two things changed in substance rather than location. Step 8 states both:

- **The reviewer holds read-only `bash`** in addition to `read,grep,find,ls`. The skill requires a
  reproduction for every `CRITICAL` and `HIGH` finding, and that standard is unmeetable without a
  shell. `pi` still has no sandbox, so on that path the constraint is prompt-level only; the trade
  is recorded in the composition contract.
- **Reviewer output is structured `GateResult` JSON with an exit code.** A crashed reviewer is now
  distinguishable from a clean one mechanically, instead of being inferred from silence. The
  operational rule is unchanged: a reviewer that keeps coming back empty is broken, not proof that
  the branch is clean.
