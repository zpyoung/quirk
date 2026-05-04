#!/usr/bin/env bash
set -u
# Stop hook for typed-artifacts.
# - Emits a one-line wrap-up reminder if artifact files exist.
# - Silent otherwise.
# Always exits 0.

[[ -z "${CLAUDE_PROJECT_DIR:-}" ]] && exit 0
[[ ! -f "$CLAUDE_PROJECT_DIR/BUGS.md" ]] && exit 0

echo "[quirk:typed-artifacts] Before closing: Route any unrouted observations to BUGS.md / DEFERRED.md / TEST_BACKLOG.md / proposals.md."
exit 0
