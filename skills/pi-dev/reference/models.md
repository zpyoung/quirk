# Pi Models, Providers & Aliases

When the user says "use pi codex" or "with a pi gemini agent" they are picking a **provider + model**. This file maps natural-language references to the exact `--provider` and `--model` flag values, lists the canonical model IDs available locally, and defines short aliases so future invocations stay consistent.

**Source of truth:** `pi --list-models`. This catalog reflects the providers/models the local pi install can actually dispatch to. The pi.dev catalog also lists `openrouter`, `mistral`, `groq`, `cerebras`, `fireworks`, `huggingface`, `cloudflare-*`, `vercel-ai-gateway`, `moonshotai`, `minimax`, `deepseek`, `xai`, `amazon-bedrock`, `azure-openai-responses`, but those will only resolve here if the user has authenticated to them. Always re-run `pi --list-models` to confirm before scripting against a non-default provider.

**Substring filter:** `pi --list-models <pattern>` scopes the output to entries whose model name contains `<pattern>`. Use this instead of dumping the full table when you only need to confirm one family — e.g., `pi --list-models 5.5`, `pi --list-models opus-4-7`, `pi --list-models codex-max`. Output still goes to stderr.

## Pro-tier variants — avoid by default

Some catalog entries are "pro" / "deep-research" tiers that are **dramatically more expensive and slower** than the standard variants. Never auto-select these:

| Model | Provider | Why avoid |
|---|---|---|
| `gpt-5-pro`, `gpt-5.2-pro`, `gpt-5.4-pro`, `gpt-5.5-pro` | `openai` | ~10–30× cost vs base, multi-minute latency |
| `o1-pro`, `o3-pro` | `openai` | Pro reasoning tier — same cost/latency profile |
| `o3-deep-research`, `o4-mini-deep-research` | `openai` | Deep-research toolchains — extended duration |

The alias preference lists in this file deliberately exclude these. If a user asks for "the best", "most capable", or "highest quality" model without naming a specific pro variant, ask via `AskUserQuestion` before dispatching — do not silently spend pro-tier budget.

## Disambiguation rule

If the user's request maps to more than one plausible model and the choice affects cost or quality, stop and clarify with `AskUserQuestion` before dispatching. Mandatory cases:

1. Generic family name with multiple shipping variants ("claude", "gemini", "gpt") with no alias-table match.
2. "Most capable" / "best" / "highest quality" requests — never silently jump to a `*-pro` variant.
3. The user-specified model ID isn't found by `pi --list-models <id>` — surface that and offer closest matches.
4. The user wants to override the default but hasn't named the target.

Format: 2–4 multiple-choice options, each labeled with the resolved `provider/model:thinking` and a one-line cost/speed hint. Never guess silently when budget is at stake.

**Separator convention (CRITICAL):**
- `anthropic` IDs use **dashes**: `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5`.
- `openai`, `openai-codex`, `google`, `github-copilot` IDs use **dots**: `gpt-5.3-codex`, `gemini-3.1-pro-preview`, `claude-sonnet-4.5` (yes, dots even though the underlying model is Anthropic's, when routed via `github-copilot`).

Mixing them up will produce "model not found" errors.

## Default

If no provider/model is specified by the user, dispatch the codex alias and let it resolve through the fallback ladder. Currently lands on `openai-codex/gpt-5.3-codex` locally, but auto-upgrades to `gpt-5.5` / `gpt-5.4` when those become available in pi.

```bash
# Resolve via preference list (auto-upgrades as newer models ship):
read PI_PROVIDER PI_MODEL PI_THINKING < <(resolve_pi_model xhigh \
    openai-codex/gpt-5.5 openai/gpt-5.5 \
    openai-codex/gpt-5.4 openai/gpt-5.4 github-copilot/gpt-5.4 \
    openai-codex/gpt-5.3-codex openai/gpt-5.3-codex github-copilot/gpt-5.3-codex)
pi --provider "$PI_PROVIDER" --model "$PI_MODEL" --thinking "$PI_THINKING" "..."
```

`:xhigh` is the deepest reasoning level. Override the alias resolution only when the user explicitly names a different model.

## Newest-first principle

Generic aliases (`codex`, `sonnet`, `opus`, `haiku`, `gemini pro`) target the newest model that *might* exist on pi, then ladder down to versions that currently ship. This means each alias has speculative top entries — `gpt-5.5`, `claude-opus-4-7`, `claude-sonnet-4-7`, `gemini-3.2-pro-preview` — that are NOT yet in `pi --list-models` as of this writing. **That is intentional.** The fallback algorithm:

1. Walks the preference list top-to-bottom.
2. Skips combos missing from `pi --list-models` (silently — they're not errors).
3. Dispatches the first combo that's both authed and available.

Net effect: the moment pi ships a newer model, the alias auto-upgrades with no skill edits. When bumping the ladder for a freshly-released model, only ever *prepend* new entries — never remove old ones, since they remain valid fallbacks.

**Explicit version pins skip the ladder.** A user saying "gpt-5.4" or "claude-sonnet-4-6" wants that exact version — preference list collapses to just the providers offering that ID.

## Trigger phrase → provider preference list

When the user's request includes any of these phrases (case-insensitive), resolve to a **preference list** of `provider/model` combos. Walk it top-to-bottom and dispatch with the first one that appears in `pi --list-models` (i.e., is authed locally). The same logical model is often served by multiple providers — never lock to one. Phrases that include "pi" are explicit pi invocations; bare model names ("sonnet", "opus") in a pi-context conversation should also resolve through this table.

| User phrase | Default thinking | Preference list (first authed wins; → = fall through) |
|---|---|---|
| (no model specified), `use pi`, `pi agent`, `pi subagent`, `pi worker` | `xhigh` | `openai-codex/gpt-5.5` → `openai/gpt-5.5` → `openai-codex/gpt-5.4` → `openai/gpt-5.4` → `github-copilot/gpt-5.4` → `openai-codex/gpt-5.3-codex` → `openai/gpt-5.3-codex` → `github-copilot/gpt-5.3-codex` |
| `pi codex`, `codex`, `with codex`, `codex agent` | `xhigh` | (same as above) |
| `pi codex max`, `codex max` | `xhigh` | `openai-codex/gpt-5.5-codex-max` → `openai/gpt-5.5-codex-max` → `openai-codex/gpt-5.4-codex-max` → `openai/gpt-5.4-codex-max` → `openai-codex/gpt-5.1-codex-max` → `openai/gpt-5.1-codex-max` → `github-copilot/gpt-5.1-codex-max` |
| `pi codex mini`, `codex mini`, `pi mini` | `medium` | `openai-codex/gpt-5.4-mini` → `openai/gpt-5.4-mini` → `github-copilot/gpt-5.4-mini` → `openai-codex/gpt-5.1-codex-mini` → `openai/gpt-5.1-codex-mini` → `github-copilot/gpt-5.1-codex-mini` |
| `pi codex spark`, `codex spark` | `high` | `openai-codex/gpt-5.4-codex-spark` → `openai-codex/gpt-5.3-codex-spark` → `openai/gpt-5.3-codex-spark` |
| `pi flagship`, `pi gpt` | `xhigh` | `openai-codex/gpt-5.5` → `openai/gpt-5.5` → `openai-codex/gpt-5.4` → `openai/gpt-5.4` → `github-copilot/gpt-5.4` |
| `gpt-5.4` (explicit pin) | `xhigh` | `openai-codex/gpt-5.4` → `openai/gpt-5.4` → `github-copilot/gpt-5.4` |
| `gpt-5.1` (explicit pin) | `xhigh` | `openai-codex/gpt-5.1` → `openai/gpt-5.1` → `github-copilot/gpt-5.1` |
| `pi sonnet`, `sonnet`, `claude sonnet`, `pi claude` | `high` | `anthropic/claude-sonnet-4-7` → `github-copilot/claude-sonnet-4.7` → `anthropic/claude-sonnet-4-6` → `github-copilot/claude-sonnet-4.6` |
| `pi opus`, `opus`, `claude opus` | `high` | `anthropic/claude-opus-4-7` → `github-copilot/claude-opus-4.7` → `anthropic/claude-opus-4-6` → `github-copilot/claude-opus-4.6` |
| `pi haiku`, `haiku`, `claude haiku` | `medium` | `anthropic/claude-haiku-4-6` → `github-copilot/claude-haiku-4.6` → `anthropic/claude-haiku-4-5` → `github-copilot/claude-haiku-4.5` |
| `pi gemini`, `gemini`, `gemini pro`, `pi gemini agent` | `high` | `google/gemini-3.2-pro-preview` → `google/gemini-3.1-pro-preview` → `github-copilot/gemini-3.1-pro-preview` → `google/gemini-3-pro-preview` → `github-copilot/gemini-3-pro-preview` |
| `pi gemini flash`, `gemini flash`, `pi flash` | `medium` | `google/gemini-flash-latest` → `google/gemini-3-flash-preview` → `github-copilot/gemini-3-flash-preview` |
| `pi grok`, `grok`, `xai grok` | `medium` | `github-copilot/grok-code-fast-1` |

If the user names a model NOT in this table, run `pi --list-models <pattern>` to scope candidates, then either use the literal model ID (if exactly one match) or ask one `AskUserQuestion` multiple-choice clarification (if multiple matches or any pro-tier candidates appear). Never silently pick a `*-pro` variant. See "Disambiguation rule" above.

## Cross-provider availability matrix

Models exposed by more than one provider on this install. Use this when constructing custom preference lists for a model not in the alias table above.

| Logical model | Providers (in fallback order) |
|---|---|
| Codex flagship (`gpt-5.3-codex`) | `openai-codex` → `openai` → `github-copilot` |
| Codex max (`gpt-5.1-codex-max`) | `openai-codex` → `openai` → `github-copilot` |
| Codex mini (`gpt-5.1-codex-mini`) | `openai-codex` → `openai` → `github-copilot` |
| Codex spark (`gpt-5.3-codex-spark`) | `openai-codex` → `openai` |
| GPT-5.4 | `openai-codex` → `openai` → `github-copilot` |
| GPT-5.1 / GPT-5.2 | `openai-codex` → `openai` → `github-copilot` |
| GPT-5 / GPT-5-mini | `openai` → `github-copilot` (not in `openai-codex`) |
| Claude sonnet 4.6 | `anthropic` (`-4-6`) → `github-copilot` (`-4.6`) |
| Claude opus 4.6 | `anthropic` (`-4-6`) → `github-copilot` (`-4.6`) |
| Claude haiku 4.5 | `anthropic` (`-4-5`) → `github-copilot` (`-4.5`) |
| Gemini 3.1 Pro | `google` → `github-copilot` |
| Gemini 3 Pro preview | `google` → `github-copilot` |
| Gemini 3 Flash preview | `google` → `github-copilot` |
| Grok-code-fast-1 | `github-copilot` only (locally) |

Order rationale: direct API providers come first (lowest latency, highest rate limits, billed via their own credit), then `github-copilot` as a subscription fallback. Override the order if the user prefers Copilot for cost reasons.

## Fallback resolution algorithm

Steps:

```
1. User says "use pi <alias>" → look up the alias's preference list above.
2. Run `pi --list-models 2>&1 >/dev/null` once per session (table is on STDERR);
   parse with `awk 'NR>1 && NF>=2 {print $1"/"$2}'`; cache as PI_AVAILABLE.
3. Walk preference list; first combo present in PI_AVAILABLE wins.
4. Dispatch with that (provider, model, default-thinking-level).
5. Log the resolved triple ("codex routed via github-copilot/gpt-5.3-codex —
   direct OpenAI key not set"). Silent fallback hides bugs.
6. On runtime auth/billing failure: retry once with the next entry in the list
   (excluding the failed one). If that also fails or no fallback remains, ABORT.
7. If no entry is present in PI_AVAILABLE at all, surface that to the user with
   the missing env vars / OAuth steps and ask whether to pick a different alias.
```

Bash implementation:

```bash
PI_AVAILABLE="$(pi --list-models 2>&1 >/dev/null | awk 'NR>1 && NF>=2 {print $1"/"$2}')"

resolve_pi_model() {
    local thinking="$1"; shift
    for combo in "$@"; do
        if grep -Fxq "$combo" <<< "$PI_AVAILABLE"; then
            echo "${combo%%/*} ${combo#*/} $thinking"
            return 0
        fi
    done
    return 1
}

# Usage — codex alias:
read PI_PROVIDER PI_MODEL PI_THINKING < <(resolve_pi_model xhigh \
    openai-codex/gpt-5.5 openai/gpt-5.5 \
    openai-codex/gpt-5.4 openai/gpt-5.4 github-copilot/gpt-5.4 \
    openai-codex/gpt-5.3-codex openai/gpt-5.3-codex github-copilot/gpt-5.3-codex \
) || { echo "no codex provider authed"; exit 1; }
```

`pi --list-models` is the single source of truth for "is this combo dispatchable right now" — it already does the full credential resolution (env vars, `auth.json`, OAuth tokens). Don't duplicate that logic.

## Canonical shorthand syntax

Pi accepts a single `provider/model:thinking` shorthand string with `--model` (the provider and thinking level are parsed out). Both forms below are equivalent:

```bash
pi --provider openai-codex --model gpt-5.3-codex --thinking xhigh "..."
pi --model openai-codex/gpt-5.3-codex:xhigh "..."
```

Use whichever is clearer in context. The split form is slightly more robust in shell scripts (no quoting traps with `:`).

## Thinking levels

Flag is `--thinking <level>` (NOT `--thinking-level`). Recognized values: `off`, `minimal`, `low`, `medium`, `high`, `xhigh`.

- **`off`** — disable extended reasoning entirely (cheapest, fastest).
- **`minimal`** — smallest non-zero reasoning budget. Useful when a model requires *some* thinking to function but you want the cheapest tier.
- **`low`** / **`medium`** — incremental reasoning budget. Default for fast models (Haiku, Flash, Codex Mini).
- **`high`** — strong reasoning. Default for balanced/strong models (Sonnet, Gemini Pro).
- **`xhigh`** — maximum reasoning. Default for the codex alias and any review pass.

Not all models accept all levels — providers that don't support a given level silently clamp. The `thinking` column in `pi --list-models` indicates support. Surface the resolved level in dispatch logs.

## Full catalog (from `pi --list-models`)

These are the literal model IDs accepted by `--model` for each provider. List captured 2026-05-06 from `pi --list-models`. Re-run that command to refresh.

### `--provider openai-codex`

```
gpt-5.1
gpt-5.1-codex-max
gpt-5.1-codex-mini
gpt-5.2
gpt-5.2-codex
gpt-5.3-codex            ← project default
gpt-5.3-codex-spark
gpt-5.4
gpt-5.4-mini
```

### `--provider openai`

```
codex-mini-latest
gpt-4
gpt-4-turbo
gpt-4.1
gpt-4.1-mini
gpt-4.1-nano
gpt-4o
gpt-4o-2024-05-13
gpt-4o-2024-08-06
gpt-4o-2024-11-20
gpt-4o-mini
gpt-5
gpt-5-chat-latest
gpt-5-codex
gpt-5-mini
gpt-5-nano
gpt-5-pro
gpt-5.1
gpt-5.1-chat-latest
gpt-5.1-codex
gpt-5.1-codex-max
gpt-5.1-codex-mini
gpt-5.2
gpt-5.2-chat-latest
gpt-5.2-codex
gpt-5.2-pro
gpt-5.3-chat-latest
gpt-5.3-codex
gpt-5.3-codex-spark
gpt-5.4
gpt-5.4-mini
gpt-5.4-nano
gpt-5.4-pro
o1
o1-pro
o3
o3-deep-research
o3-mini
o3-pro
o4-mini
o4-mini-deep-research
```

### `--provider anthropic` (dash separators)

```
claude-3-haiku-20240307
claude-3-5-haiku-20241022
claude-3-5-haiku-latest
claude-haiku-4-5
claude-haiku-4-5-20251001
claude-3-opus-20240229
claude-opus-4-0
claude-opus-4-1
claude-opus-4-1-20250805
claude-opus-4-20250514
claude-opus-4-5
claude-opus-4-5-20251101
claude-opus-4-6
claude-3-sonnet-20240229
claude-3-5-sonnet-20240620
claude-3-5-sonnet-20241022
claude-3-7-sonnet-20250219
claude-sonnet-4-0
claude-sonnet-4-20250514
claude-sonnet-4-5
claude-sonnet-4-5-20250929
claude-sonnet-4-6
```

Note: `claude-opus-4-7` does NOT exist on this install. Latest opus is `claude-opus-4-6`.

### `--provider google` (dot separators)

```
gemini-1.5-flash
gemini-1.5-flash-8b
gemini-1.5-pro
gemini-2.0-flash
gemini-2.0-flash-lite
gemini-2.5-flash
gemini-2.5-flash-lite
gemini-2.5-flash-lite-preview-06-17
gemini-2.5-flash-lite-preview-09-2025
gemini-2.5-flash-preview-04-17
gemini-2.5-flash-preview-05-20
gemini-2.5-flash-preview-09-2025
gemini-2.5-pro
gemini-2.5-pro-preview-05-06
gemini-2.5-pro-preview-06-05
gemini-3-flash-preview
gemini-3-pro-preview
gemini-3.1-flash-lite-preview
gemini-3.1-pro-preview
gemini-3.1-pro-preview-customtools
gemini-flash-latest
gemini-flash-lite-latest
gemini-live-2.5-flash
gemini-live-2.5-flash-preview-native-audio
gemma-3-27b-it
gemma-4-26b-it
gemma-4-31b-it
```

### `--provider github-copilot` (dot separators; subscription auth via `pi /login`)

```
claude-haiku-4.5
claude-opus-4.5
claude-opus-4.6
claude-sonnet-4
claude-sonnet-4.5
claude-sonnet-4.6
gemini-2.5-pro
gemini-3-flash-preview
gemini-3-pro-preview
gemini-3.1-pro-preview
gpt-4.1
gpt-4o
gpt-5
gpt-5-mini
gpt-5.1
gpt-5.1-codex
gpt-5.1-codex-max
gpt-5.1-codex-mini
gpt-5.2
gpt-5.2-codex
gpt-5.3-codex
gpt-5.4
gpt-5.4-mini
grok-code-fast-1
```

### Other providers

The pi.dev catalog also exposes: `openrouter` (273+ models, multi-provider routing including Grok variants and DeepSeek), `amazon-bedrock`, `azure-openai-responses`, `mistral`, `groq`, `cerebras`, `fireworks`, `huggingface`, `cloudflare-workers-ai`, `cloudflare-ai-gateway`, `vercel-ai-gateway`, `moonshotai` / `moonshotai-cn` (Kimi), `minimax` / `minimax-cn`, `deepseek`, `xai`. None of these are in `pi --list-models` on this install — they require additional auth before they will resolve. To use one, have the user authenticate (e.g., `OPENROUTER_API_KEY`, `pi /login` for OAuth providers), then re-run `pi --list-models` to confirm.

## Auth requirements per provider

Each provider has its own credential. Pi resolves auth in order: `--api-key` flag → `~/.pi/agent/auth.json` → provider env var → `models.json`.

| Provider | Env var | Notes |
|---|---|---|
| `openai`, `openai-codex` | `OPENAI_API_KEY` | OpenAI direct |
| `anthropic` | `ANTHROPIC_API_KEY` | Anthropic direct |
| `google` (Gemini) | `GEMINI_API_KEY` | |
| `github-copilot` | (none — OAuth) | One-time `pi /login` |
| `openrouter` | `OPENROUTER_API_KEY` | Not configured by default |
| `groq` | `GROQ_API_KEY` | Not configured by default |
| `mistral` | `MISTRAL_API_KEY` | Not configured by default |
| `deepseek` | `DEEPSEEK_API_KEY` | Not configured by default |
| `xai` | `XAI_API_KEY` | Not configured by default |

Subscription providers — `github-copilot`, plus Claude Pro/Max OAuth and ChatGPT Plus when used through pi — require a one-time interactive `pi /login` before headless use. They will not work in fresh `--no-session` invocations until the user has logged in once.

Don't pre-validate env vars manually before dispatch — `pi --list-models` already does that resolution end-to-end (env vars, `auth.json`, OAuth tokens) and only enumerates combos that will actually work. Use it as the single auth-status oracle. Never modify `~/.pi/agent/auth.json`.

(For the dispatch resolution algorithm see "Fallback resolution algorithm" above.)

## When to override the default

The `openai-codex/gpt-5.3-codex:xhigh` default optimizes for code-quality on edits. Override when:

- **Cost-sensitive bulk work** (test generation, docs scaffolding) → `claude-haiku-4-5` or `gpt-5.1-codex-mini`.
- **Adversarial review pass** → use a *different provider* than the worker. If worker is `openai-codex`, reviewer should be `anthropic` (`claude-sonnet-4-6`) or `google` (`gemini-3.1-pro-preview`). Cross-provider review surfaces issues that same-provider review tends to miss.
- **Long-context refactors** → `gemini-3.1-pro-preview` (1M context) or `claude-opus-4-6` (1M context via `anthropic`) or `gpt-5.4-pro` (1.1M context via `openai`).
- **Speed over depth** → `gemini-flash-latest`, `gpt-5.1-codex-mini`, or `claude-haiku-4-5` with `:medium`.
