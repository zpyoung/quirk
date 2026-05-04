# Print Mode (`pi -p` / `--print`)

The fastest path to headless. Pi runs the prompt, executes tools autonomously, then prints the final assistant text to stdout and exits.

## Basic shapes

```bash
pi -p "Summarize this codebase"
```

### Piped stdin (key for pipeline composition)

Pi merges piped stdin into the initial prompt:

```bash
cat README.md | pi -p "Summarize this text"
git diff HEAD~1 | pi -p "Write a conventional commit message for this diff"
```

> **Pre-0.65.1 caveat:** older versions silently drop piped stdin in non-interactive mode. The fallback is `@file` arguments. Preflight checks should pin `pi >= 0.65.1` to avoid this.

### File arguments (`@`)

Prefix paths with `@` to inline files into the message:

```bash
pi -p @prompt.md "Answer this"
pi -p @screenshot.png "What's in this image?"
pi @code.ts @test.ts "Review these files"
```

`@`-args work for text, source code, and images alike.

## Critical flags for automation

| Flag | Effect |
|---|---|
| `--no-session` | Ephemeral; nothing persisted to `~/.pi/agent/sessions/` |
| `--offline` | Suppress startup network/update check |
| `--tools read,bash,edit,write` | Allowlist of built-in tools |
| `--no-builtin-tools` | Disable all built-in tools (extension tools still load) |
| `--no-tools` | Disable ALL tools — LLM only, no execution |
| `--model sonnet:high` | Provider/model/thinking shorthand |
| `--no-context-files` | Skip `AGENTS.md` / `CLAUDE.md` discovery |
| `--no-extensions` | Skip extension discovery |
| `-e ./my-ext.ts` | Load exactly one extension (combine with `--no-extensions`) |
| `--system-prompt "..."` | Replace the default system prompt |
| `--append-system-prompt "..."` | Append to default system prompt |

## Patterns

### Read-only analysis (safe-ish for CI)

```bash
pi --tools read,grep,find,ls -p "Review the code for security issues"
```

Combine with `--no-tools` for pure analysis where the LLM isn't allowed to run anything at all.

### Pipeline orchestration (pi-captain style)

Each step is an isolated subprocess; pin the model per stage to balance speed vs depth.

```bash
# Quick analysis step
pi --print --no-session --offline --model flash --tools read \
  "Summarize the architecture"

# Deep implementation step
pi --print --no-session --offline --model sonnet --tools read,bash,edit,write \
  "Implement the authentication module per AGENTS.md"
```

### Proposed flags (track in pi issue tracker)

`--max-turns <n>` and `--max-tokens <n>` are proposed for capping individual subprocess cost in pipelines. Until they ship, time-box with `gtimeout`/`timeout` and rely on the model's own stop conditions.

## When NOT to use print mode

- You want to observe streaming tool calls, thinking, or partial output → use **JSON mode**.
- You need multi-turn control (steer, follow-up, abort, model swap mid-session) → use **RPC** or **SDK**.
- You're in a Node.js process and want types + same-process speed → use **SDK**.
