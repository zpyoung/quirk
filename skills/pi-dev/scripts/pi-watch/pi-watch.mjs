#!/usr/bin/env node
/**
 * pi-watch — high-level pi runner. Agent passes prompt + alias; the script
 * resolves provider/model/thinking, walks a fallback ladder for whatever is
 * authed locally, and streams the result.
 *
 *   stdout = assistant text only (caller can capture cleanly with $(...))
 *   stderr = "  ▶ resolved <p>/<m>:<t>" header, "  ⚙ tool args" lines, "  ✔ done"
 *
 * Bypasses pi's DefaultResourceLoader (extensions / skills / prompts / themes /
 * AGENTS.md discovery) so it starts instantly regardless of cwd.
 *
 * Usage:
 *   pi-watch --alias <alias> [--thinking <level>] [--tools t1,t2|--no-tools] "<prompt>"
 *   pi-watch --provider <p> --model <m> [--thinking <level>] [--tools ...] "<prompt>"
 *   pi-watch --list-aliases
 */

import { spawnSync } from "node:child_process";
import { getModel } from "@mariozechner/pi-ai";
import {
    AuthStorage,
    createAgentSession,
    createExtensionRuntime,
    ModelRegistry,
    SessionManager,
    SettingsManager,
} from "@mariozechner/pi-coding-agent";

// ---- Aliases -------------------------------------------------------------
// Each alias = (default thinking level) + ordered preference list. First combo
// that's both shipping in pi AND authed locally wins. Newest-first so aliases
// auto-upgrade as new models ship. Pro-tier variants are intentionally absent
// (~10–30× cost, multi-minute latency) — only dispatch on explicit request.
const ALIASES = {
    // Default coding alias — gpt flagship via codex routing. GPT-5.6 Sol is the
    // flagship tier (successor to gpt-5.5, same $5/$30 price point).
    codex: {
        thinking: "medium",
        prefs: [
            "openai-codex/gpt-5.6-sol", "openai/gpt-5.6-sol", "github-copilot/gpt-5.6-sol",
            "openai-codex/gpt-5.5", "openai/gpt-5.5",
            "openai-codex/gpt-5.4", "openai/gpt-5.4", "github-copilot/gpt-5.4",
            "openai-codex/gpt-5.3-codex", "openai/gpt-5.3-codex", "github-copilot/gpt-5.3-codex",
        ],
    },
    // Deepest reasoning. GPT-5.6 folded the standalone -codex-max model into Sol,
    // the only tier that natively supports the `max` reasoning effort; older
    // fallback models clamp max→xhigh.
    "codex-max": {
        thinking: "max",
        prefs: [
            "openai-codex/gpt-5.6-sol", "openai/gpt-5.6-sol", "github-copilot/gpt-5.6-sol",
            "openai-codex/gpt-5.5-codex-max", "openai/gpt-5.5-codex-max",
            "openai-codex/gpt-5.4-codex-max", "openai/gpt-5.4-codex-max",
            "openai-codex/gpt-5.1-codex-max", "openai/gpt-5.1-codex-max", "github-copilot/gpt-5.1-codex-max",
        ],
    },
    // Fast / cheapest coding tier. GPT-5.6 Luna is the mini/spark successor.
    "codex-mini": {
        thinking: "medium",
        prefs: [
            "openai-codex/gpt-5.6-luna", "openai/gpt-5.6-luna", "github-copilot/gpt-5.6-luna",
            "openai-codex/gpt-5.4-mini", "openai/gpt-5.4-mini", "github-copilot/gpt-5.4-mini",
            "openai-codex/gpt-5.1-codex-mini", "openai/gpt-5.1-codex-mini", "github-copilot/gpt-5.1-codex-mini",
        ],
    },
    "codex-spark": {
        thinking: "high",
        prefs: [
            "openai-codex/gpt-5.4-codex-spark",
            "openai-codex/gpt-5.3-codex-spark", "openai/gpt-5.3-codex-spark",
        ],
    },
    // Balanced everyday coding tier — GPT-5.6 Terra ($2.50/$15, ~gpt-5.5-class at
    // half the cost). Falls back to gpt-5.4, the same-priced balanced predecessor.
    terra: {
        thinking: "high",
        prefs: [
            "openai-codex/gpt-5.6-terra", "openai/gpt-5.6-terra", "github-copilot/gpt-5.6-terra",
            "openai-codex/gpt-5.4", "openai/gpt-5.4", "github-copilot/gpt-5.4",
        ],
    },
    sonnet: {
        thinking: "high",
        prefs: [
            "anthropic/claude-sonnet-4-7", "github-copilot/claude-sonnet-4.7",
            "anthropic/claude-sonnet-4-6", "github-copilot/claude-sonnet-4.6",
        ],
    },
    opus: {
        thinking: "high",
        prefs: [
            "anthropic/claude-opus-4-7", "github-copilot/claude-opus-4.7",
            "anthropic/claude-opus-4-6", "github-copilot/claude-opus-4.6",
        ],
    },
    haiku: {
        thinking: "medium",
        prefs: [
            "anthropic/claude-haiku-4-6", "github-copilot/claude-haiku-4.6",
            "anthropic/claude-haiku-4-5", "github-copilot/claude-haiku-4.5",
        ],
    },
    gemini: {
        thinking: "high",
        prefs: [
            "google/gemini-3.2-pro-preview",
            "google/gemini-3.1-pro-preview", "github-copilot/gemini-3.1-pro-preview",
            "google/gemini-3-pro-preview", "github-copilot/gemini-3-pro-preview",
        ],
    },
    flash: {
        thinking: "medium",
        prefs: [
            "google/gemini-flash-latest",
            "google/gemini-3-flash-preview", "github-copilot/gemini-3-flash-preview",
        ],
    },
    grok: {
        thinking: "medium",
        prefs: ["github-copilot/grok-code-fast-1"],
    },
};

// ---- CLI parsing ---------------------------------------------------------
const VALID_THINKING = new Set(["off", "minimal", "low", "medium", "high", "xhigh", "max"]);
const args = process.argv.slice(2);
const opts = {
    alias: null,
    provider: null,
    model: null,
    thinking: null,
    tools: ["read", "bash"],
    prompt: null,
    listAliases: false,
    check: false,
    checkAlias: null,
};
function takeValue(flag, i) {
    const v = args[i + 1];
    if (v === undefined || v.startsWith("--")) {
        console.error(`pi-watch: ${flag} requires a value`);
        process.exit(2);
    }
    return v;
}
for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--alias") { opts.alias = takeValue(a, i); i++; }
    else if (a === "--provider") { opts.provider = takeValue(a, i); i++; }
    else if (a === "--model") { opts.model = takeValue(a, i); i++; }
    else if (a === "--thinking" || a === "--thinking-level") { opts.thinking = takeValue(a, i); i++; }
    else if (a === "--tools") { opts.tools = takeValue(a, i).split(",").map((s) => s.trim()).filter(Boolean); i++; }
    else if (a === "--no-tools") opts.tools = [];
    else if (a === "--list-aliases") opts.listAliases = true;
    else if (a === "--check") {
        opts.check = true;
        // Optional alias argument: the next non-flag token, if present.
        if (args[i + 1] !== undefined && !args[i + 1].startsWith("--")) { opts.checkAlias = args[i + 1]; i++; }
    }
    else if (a === "-h" || a === "--help") { printHelp(); process.exit(0); }
    else if (a.startsWith("--")) { console.error(`pi-watch: unknown flag ${a}`); process.exit(2); }
    else { opts.prompt = (opts.prompt ? opts.prompt + " " : "") + a; }
}

if (opts.thinking !== null && !VALID_THINKING.has(opts.thinking)) {
    console.error(`pi-watch: invalid --thinking '${opts.thinking}'. Valid: ${[...VALID_THINKING].join(", ")}`);
    process.exit(2);
}
if (opts.alias && (opts.provider || opts.model)) {
    console.error(`pi-watch: --alias is mutually exclusive with --provider/--model`);
    process.exit(2);
}
if ((opts.provider && !opts.model) || (opts.model && !opts.provider)) {
    console.error(`pi-watch: --provider and --model must be passed together`);
    process.exit(2);
}

if (opts.listAliases) {
    for (const [name, cfg] of Object.entries(ALIASES)) {
        console.log(`${name.padEnd(12)} thinking=${cfg.thinking}  prefs=${cfg.prefs.length}`);
        for (const combo of cfg.prefs) console.log(`  - ${combo}`);
    }
    process.exit(0);
}

// --check is a preflight mode: validate alias resolution, then exit. It never
// runs a prompt, so it short-circuits before the prompt-required path below.
if (opts.check) {
    if (opts.prompt || opts.alias || opts.provider || opts.model) {
        process.stderr.write("  ⓘ --check validates aliases only — ignoring prompt/--alias/--provider/--model (no model is run)\n");
    }
    runCheck(opts.checkAlias, opts.thinking);
}

function printHelp() {
    console.error('Usage:');
    console.error('  pi-watch --alias <alias> [--thinking <level>] [--tools t1,t2|--no-tools] "<prompt>"');
    console.error('  pi-watch --provider <p> --model <m> [--thinking <level>] [--tools ...] "<prompt>"');
    console.error('  pi-watch --check [alias]       # preflight: which aliases resolve to an authed model');
    console.error('  pi-watch --list-aliases');
    console.error('');
    console.error(`Aliases: ${Object.keys(ALIASES).join(", ")}`);
}

// ---- Resolve provider/model/thinking -------------------------------------
function listAvailable() {
    // pi --list-models writes the table to STDERR. Fast (~0.5s) and does not
    // trigger pi's slow cwd resource scan, so safe to call from any directory.
    // We rely on `pi` (not the SDK registry) to resolve auth — it handles env
    // vars, ~/.pi/agent/auth.json, OAuth subscription tokens, and models.json
    // overrides uniformly. Reimplementing that in-process would diverge.
    const res = spawnSync("pi", ["--list-models"], { encoding: "utf8" });
    if (res.error) {
        console.error(`pi-watch: cannot run 'pi --list-models': ${res.error.message}`);
        process.exit(4);
    }
    if (res.status !== 0 && res.status !== null) {
        console.error(`pi-watch: 'pi --list-models' exited ${res.status}`);
        if (res.stderr) console.error(res.stderr.slice(0, 2000));
        process.exit(4);
    }
    const text = (res.stderr || "") + (res.stdout || "");
    const set = new Set();
    for (const line of text.split("\n")) {
        const stripped = line.replace(/\x1b\[[0-9;]*m/g, "").trim();
        if (!stripped) continue;
        const cols = stripped.split(/\s+/);
        if (cols.length < 2) continue;
        if (/^provider/i.test(cols[0]) || /^[-=]+$/.test(cols[0])) continue;
        set.add(`${cols[0]}/${cols[1]}`);
    }
    return set;
}

// Walk an alias's preference ladder against a set of authed/shipping combos.
// Returns the first match as {provider, model, thinking}, or null if none —
// no process.exit, so callers (resolveAlias, runCheck) decide how to react.
function resolveAgainst(cfg, avail, thinkingOverride) {
    for (const combo of cfg.prefs) {
        if (avail.has(combo)) {
            const slash = combo.indexOf("/");
            return {
                provider: combo.slice(0, slash),
                model: combo.slice(slash + 1),
                thinking: thinkingOverride ?? cfg.thinking,
            };
        }
    }
    return null;
}

function resolveAlias(alias, thinkingOverride) {
    const cfg = ALIASES[alias];
    if (!cfg) {
        console.error(`pi-watch: unknown alias '${alias}'. Known: ${Object.keys(ALIASES).join(", ")}`);
        process.exit(2);
    }
    const resolved = resolveAgainst(cfg, listAvailable(), thinkingOverride);
    if (resolved) return { ...resolved, triedFromAlias: true };
    console.error(`pi-watch: no provider in alias '${alias}' is authed/shipping. Tried:`);
    for (const combo of cfg.prefs) console.error(`  - ${combo}`);
    console.error(`Run 'pi --list-models' to see what's available, or run 'pi /login' for the provider you want.`);
    process.exit(5);
}

// --check [alias]: preflight which aliases resolve to a locally-authed model
// WITHOUT running a prompt. Validates one alias (if given) or every alias.
// Exit 0 = all checked aliases are ready; exit 5 = at least one is not;
// exit 2 = the named alias is unknown; exit 4 = `pi` itself can't be queried.
//
// The report goes to STDERR — pi-watch reserves stdout for assistant text, so
// gating a captured dispatch (`result="$(pi-watch --check x && pi-watch ...)"`)
// stays clean. The exit code, not stdout, is the machine-readable gate signal.
//
// `checkAlias` is null only when no alias was supplied (→ check all); a
// provided-but-empty string is an explicit (invalid) alias → exit 2.
function runCheck(checkAlias, thinkingOverride) {
    if (checkAlias !== null && !ALIASES[checkAlias]) {
        console.error(`pi-watch: unknown alias '${checkAlias}'. Known: ${Object.keys(ALIASES).join(", ")}`);
        process.exit(2);
    }
    const names = checkAlias !== null ? [checkAlias] : Object.keys(ALIASES);
    const avail = listAvailable();   // runs `pi --list-models` once; exits 4 if pi is missing
    const pad = Math.max(...names.map((n) => n.length));
    const failed = [];
    process.stderr.write(`pi-watch: validating ${checkAlias !== null ? `alias '${checkAlias}'` : "aliases"} against authed models (pi --list-models)\n\n`);
    for (const name of names) {
        const cfg = ALIASES[name];
        const resolved = resolveAgainst(cfg, avail, thinkingOverride);
        if (resolved) {
            process.stderr.write(`  ✓ ${name.padEnd(pad)}  ${resolved.provider}/${resolved.model}:${resolved.thinking}\n`);
        } else {
            failed.push(name);
            process.stderr.write(`  ✗ ${name.padEnd(pad)}  no authed/shipping model (0/${cfg.prefs.length} combos)\n`);
        }
    }
    const okCount = names.length - failed.length;
    process.stderr.write("\n");
    if (failed.length === 0) {
        process.stderr.write(`${okCount}/${names.length} ${names.length === 1 ? "alias" : "aliases"} ready.\n`);
        process.exit(0);
    }
    process.stderr.write(`${okCount}/${names.length} ready — not available: ${failed.join(", ")}.\n`);
    process.stderr.write(`Run 'pi /login' for the needed provider, or 'pi --list-models' to see what's authed.\n`);
    if (checkAlias !== null) {
        process.stderr.write(`\nLadder tried for '${checkAlias}':\n`);
        for (const combo of ALIASES[checkAlias].prefs) process.stderr.write(`  - ${combo}\n`);
    }
    process.exit(5);
}

let resolved;
if (opts.alias) {
    resolved = resolveAlias(opts.alias, opts.thinking);
} else if (opts.provider && opts.model) {
    resolved = { provider: opts.provider, model: opts.model, thinking: opts.thinking ?? "high", triedFromAlias: false };
} else {
    printHelp();
    process.exit(2);
}

if (!opts.prompt) {
    console.error('pi-watch: missing prompt. Pass it as a positional arg.');
    process.exit(2);
}

// ---- Bypass DefaultResourceLoader ----------------------------------------
const model = getModel(resolved.provider, resolved.model);
if (!model) {
    console.error(`pi-watch: model not in pi-ai registry: ${resolved.provider}/${resolved.model}`);
    console.error(`(This usually means pi shipped the model in --list-models but pi-ai is older. Run 'pnpm update' in this dir.)`);
    process.exit(3);
}

const resourceLoader = {
    getExtensions: () => ({ extensions: [], errors: [], runtime: createExtensionRuntime() }),
    getSkills: () => ({ skills: [], diagnostics: [] }),
    getPrompts: () => ({ prompts: [], diagnostics: [] }),
    getThemes: () => ({ themes: [], diagnostics: [] }),
    getAgentsFiles: () => ({ agentsFiles: [] }),
    getSystemPrompt: () => "You are a coding assistant. Be concise and direct.",
    getAppendSystemPrompt: () => [],
    extendResources: () => {},
    reload: async () => {},
};

const cwd = process.cwd();
const home = process.env.HOME ?? "";
const authStorage = AuthStorage.create(`${home}/.pi/agent/auth.json`);
const modelRegistry = ModelRegistry.inMemory(authStorage);
const settingsManager = SettingsManager.inMemory({
    compaction: { enabled: false },
    retry: { enabled: true, maxRetries: 2 },
});

process.stderr.write(`  ▶ resolved ${resolved.provider}/${resolved.model}:${resolved.thinking}${resolved.triedFromAlias ? ` (alias ${opts.alias})` : ""}\n`);

try {
    const { session } = await createAgentSession({
        cwd,
        agentDir: `${home}/.pi/agent`,
        model,
        thinkingLevel: resolved.thinking,
        authStorage,
        modelRegistry,
        resourceLoader,
        tools: opts.tools,
        sessionManager: SessionManager.inMemory(cwd),
        settingsManager,
    });

    session.subscribe((event) => {
        if (event.type === "message_update" && event.assistantMessageEvent?.type === "text_delta") {
            process.stdout.write(event.assistantMessageEvent.delta);
        } else if (event.type === "tool_execution_start") {
            const a = event.args ?? {};
            const summary = a.command ?? a.file_path ?? a.path ?? a.pattern ?? "";
            process.stderr.write(`  ⚙ ${event.toolName} ${summary}\n`);
        }
    });

    await session.prompt(opts.prompt);
    process.stdout.write("\n");
    process.stderr.write("  ✔ done\n");
    process.exit(0);
} catch (err) {
    process.stderr.write(`\n  ✖ error: ${err?.message ?? err}\n`);
    process.exit(1);
}
