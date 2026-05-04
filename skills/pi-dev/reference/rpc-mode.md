# RPC Mode (`pi --mode rpc`)

Bidirectional JSONL protocol over stdin/stdout. Pi never draws a TUI; you drive it with JSON commands from any language. This is the embedding mode for IDEs, Slack/Discord bots, Electron apps, and custom orchestrators in non-Node hosts.

## Launching

```bash
pi --mode rpc --no-session
# Optional: --provider anthropic --model sonnet:high --session-dir <path>
```

## Protocol framing

- One JSON object per line, **`\n` only** (not `\r\n`, not Unicode line separators).
- **Commands** are sent on stdin (one per line).
- **Responses** (`type: "response"`) and **events** are streamed on stdout.
- All commands accept an optional `id` field for request/response correlation.

## Commands

| Command | Purpose |
|---|---|
| `{"type":"prompt","message":"..."}` | Send a prompt (main entry point) |
| `{"type":"steer","message":"..."}` | Queue a message during streaming, delivered after current tool calls finish |
| `{"type":"follow_up","message":"..."}` | Queue a message delivered after agent fully stops |
| `{"type":"abort"}` | Abort current operation |
| `{"type":"bash","command":"ls -la"}` | Execute shell command; output injected into next LLM context |
| `{"type":"new_session"}` | Start fresh session |
| `{"type":"switch_session","sessionPath":"..."}` | Load a different session file |
| `{"type":"get_state"}` | Current model, thinking level, isStreaming, session info, token counts |
| `{"type":"get_messages"}` | Full conversation history |
| `{"type":"set_model","provider":"anthropic","modelId":"claude-sonnet-4-20250514"}` | Switch model mid-session |
| `{"type":"set_thinking_level","level":"high"}` | Reasoning level (`off`, `low`, `medium`, `high`, `xhigh`) |
| `{"type":"compact","customInstructions":"..."}` | Manually compact context |
| `{"type":"get_commands"}` | List all available slash commands, skills, prompt templates |
| `{"type":"get_session_stats"}` | Token usage, cost, context-window % |
| `{"type":"fork","entryId":"abc123"}` | Fork from a previous message |

## Streaming-behavior contract

If you send a `prompt` while the agent is already streaming, you MUST declare the behavior or pi returns an error:

```json
{"type":"prompt","message":"Stop and do this instead","streamingBehavior":"steer"}
{"type":"prompt","message":"After you're done also do X","streamingBehavior":"followUp"}
```

`steer` queues the message for delivery after the current tool calls finish; `followUp` waits until the agent fully stops.

## Extension UI sub-protocol

Extensions that call `ctx.ui.select()`, `ctx.ui.confirm()`, or `ctx.ui.input()` in interactive mode emit `extension_ui_request` events in RPC mode and block until the host sends back a matching `extension_ui_response`. Fire-and-forget UI methods (`notify`, `setStatus`, `setWidget`) emit events with no response required.

## Python client (minimal)

```python
import subprocess, json

proc = subprocess.Popen(
    ["pi", "--mode", "rpc", "--no-session"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
)

def send(cmd):
    proc.stdin.write(json.dumps(cmd) + "\n")
    proc.stdin.flush()

def stream():
    for line in proc.stdout:
        yield json.loads(line)

send({"type": "prompt", "message": "What files are here?"})

for event in stream():
    if event.get("type") == "message_update":
        delta = event.get("assistantMessageEvent", {})
        if delta.get("type") == "text_delta":
            print(delta["delta"], end="", flush=True)
    if event.get("type") == "agent_end":
        break
```

## Node.js JSONL reader (do NOT use `readline`)

Node's `readline` splits on Unicode line separators U+2028 and U+2029 in addition to `\n`. The pi protocol allows those characters inside JSON string fields, so `readline` will silently split a single event across two "lines" and corrupt parsing. Use a `StringDecoder`-based buffered reader splitting only on `\n`:

```typescript
import { StringDecoder } from "string_decoder";
import { spawn } from "child_process";

const agent = spawn("pi", ["--mode", "rpc", "--no-session"]);
const decoder = new StringDecoder("utf8");
let buffer = "";

agent.stdout.on("data", (chunk) => {
    buffer += decoder.write(chunk);
    while (true) {
        const idx = buffer.indexOf("\n");
        if (idx === -1) break;
        let line = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 1);
        if (line.endsWith("\r")) line = line.slice(0, -1);
        const event = JSON.parse(line);
        // handle event
    }
});

agent.stdin.write(JSON.stringify({ type: "prompt", message: "Hello" }) + "\n");
```

## When to use RPC mode

- Multi-turn agent inside a Python/Go/Rust/Ruby host.
- IDE integration where you need to interrupt, steer, and resume.
- Multi-agent orchestration where workers are pi subprocesses (the orchestrator can be SDK or another language).

## When NOT to use RPC mode

- Single-shot CI step → **print mode** is one line.
- Node.js process → **SDK** is the same thing in-process with TypeScript types.
- You only want a stream of events, no input → **JSON mode** is simpler.
