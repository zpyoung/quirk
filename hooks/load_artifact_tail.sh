#!/usr/bin/env bash
set -u
# SessionStart hook for typed-artifacts.
# - If artifact files exist: print last lines so Claude has context.
# - If artifact files are missing: suggest /quirk:artifacts:init.
# - If $CLAUDE_PROJECT_DIR is unset: silent no-op.
# Always exits 0.

[[ -z "${CLAUDE_PROJECT_DIR:-}" ]] && exit 0
[[ ! -d "$CLAUDE_PROJECT_DIR" ]] && exit 0

ARTIFACTS=(BUGS.md DEFERRED.md TEST_BACKLOG.md proposals.md)
present=0
for f in "${ARTIFACTS[@]}"; do
  [[ -f "$CLAUDE_PROJECT_DIR/$f" ]] && present=$((present+1))
done

if [[ $present -eq 0 ]]; then
  echo "[quirk:typed-artifacts] No artifact files in this project. Run /quirk:artifacts:init to scaffold."
  exit 0
fi

for f in "${ARTIFACTS[@]}"; do
  path="$CLAUDE_PROJECT_DIR/$f"
  [[ -f "$path" ]] || continue
  size=$(wc -c <"$path" 2>/dev/null || echo 0)
  if [[ "$size" -gt 1048576 ]]; then
    echo "[quirk:typed-artifacts] $f >1MB; skipping tail load."
    continue
  fi
  echo "----- $f (last 50 lines) -----"
  tail -n 50 "$path"
  echo ""
done

exit 0
