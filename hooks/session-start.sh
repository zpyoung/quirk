#!/usr/bin/env bash
# SessionStart hook for quirk plugin (Claude Code only)
# Injects the using-quirk skill content into every new/cleared/compacted session.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILL_FILE="${PLUGIN_ROOT}/skills/using-quirk/SKILL.md"

if [ ! -f "$SKILL_FILE" ]; then
    exit 0
fi

python3 - "$SKILL_FILE" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    skill = f.read()
context = (
    "<EXTREMELY_IMPORTANT>\n"
    "You have quirk skills.\n\n"
    "**Below is the full content of your 'quirk:using-quirk' skill — your "
    "introduction to using skills. For all other skills, use the 'Skill' tool:**\n\n"
    f"{skill}\n"
    "</EXTREMELY_IMPORTANT>"
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }
}))
PY
