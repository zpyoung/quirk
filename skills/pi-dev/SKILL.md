---
name: pi-dev
description: Use when invoking the pi coding agent (binary `pi`, package `@mariozechner/pi-coding-agent`) in headless mode — print, JSON-stream, RPC subprocess, or in-process SDK. Triggers on "use pi", "use pi dev", "pi agent", "pi subagent", "run pi", "pi headless", "pi codex", "pi gemini", "pi sonnet", "pi opus", "pi haiku", "pi grok", "pi deepseek", "pi --print", "pi --mode json", "pi --mode rpc", or any request to dispatch / embed / script the pi coding agent. Picks the right mode, resolves provider/model aliases, and supplies a working invocation recipe.
---

# pi-dev

## Overview

Pi has four run modes. One is interactive; the other three are headless and used for scripts, CI, embedded agents, and multi-agent orchestration. There is also a TypeScript SDK that runs Pi in-process.

Use this skill when the user asks you to run `pi` non-interactively, embed pi in a script or app, or build orchestration on top of pi.

## Mode selection

Pick a mode by asking: *what is calling pi, and what does it need from the response?*

| Caller | Needs | Mode |
|---|---|---|
| Bash script, CI step, one-off task | Final answer text only | **Print** (`pi -p`) |
| Tooling that watches tool calls / streaming deltas | Events as JSONL | **JSON stream** (`pi --mode json`) |
| Non-Node host (Python, Go, Rust) needing multi-turn control | Bidirectional command/event protocol | **RPC** (`pi --mode rpc`) |
| Node.js app with type safety, same-process | TS API, no subprocess | **SDK** (`@mariozechner/pi-coding-agent`) |

If the user is building a multi-agent system: orchestrator runs as SDK or interactive session; workers run as `pi --mode rpc --no-session` subprocesses, coordinated via JSONL.

## Provider & model selection

Pass either split flags or shorthand:

```bash
pi --provider openai-codex --model gpt-5.5 --thinking-level xhigh "..."
pi --model openai-codex/gpt-5.5:xhigh "..."   # shorthand form
```

**Separator rule:** `anthropic` IDs use **dashes** (`claude-sonnet-4-6`). All other providers — `openai`, `openai-codex`, `google`, `github-copilot` — use **dots** (`gpt-5.5`, `gemini-3.1-pro-preview`, `claude-sonnet-4.6` when routed via copilot). The preference lists below already encode the right form per provider — copy verbatim.

**Aliases resolve to a preference list, not a single combo.** Walk top-to-bottom; dispatch the first combo present in `pi --list-models` (i.e., authed locally and shipping in this pi version). Generic aliases lead with newest-first speculative entries (`gpt-5.5`, `claude-opus-4-7`, etc.) — the fallback algorithm skips combos that don't exist yet, so aliases auto-upgrade as pi ships newer models.

| User says | Default thinking | Preference list (first authed wins; → = fall through) |
|---|---|---|
| (no model) / "use pi" / "pi codex" / "codex" | `xhigh` | `openai-codex/gpt-5.5` → `openai/gpt-5.5` → `openai-codex/gpt-5.4` → `openai/gpt-5.4` → `github-copilot/gpt-5.4` → `openai-codex/gpt-5.3-codex` → `openai/gpt-5.3-codex` → `github-copilot/gpt-5.3-codex` |
| "codex max" | `xhigh` | `openai-codex/gpt-5.5-codex-max` → `openai/gpt-5.5-codex-max` → `openai-codex/gpt-5.4-codex-max` → `openai/gpt-5.4-codex-max` → `openai-codex/gpt-5.1-codex-max` → `openai/gpt-5.1-codex-max` → `github-copilot/gpt-5.1-codex-max` |
| "codex mini" / "pi mini" | `medium` | `openai-codex/gpt-5.4-mini` → `openai/gpt-5.4-mini` → `github-copilot/gpt-5.4-mini` → `openai-codex/gpt-5.1-codex-mini` → `openai/gpt-5.1-codex-mini` → `github-copilot/gpt-5.1-codex-mini` |
| "codex spark" | `high` | `openai-codex/gpt-5.4-codex-spark` → `openai-codex/gpt-5.3-codex-spark` → `openai/gpt-5.3-codex-spark` |
| "pi flagship" / "pi gpt" | `xhigh` | `openai-codex/gpt-5.5` → `openai/gpt-5.5` → `openai-codex/gpt-5.4` → `openai/gpt-5.4` → `github-copilot/gpt-5.4` |
| "gpt-5.4" (explicit version pin) | `xhigh` | `openai-codex/gpt-5.4` → `openai/gpt-5.4` → `github-copilot/gpt-5.4` |
| "pi sonnet" / "sonnet" / "claude sonnet" | `high` | `anthropic/claude-sonnet-4-7` → `github-copilot/claude-sonnet-4.7` → `anthropic/claude-sonnet-4-6` → `github-copilot/claude-sonnet-4.6` |
| "pi opus" / "opus" | `high` | `anthropic/claude-opus-4-7` → `github-copilot/claude-opus-4.7` → `anthropic/claude-opus-4-6` → `github-copilot/claude-opus-4.6` |
| "pi haiku" / "haiku" | `medium` | `anthropic/claude-haiku-4-6` → `github-copilot/claude-haiku-4.6` → `anthropic/claude-haiku-4-5` → `github-copilot/claude-haiku-4.5` |
| "pi gemini" / "gemini" / "gemini pro" | `high` | `google/gemini-3.2-pro-preview` → `google/gemini-3.1-pro-preview` → `github-copilot/gemini-3.1-pro-preview` → `google/gemini-3-pro-preview` → `github-copilot/gemini-3-pro-preview` |
| "pi flash" / "gemini flash" | `medium` | `google/gemini-flash-latest` → `google/gemini-3-flash-preview` → `github-copilot/gemini-3-flash-preview` |
| "pi grok" / "grok" | `medium` | `github-copilot/grok-code-fast-1` |

**Explicit version pins skip the ladder** — "gpt-5.4" or "claude-sonnet-4-6" means that exact version, no upgrade ladder. **Pro-tier variants** (`gpt-5-pro`, `gpt-5.2-pro`, `gpt-5.4-pro`, `gpt-5.5-pro`, `o1-pro`, `o3-pro`, `o3-deep-research`, `o4-mini-deep-research`) are excluded from all alias ladders — ~10–30× cost and multi-minute latency. Only dispatch them on explicit user request.

Thinking levels: `off`, `low`, `medium`, `high`, `xhigh`. Providers that don't support a level silently clamp.

Full catalog, cross-provider matrix, and dispatch resolution algorithm: `reference/models.md`.

## Resolution + fallback (in 4 steps)

```bash
# 1. Cache available combos. Note: pi writes the table to STDERR.
PI_AVAILABLE="$(pi --list-models 2>&1 >/dev/null | awk 'NR>1 && NF>=2 {print $1"/"$2}')"

# 2. resolve_pi_model walks a preference list against PI_AVAILABLE.
#    Full implementation: reference/models.md ("Fallback resolution algorithm").
read PI_PROVIDER PI_MODEL PI_THINKING < <(resolve_pi_model xhigh \
    openai-codex/gpt-5.5 openai/gpt-5.5 \
    openai-codex/gpt-5.4 openai/gpt-5.4 github-copilot/gpt-5.4 \
    openai-codex/gpt-5.3-codex) || { echo "no codex provider authed"; exit 1; }

# 3. Dispatch; log the resolved triple so the user sees which fallback fired.
echo "codex routed via $PI_PROVIDER/$PI_MODEL:$PI_THINKING"
pi --provider "$PI_PROVIDER" --model "$PI_MODEL" --thinking-level "$PI_THINKING" "..."

# 4. On runtime auth/billing failure, retry ONCE with the next preference entry.
#    No infinite loop — cap at one cross-provider retry per worker.
```

Substring filter: `pi --list-models 5.5 2>&1 >/dev/null` scopes the table to a single family — use this when confirming whether a specific variant is shipping.

`pi --list-models` is the single source of truth for "is this combo dispatchable now" — it already resolves env vars / `auth.json` / OAuth tokens. Don't duplicate that check manually. Never silently pick a fallback; always log the resolved triple.

## Disambiguate via AskUserQuestion when ambiguous

Stop and ask before dispatching when:
- Generic family name with multiple shipping variants and no alias-table match.
- "Best" / "most capable" / "highest quality" — never silently jump to `*-pro`.
- Specified ID isn't in `pi --list-models <id>`.
- User wants override but didn't name the target.

Format: 2–4 multiple-choice options, each labeled `provider/model:thinking` + cost/speed hint.

## Critical preflight (before any mode)

1. **`pi --version` ≥ 0.65.1.** Older versions have a JSON+piped-stdin regression where `--mode json` falls back to plain text when stdin is piped. Upgrade with `pnpm add -g @mariozechner/pi-coding-agent`.
2. **Auth.** Resolution order: `--api-key` flag → `~/.pi/agent/auth.json` → provider env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`) → `models.json`. Never modify `auth.json`. Subscription providers (Claude OAuth, ChatGPT Plus, GitHub Copilot) need a one-time interactive `pi /login`.
3. **No `--cd` flag.** Pi has no working-directory flag — the caller MUST `cd` before invoking pi.
4. **No built-in sandbox.** Workers can write anywhere under user permissions. Filesystem isolation is the caller's responsibility (worktrees, containers).
5. **No built-in timeout.** Wrap with `gtimeout` (macOS) / `timeout` (Linux).
6. **Exit codes are undocumented.** Don't trust `$?` alone — also inspect stderr and JSONL stream.

## Print mode — the one-liner

Fastest path to headless. Prints final assistant text and exits.

```bash
pi -p "Summarize this codebase"
cat README.md | pi -p "Summarize this text"
git diff HEAD~1 | pi -p "Write a conventional commit message for this diff"
pi -p @prompt.md @screenshot.png "Answer this"
```

**Critical flags for automation:**
- `--no-session` — ephemeral, nothing persisted to `~/.pi/agent/sessions/`
- `--offline` — suppress startup network/update check
- `--tools read,bash,edit,write` — allowlist built-in tools
- `--no-tools` — LLM only, no tool execution (good for analysis/review)
- `--model sonnet:high` — provider/model/thinking shorthand
- `--system-prompt "..."` / `--append-system-prompt "..."` — replace or append the system prompt
- `--no-context-files` — skip `AGENTS.md` / `CLAUDE.md` discovery (use only when conventions conflict)

**Piped stdin caveat (pre-0.65.1):** if `--mode json` + piped stdin misbehaves, use `@file` arguments instead.

Full deep-dive: `reference/print-mode.md`.

## JSON event stream — observable one-shots

Like print mode, but streams JSONL events on stdout (final text, tool calls, thinking deltas). Plain text goes to stderr.

```bash
pi --mode json "List files" 2>/dev/null | jq -c 'select(.type == "message_end")'

# Extract just the final assistant text:
pi --mode json "Explain the auth flow" \
  | jq -r 'select(.type=="agent_end") | .messages[] | select(.role=="assistant") | .content[] | select(.type=="text") | .text'
```

**Event sequence** (one JSON object per line):

```
session (header, first line)
agent_start
  turn_start
    message_start
    message_update      ← streaming text/thinking/tool deltas
    message_end
    tool_execution_start
    tool_execution_update
    tool_execution_end
  turn_end
agent_end               ← final messages
```

Full event reference: `reference/json-mode.md`.

## RPC mode — bidirectional control

Headless, fully programmatic. Drive pi from any language via JSONL on stdin/stdout.

```bash
pi --mode rpc --no-session [--provider anthropic --model sonnet:high]
```

**Protocol:** one JSON object per line, `\n` only. Commands → stdin. Responses (`type: "response"`) and events → stdout. Optional `id` field correlates request/response.

**Key commands:** `prompt`, `steer`, `follow_up`, `abort`, `bash`, `new_session`, `switch_session`, `get_state`, `get_messages`, `set_model`, `set_thinking_level`, `compact`, `get_commands`, `get_session_stats`, `fork`.

**Streaming behavior:** sending `prompt` while the agent is mid-stream requires `streamingBehavior: "steer" | "followUp"` or it errors.

**Node.js framing trap:** **do not use Node's `readline`** — it splits on Unicode line separators U+2028/U+2029 in addition to `\n`, which corrupts the protocol. Use a `StringDecoder`-based buffered reader splitting only on `\n`.

Minimal Python and Node examples + the full command reference: `reference/rpc-mode.md`.

## SDK mode — in-process Node.js

Same `AgentSession` object the CLI uses internally. Skip the subprocess.

```bash
pnpm add @mariozechner/pi-coding-agent
```

```typescript
import { createAgentSession, SessionManager } from "@mariozechner/pi-coding-agent";

const { session } = await createAgentSession({
    sessionManager: SessionManager.inMemory(),
});

session.subscribe((event) => {
    if (event.type === "message_update" &&
        event.assistantMessageEvent.type === "text_delta") {
        process.stdout.write(event.assistantMessageEvent.delta);
    }
});

await session.prompt("What files are in the current directory?");
```

**Key building blocks:**
- `createAgentSession({ cwd, agentDir, model, thinkingLevel, tools, customTools, resourceLoader, sessionManager, settingsManager })`
- `DefaultResourceLoader` — override system prompt, inject context files, register `.claude/commands/` as prompts, attach extension factories
- `SessionManager.inMemory() | .create(cwd) | .continueRecent(cwd) | .open(path)` — sessions are JSONL trees that can branch
- `AgentSession`: `prompt(text, { streamingBehavior })`, `steer`, `followUp`, `compact`, `abort`, `dispose`, plus state (`messages`, `isStreaming`, `model`, `thinkingLevel`, `agent.state`)
- `runPrintMode(runtime, opts)` / `runRpcMode(runtime)` / `new InteractiveMode(runtime, opts)` — embed any of the CLI run modes inside your harness

Full SDK API + ResourceLoader override patterns: `reference/sdk-mode.md`.

## Multi-agent orchestration

For teams of pi workers (decompose → dispatch → review → integrate → test):
- Workers: `pi --mode rpc --no-session` subprocesses, one per specialized role
- Orchestrator: SDK `AgentSession`, or another `pi --mode json` shell
- Coordination: orchestrator sends `prompt`, reads `agent_end` for results
- Parallel: `Promise.all` over RPC subprocesses, or tmux session matrix
- Three-tier (orchestrator → team leads → workers) is supported — pi has no opinion on topology

Patterns + pitfalls: `reference/orchestration.md`.

## Environment variables

| Variable | Effect |
|---|---|
| `PI_CODING_AGENT_DIR` | Override config dir (default `~/.pi/agent`) |
| `PI_CODING_AGENT_SESSION_DIR` | Override session storage location |
| `PI_OFFLINE` | Disable startup network operations (update checks, telemetry) |
| `PI_SKIP_VERSION_CHECK` | Skip pi.dev version probe |
| `PI_TELEMETRY` | Enable/disable install telemetry (`1`/`0`) |
| `PI_CACHE_RETENTION` | Set `long` for extended prompt cache |
| `ANTHROPIC_API_KEY` (etc.) | Picked up automatically; `--api-key` overrides |

## Canonical headless dispatch recipe

When invoking pi from a script, this is the safe form. It survives paths with spaces, works under zsh AND bash, captures pipeline exit codes correctly, and writes pure JSONL to the events file.

```bash
PI_WT="$REPO_ROOT"               # or per-worker worktree
PI_OUT="$SLICE_DIR/events.jsonl"
PI_ERR="$SLICE_DIR/stderr.log"
PI_PROMPT="$SLICE_DIR/prompt.txt"
PI_TIMEOUT=900                   # seconds; 1800 for complex
PI_PROVIDER=openai-codex         # placeholder — call resolve_pi_model with the codex preference list
PI_MODEL=gpt-5.3-codex           # placeholder — fallback walks gpt-5.5 → gpt-5.4 → gpt-5.3-codex
PI_THINKING=xhigh                # paired default

bash -c '
  cat "$1" \
  | gtimeout --kill-after=30 --foreground "$2" \
      bash -c "
        cd \"\$1\" && pi \
          --mode json \
          --no-session \
          --offline \
          --provider \"\$2\" \
          --model \"\$3\" \
          --thinking-level \"\$4\"
      " _ "$3" "$4" "$5" "$6" \
    > "$7" 2> "$8"
  echo "${PIPESTATUS[1]}" > "$9"
' _ "$PI_PROMPT" "$PI_TIMEOUT" "$PI_WT" "$PI_PROVIDER" "$PI_MODEL" "$PI_THINKING" \
    "$PI_OUT" "$PI_ERR" "$SLICE_DIR/exit_code"
```

Why each piece:
- Outer `bash -c` so `PIPESTATUS` works regardless of caller shell (zsh's `pipestatus` is incompatible).
- Inner `bash -c "... cd \"\$1\" && pi ..." _ "$path"` because pi has no `--cd` flag; positional args avoid shell-quoting hell on paths with spaces.
- `gtimeout --kill-after=30 --foreground "$T"` enforces wall-clock cap, escalates SIGTERM → SIGKILL after 30s, keeps signals reaching pi (not just the wrapper).
- `--mode json --no-session --offline` is the parallel-safe ephemeral combo.
- For review passes: add `--no-tools` so the reviewer can't edit files (pi's closest substitute for a read-only sandbox).
- Linux: replace `gtimeout` with `timeout`.

## Failure detection (do NOT trust `$?` alone)

Apply rules in this order, first match wins:

1. **Auth failure** in stderr OR events → first try the next entry in the model's preference list (one cross-provider retry only); if no fallback remains or it also auth-fails, ABORT entire run. Patterns:
   - OpenAI / `openai-codex`: `Incorrect API key`, `Invalid API key`, HTTP 401 + `invalid_request_error`
   - Anthropic: `invalid x-api-key`, `authentication_error`
   - Google/Gemini: `API key not valid`, `INVALID_ARGUMENT` (case-sensitive), HTTP 400
   - GitHub Copilot: `not authenticated`, `subscription required`, OAuth token expired
   - Generic: `401 Unauthorized`, `unauthorized`
2. **Billing failure** (`insufficient_quota`, `quota.exceeded`) → try the next preference-list entry once; if it also fails or no fallback exists, ABORT (don't consume retry budget on a misconfigured account).
3. **Rate limit** (HTTP 429, `rate_limit_error`, `rate_limit_exceeded`, `RESOURCE_EXHAUSTED`, `too many requests`) → RETRIABLE (single retry with 60s backoff).
4. `events.jsonl` missing/empty → FAIL (worker hung or never started).
5. Stream is only `error` events with no completion marker → FAIL.
6. Exit code 124 from `gtimeout` → TIMED_OUT, mark FAIL (no auto-retry beyond plan caps).
7. Worker ran but `git diff --cached --quiet` after `git add -A` → no edits made; FAIL on cycle 1, possibly DEMOTE on cycle 2 if cycle 1 already produced a good commit.

Auth/billing failures hit every worker the same way — short-circuit the whole run; do not consume retry budget.

## Token usage extraction (best-effort)

Pi's `--mode json` event schema for token usage is not officially stable. Scan events for any object exposing `usage` / `tokens` / `inputTokens` / `outputTokens` / `contextUsage`:

```bash
jq -s '
  map(select((.usage // .tokens // .contextUsage) != null))
  | map(.usage // .tokens // .contextUsage)
' events.jsonl 2>/dev/null
```

If nothing matches, mark token usage as `not captured` rather than fabricating numbers.

## Reviewer JSON parse fallback

When a reviewer worker is asked for JSON output, parse with this cascade:

1. `JSON.parse(content)` over the whole assistant message.
2. Search for the first ` ```json … ``` ` fenced block; parse its body.
3. Search for the first balanced `{ … }` block; parse.
4. On total failure: synthesize `{ verdict: "NEEDS_FIX", findings: [{ severity: "HIGH", issue: "reviewer output unparseable" }] }`. Never count an unparseable response as a PASS.

## Don't

- **Don't** modify `~/.pi/agent/auth.json` or `~/.pi/agent/AGENTS.md`.
- **Don't** use Node's `readline` to parse RPC stdout — see RPC framing trap.
- **Don't** rely on pi's session resume (`--continue` / `--session <id>`) for reproducibility — re-dispatch with prior context inlined into the prompt instead.
- **Don't** dispatch parallel `git worktree add` calls — they race on `.git/config.lock`. Serialize creation; only the workers run parallel.
- **Don't** run multiple workers in the same working directory — pi has no sandbox; they will overwrite each other.
- **Don't** default to `--no-context-files`. Workers should inherit `AGENTS.md` / `CLAUDE.md` unless conventions conflict.
- **Don't** use `pi --print` without `--no-session` and `--offline` in CI/scripts — you'll persist sessions and probe the network.
