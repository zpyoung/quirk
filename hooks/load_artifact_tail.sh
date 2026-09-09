#!/usr/bin/env bash
set -u
# SessionStart hook for typed-artifacts.
# - If artifact files exist: call pm.py --index for a bounded summary.
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

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")")}"
PM="$PLUGIN_ROOT/bin/pm.py"

status=1
output=""
if [[ -f "$PM" ]]; then
  output="$(python3 "$PM" --index --project-dir "$CLAUDE_PROJECT_DIR" 2>/dev/null)"
  status=$?
fi

# A broken pm.py (non-zero exit, traceback, empty output, uninitialized
# project) must never break session start — fall back to one line instead.
if [[ $status -eq 0 && -n "$output" ]]; then
  echo "$output"
  # --index now names in_progress/delivered/closed work, but the unplaced count is
  # still a bare number; --next is the only surface that names which ready entry
  # to pick up next.
  shortlist="$(python3 "$PM" --next --project-dir "$CLAUDE_PROJECT_DIR" 2>/dev/null)"
  next_status=$?
  if [[ $next_status -eq 0 && -n "$shortlist" ]]; then
    grep -v 'unplaced (' <<<"$shortlist" || true
  fi
else
  echo "[quirk:pm] index unavailable"
fi

exit 0
