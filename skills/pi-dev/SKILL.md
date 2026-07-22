---
name: pi-dev
description: Use when dispatching the pi coding agent for a sub-task — code review, analysis, edits, or multi-agent orchestration. Triggers on "use pi", "run pi", or "pi <model>" (codex, terra, opus, sonnet, gemini, haiku, grok).
---

# pi-dev

## TL;DR — call `pi-watch` with an alias

```bash
pi-watch --alias codex "Explain the auth flow in src/auth.ts"
```

`pi-watch` is the shipped wrapper at `scripts/pi-watch/`. It picks the first authed model from the alias's preference ladder, runs pi in-process via the SDK (no DefaultResourceLoader cwd scan), and splits the stream:

- **stdout** = assistant text only — capturable via `result="$(pi-watch ...)"`
- **stderr** = `▶ resolved <provider>/<model>:<thinking>` header, `⚙ tool args` progress, `✔ done`

That's the whole interface. Don't construct `--provider`/`--model`/`--thinking` triples by hand or invoke the `pi` binary directly unless one of the [escape hatches](#escape-hatches) below applies.

## Validate before dispatching

An alias only works if a model in its ladder is authed on *this* machine. Don't assume — preflight with `--check`, which resolves the alias against `pi --list-models` **without** running a prompt (or spending tokens):

```bash
pi-watch --check codex && pi-watch --alias codex "<prompt>"   # dispatch only if codex resolves
pi-watch --check                                              # ✓/✗ report for every alias
```

`pi-watch --check <alias>` exits **0** when the alias resolves to an authed/shipping model and **non-zero** otherwise — so gate real dispatches on it (`--check … && pi-watch …`) to never fire a doomed run. With no alias it checks all of them and prints which are ready. `--list-aliases` shows the *static* ladders; `--check` tells you which actually work right now.

The ✓/✗ report prints to **stderr** (like pi-watch's other progress output) and the gate keys off the **exit code** — so wrapping the whole gate in a capture (`result="$(pi-watch --check codex && pi-watch --alias codex '…')"`) keeps `result` to the assistant text only.

| Exit | Meaning |
|---|---|
| 0 | Every checked alias resolves to an authed model |
| 2 | Named alias is unknown |
| 4 | Can't query `pi` (binary missing — see [Setup](#setup-one-time-per-workstation)) |
| 5 | At least one checked alias won't run — no authed/shipping model (run `pi /login`), or SDK skew: pi lists the model but the bundled pi-ai catalog lacks it (run `pnpm update` in the pi-watch dir) |

## Aliases

| Alias | Default thinking | Routes to |
|---|---|---|
| `codex` (default coding) | `medium` | gpt-5.6-sol → 5.5 → 5.4 → 5.3-codex (across `openai-codex`/`openai`/`github-copilot`) |
| `codex-max` | `max` | gpt-5.6-sol → 5.5-codex-max → 5.4-codex-max → 5.1-codex-max |
| `codex-mini` | `medium` | gpt-5.6-luna → 5.4-mini → 5.1-codex-mini |
| `codex-spark` | `high` | gpt-5.4-codex-spark → 5.3-codex-spark |
| `terra` (balanced) | `high` | gpt-5.6-terra → 5.4 |
| `sonnet` | `high` | claude-sonnet-4-7 → 4-6 (anthropic + copilot) |
| `opus` | `high` | claude-opus-4-7 → 4-6 |
| `haiku` | `medium` | claude-haiku-4-6 → 4-5 |
| `gemini` | `high` | gemini-3.2-pro-preview → 3.1 → 3 |
| `flash` | `medium` | gemini-flash-latest → 3-flash-preview |
| `grok` | `medium` | github-copilot/grok-code-fast-1 |

GPT-5.6 replaced the suffix ladder with three capability tiers: **Sol** (flagship, $5/$30, the only tier that unlocks `max` reasoning effort), **Terra** (balanced, $2.50/$15), **Luna** (fast/cheapest, $1/$6). Sol takes over `codex`/`codex-max`, Luna takes over `codex-mini`, and Terra gets its own `terra` alias.

Aliases auto-upgrade as new models ship — newest entries at the top of each ladder are speculative and skipped if not yet in `pi --list-models`. **OpenAI pro / deep-research tiers are deliberately excluded** from alias ladders: `gpt-5-pro`, `gpt-5.x-pro`, `o1-pro`, `o3-pro`, `o3-deep-research`, `o4-mini-deep-research` (~10–30× cost, multi-minute latency). GPT-5.6's **Sol Pro** and **Ultra mode** are the same lever — they're request-time params (`reasoning.mode`), not separate model IDs, so there's no alias for them. Dispatch pro-tier only on explicit user request via `--provider`/`--model`. *(Note: `gemini-*-pro-preview` is Google's standard tier, not a pro tier — it routes via the `gemini` alias.)*

To see the full ladders: `pi-watch --list-aliases`.

## Common flags

```bash
pi-watch --alias <alias> "<prompt>"                          # default tools: read,bash
pi-watch --alias <alias> --tools read "<prompt>"             # restrict tools
pi-watch --alias <alias> --no-tools "<prompt>"               # LLM only — review/analysis
pi-watch --alias <alias> --thinking medium "<prompt>"        # override default thinking
pi-watch --check <alias>                                     # preflight one alias (exit 0 = authed model resolves)
pi-watch --check                                             # preflight all aliases — ✓/✗ report
```

Thinking levels: `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. `max` is the opt-in ceiling above `xhigh`, native on GPT-5.6 Sol and adaptive Claude models (it's the `codex-max` default); other models silently clamp it — and any unsupported level — down.

### Tools

Pi's built-in tool names (pass to `--tools`, comma-separated):

| Tool | Capability | Off by default? |
|---|---|---|
| `read` | Read file contents | no — pi-watch enables |
| `bash` | Execute bash commands | no — pi-watch enables |
| `edit` | Edit files with find/replace | yes |
| `write` | Write files (create/overwrite) | yes |
| `grep` | Search file contents (read-only) | yes |
| `find` | Find files by glob pattern (read-only) | yes |
| `ls` | List directory contents (read-only) | yes |

Pick by what the worker needs to *do*, not what would be "complete":

- **Read-only review / analysis / summarization** → `--tools read,grep,find,ls` (no shell, no writes).
- **Pure LLM judgment, no filesystem** → `--no-tools` (e.g., reviewer worker scoring a diff that's already in the prompt).
- **Code edits** → `--tools read,grep,find,edit,write` (omit `bash` if you don't want shell execution; add it back when running tests is part of the worker's job).
- **Default coding worker** (build, test, edit, commit) → omit `--tools` (uses `read,bash`) and add `edit,write` if it needs to mutate files: `--tools read,bash,edit,write`.

Tool grants are an allowlist; whatever you don't list is unavailable to the model. Pi has **no built-in sandbox** — `bash`, `edit`, and `write` give the worker full user-level filesystem access. Run mutating workers in a worktree or container if isolation matters.

## Disambiguate before dispatching

Stop and ask the user (multiple-choice via AskUserQuestion) when:

- They say "best" / "most capable" — never silently jump to a `*-pro` model.
- They name a generic family with no alias-table match.
- They request a model that isn't in `pi --list-models <id>` output.
- The choice is between an alias and an explicit pin.

## Setup (one-time per workstation)

Install the launcher **as a copy** on your PATH. The launcher resolves the
*currently installed* quirk version on every run (from `installed_plugins.json`),
so it keeps tracking `claude plugin update` — unlike a symlink into a versioned
cache dir, which freezes at install-time and dangles when that version is pruned.

```bash
# Resolve the install dir directly — there is no `claude plugin path` command.
QUIRK="$(node -e 'const fs=require("fs"),os=require("os"),p=require("path");const P=JSON.parse(fs.readFileSync(p.join(os.homedir(),".claude/plugins/installed_plugins.json"),"utf8")).plugins;const k=P["quirk@quirk-dev"]?"quirk@quirk-dev":Object.keys(P).find(x=>x.startsWith("quirk@"));process.stdout.write(k?P[k][0].installPath:"")')"
install -m755 "$QUIRK/skills/pi-dev/scripts/pi-watch/pi-watch" ~/.local/bin/pi-watch  # or any PATH dir
```

Verify: `pi --version` → expect ≥ 0.65.1. `pi /login` for any subscription provider you want (Claude, ChatGPT, Copilot). Then `pi-watch --check` to confirm which aliases resolve to an authed model — the first run also auto-installs the current version's Node deps if they're missing.

**Updating:** `claude plugin update quirk` is enough — `pi-watch` auto-follows. Run `pi-watch --where` to see which version/dir it resolves to (and whether that copy has the current alias ladder). Re-run the `install` line above only if the launcher script itself changes (rare); mjs/alias updates are picked up automatically.

*(Dev checkout: point the launcher at a working tree instead — `ln -sf "$(pwd)/pi-watch" ~/.local/bin/pi-watch` from `skills/pi-dev/scripts/pi-watch`, or set `PI_WATCH_DIR`. A launcher whose own dir holds the code and sits outside the plugin cache runs that tree, so local edits are live.)*

## Escape hatches

Use the raw `pi` binary or the SDK directly only for these cases:

| Need | Use | Reference |
|---|---|---|
| One-off script, just want final text, no streaming | `pi -p "..."` | `reference/print-mode.md` |
| Tooling that consumes JSONL events | `pi --mode json` | `reference/json-mode.md` |
| Non-Node host (Python/Go/Rust) needing bidirectional control | `pi --mode rpc --no-session` | `reference/rpc-mode.md` |
| Embedding pi in a Node.js app with type safety | `@earendil-works/pi-coding-agent` SDK | `reference/sdk-mode.md` |
| Multi-agent orchestrator (decompose → dispatch → review → integrate) | RPC subprocess workers + SDK orchestrator | `reference/orchestration.md` |
| Need a model not covered by an alias, or pinning an exact version | `pi-watch --provider <p> --model <m> [--thinking <l>]` | `reference/models.md` (full catalog, separator quirks, fallback algorithm) |

When invoking the raw `pi` binary in scripts always pass `--no-session --offline` and wrap with `gtimeout` (macOS) / `timeout` (Linux). Pi has no `--cd` flag (caller must `cd` first), no built-in sandbox, no built-in timeout. Full headless dispatch recipe: `reference/print-mode.md#canonical-headless-recipe`.

## Don't

- **Don't** construct `--provider`/`--model`/`--thinking` triples manually when an alias would work — you'll miss fallback and lose auto-upgrade.
- **Don't** modify `~/.pi/agent/auth.json` or `~/.pi/agent/AGENTS.md`.
- **Don't** dispatch parallel `git worktree add` calls when running pi workers — they race on `.git/config.lock`. Serialize creation; only the workers run parallel.
- **Don't** run multiple workers in the same working directory — pi has no sandbox; they will overwrite each other.
- **Don't** silently fall back across providers when running raw `pi`. Always log the resolved triple (`pi-watch` does this automatically via the `▶ resolved` line).
- **Don't** use Node's `readline` to parse RPC stdout — see `reference/rpc-mode.md` for the U+2028/U+2029 framing trap.
