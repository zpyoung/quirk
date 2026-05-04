#!/usr/bin/env bash
set -u
# PostToolUse hook for typed-artifacts.
# - Reads JSON from stdin; extracts tool_input.file_path.
# - Greps the file for tic phrases from templates/tic_phrases.json.
# - On match: emits a warning suggesting the routing destination.
# - On no match, no artifacts, missing file, missing patterns, or binary file: silent.
# Always exits 0.

[[ -z "${CLAUDE_PROJECT_DIR:-}" ]] && exit 0
[[ ! -f "$CLAUDE_PROJECT_DIR/BUGS.md" ]] && exit 0  # gate on artifacts

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")")}"
PHRASES="$PLUGIN_ROOT/templates/tic_phrases.json"
[[ -f "$PHRASES" ]] || exit 0

# Read stdin; extract file_path with python (json on path everywhere).
stdin_json="$(cat 2>/dev/null || true)"
[[ -z "$stdin_json" ]] && exit 0

file_path="$(printf '%s' "$stdin_json" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get("tool_input",{}).get("file_path",""))
except Exception:
    pass' 2>/dev/null)"

[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

# Skip binaries — use grep -I (skip binary files).
if ! grep -Iq '' "$file_path" 2>/dev/null; then
  exit 0
fi

# Extract phrase list with python.
phrases="$(python3 -c 'import json,sys
with open("'"$PHRASES"'") as f: d=json.load(f)
for p in d.get("patterns",[]):
    print(p["phrase"]+"\t"+p["suggested_artifact"])' 2>/dev/null)"

[[ -z "$phrases" ]] && exit 0

while IFS=$'\t' read -r phrase artifact; do
  [[ -z "$phrase" ]] && continue
  if grep -nFi -- "$phrase" "$file_path" >/dev/null 2>&1; then
    line=$(grep -nFi -- "$phrase" "$file_path" | head -n 1 | cut -d: -f1)
    echo "[quirk:typed-artifacts] Tic phrase '$phrase' detected at $file_path:$line — consider routing to $artifact"
  fi
done <<< "$phrases"

exit 0
