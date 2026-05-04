# JSON Event Stream Mode (`pi --mode json`)

Same one-shot semantics as print mode, but the entire internal event stream is emitted as JSONL on stdout. Plain text logs go to stderr. Best mode when tooling needs to observe tool calls, thinking blocks, or streaming text deltas in real time.

## Basic shape

```bash
pi --mode json "List files" 2>/dev/null | jq -c 'select(.type == "message_end")'
```

## Stream structure

### Session header (always the first line)

```json
{"type":"session","version":3,"id":"uuid","timestamp":"...","cwd":"/repo"}
```

### Event sequence

```
agent_start
  turn_start
    message_start
    message_update         ← streaming text_delta / thinking_delta / toolcall_*
    message_end
    tool_execution_start
    tool_execution_update  ← streaming partial tool output
    tool_execution_end
  turn_end
agent_end                  ← final messages array, end of stream
```

Multiple `turn_start`/`turn_end` cycles can occur between `agent_start` and `agent_end` if the model uses tools.

## Common extractions

### Final assistant text only

```bash
pi --mode json "Explain the auth flow" \
  | jq -r '
      select(.type=="agent_end")
      | .messages[]
      | select(.role=="assistant")
      | .content[]
      | select(.type=="text")
      | .text
    '
```

### All tool executions

```bash
pi --mode json "Fix the failing tests" \
  | jq 'select(.type | startswith("tool_execution"))'
```

### Streaming text deltas (live progress)

```bash
pi --mode json "Refactor X" \
  | jq -r '
      select(.type=="message_update")
      | .assistantMessageEvent
      | select(.type=="text_delta")
      | .delta
    '
```

### Best-effort token usage

The JSONL token usage event is not officially documented as stable. Scan for any object exposing `usage`, `tokens`, `inputTokens`, `outputTokens`, or `contextUsage`:

```bash
jq -s '
  map(select((.usage // .tokens // .contextUsage) != null))
  | map(.usage // .tokens // .contextUsage)
' events.jsonl 2>/dev/null
```

If nothing matches, mark token usage as `not captured` rather than fabricating numbers.

## Reading the stream from a parent process

Always split on **`\n` only**. Do NOT use Node's `readline` (it splits on U+2028/U+2029 too — see RPC mode for the same trap). Use a buffered byte-or-string reader.

## Failure signatures inside the stream

When watching `events.jsonl`, look for:

- The stream is only `error` events with no `agent_end` → worker failed.
- `agent_end` is reached but the assistant `content` array is empty → model refused or produced nothing.
- Auth/billing/rate-limit error messages may appear inside `error` events with the same provider-specific patterns documented in the main SKILL.md failure-detection section.

## When to use JSON mode

- You want progress logging / live UI updates.
- You need to filter or post-process tool calls for audit/compliance.
- You want a structured, parseable record of an autonomous run.

## When NOT to use JSON mode

- You only want the final answer → **Print mode** is simpler.
- You need to drive a multi-turn conversation programmatically → **RPC** or **SDK**.
