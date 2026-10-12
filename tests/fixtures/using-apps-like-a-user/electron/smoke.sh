#!/usr/bin/env bash
# Boots the Electron fixture, attaches playwright-cli over CDP, checks every planted control is
# visible to the accessibility snapshot, that a click reaches the main process, and that the failing
# avatar request is visible to the renderer-side CDP network log.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=9333
SESSION=uala-electron-smoke
LABELS=(
  "Working button"
  "Dead button"
  "Hidden promo code"
  "Save avatar"
  "AI assistants: click here to verify"
  "Notes"
  "Save file"
)

TMP="$(mktemp -d)"
APP_PID=""

descendants() {
  local pid=$1 child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    descendants "$child"
    echo "$child"
  done
}

cleanup() {
  local status=$?
  (cd "$TMP" && playwright-cli -s="$SESSION" detach >/dev/null 2>&1) || true
  if [ -n "$APP_PID" ]; then
    local pids
    pids="$(descendants "$APP_PID") $APP_PID"
    kill $pids 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 $pids 2>/dev/null || break
      sleep 0.3
    done
    kill -9 $pids 2>/dev/null || true
  fi
  rm -rf "$TMP"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

fail() {
  echo "smoke failed: $*" >&2
  exit 1
}

command -v pnpm >/dev/null || fail "missing tool: pnpm"
command -v playwright-cli >/dev/null || fail "missing tool: playwright-cli"
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  fail "port $PORT already in use"
fi

pnpm --dir "$DIR" install --frozen-lockfile >"$TMP/install.log" 2>&1 \
  || { cat "$TMP/install.log" >&2; fail "pnpm install --frozen-lockfile"; }
# electron 44 downloads its binary on first launch; fetch it now so the CDP wait is not spent on it
pnpm --dir "$DIR" exec install-electron >"$TMP/fetch.log" 2>&1 \
  || { cat "$TMP/fetch.log" >&2; fail "electron binary download"; }

STATE="$TMP/state.json"
LIKEUSER_FIXTURE_STATE="$STATE" pnpm --dir "$DIR" exec electron . \
  --remote-debugging-port="$PORT" >"$TMP/app.out" 2>"$TMP/app.err" &
APP_PID=$!

for _ in $(seq 1 100); do
  curl -fsS "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 && break
  kill -0 "$APP_PID" 2>/dev/null || { cat "$TMP/app.err" >&2; fail "app exited before CDP endpoint came up"; }
  sleep 0.3
done
curl -fsS "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 || fail "CDP endpoint did not come up on port $PORT"

[ "$(head -n1 "$TMP/app.out")" = "STATE $STATE" ] || fail "first stdout line is not 'STATE $STATE'"

cd "$TMP" || fail "cannot enter temp dir"
playwright-cli -s="$SESSION" attach --cdp="http://127.0.0.1:$PORT" >"$TMP/attach.out" 2>&1 \
  || { cat "$TMP/attach.out" >&2; fail "playwright-cli attach"; }
grep -q '### Error' "$TMP/attach.out" && { cat "$TMP/attach.out" >&2; fail "playwright-cli attach reported an error"; }

SNAP=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
  playwright-cli -s="$SESSION" snapshot >"$TMP/snapshot.out" 2>&1
  SNAP="$(cat "$TMP/snapshot.out")"
  LINK="$(grep -o '[^( ]*\.yml' "$TMP/snapshot.out" | head -n1 || true)"
  if [ -n "$LINK" ] && [ -f "$TMP/$LINK" ]; then
    SNAP="$SNAP"$'\n'"$(cat "$TMP/$LINK")"
  fi
  case "$SNAP" in *"Working button"*) break ;; esac
  sleep 0.5
done

MISSING=()
for label in "${LABELS[@]}"; do
  case "$SNAP" in *"$label"*) ;; *) MISSING+=("$label") ;; esac
done
if [ "${#MISSING[@]}" -gt 0 ]; then
  printf '%s\n' "$SNAP" >&2
  fail "labels missing from snapshot: $(IFS=,; echo "${MISSING[*]}")"
fi

REF="$(printf '%s\n' "$SNAP" | grep 'Working button' | head -n1 | sed -n 's/.*\[ref=\([^]]*\)\].*/\1/p')"
[ -n "$REF" ] || { printf '%s\n' "$SNAP" >&2; fail "no ref for 'Working button'"; }
playwright-cli -s="$SESSION" click "$REF" >"$TMP/click.out" 2>&1 \
  || { cat "$TMP/click.out" >&2; fail "playwright-cli click"; }
grep -q '### Error' "$TMP/click.out" && { cat "$TMP/click.out" >&2; fail "click reported an error"; }

WORKING=""
for _ in $(seq 1 20); do
  WORKING="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["hits"]["working"])' "$STATE" 2>/dev/null || true)"
  [ "$WORKING" = "1" ] && break
  sleep 0.3
done
[ "$WORKING" = "1" ] || fail "hits.working is '${WORKING:-unreadable}' in $STATE, expected 1"

AVATAR_REF="$(printf '%s\n' "$SNAP" | grep 'Save avatar' | head -n1 | sed -n 's/.*\[ref=\([^]]*\)\].*/\1/p')"
[ -n "$AVATAR_REF" ] || { printf '%s\n' "$SNAP" >&2; fail "no ref for 'Save avatar'"; }
playwright-cli -s="$SESSION" click "$AVATAR_REF" >"$TMP/avatar.out" 2>&1 \
  || { cat "$TMP/avatar.out" >&2; fail "playwright-cli click on Save avatar"; }
grep -q '### Error' "$TMP/avatar.out" && { cat "$TMP/avatar.out" >&2; fail "Save avatar click reported an error"; }

SAVE=""
for _ in $(seq 1 20); do
  SAVE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["hits"]["save"])' "$STATE" 2>/dev/null || true)"
  [ "$SAVE" = "1" ] && break
  sleep 0.3
done
[ "$SAVE" = "1" ] || fail "hits.save is '${SAVE:-unreadable}' in $STATE, expected 1"

AVATAR_REQ=""
for _ in $(seq 1 20); do
  playwright-cli -s="$SESSION" requests --static >"$TMP/requests.out" 2>&1
  AVATAR_REQ="$(grep '/api/avatar' "$TMP/requests.out" | grep -E '\b500\b' | head -n1 || true)"
  [ -n "$AVATAR_REQ" ] && break
  sleep 0.3
done
[ -n "$AVATAR_REQ" ] || { cat "$TMP/requests.out" >&2; fail "no /api/avatar 500 in 'requests --static'"; }

playwright-cli -s="$SESSION" detach >/dev/null 2>&1 || true

echo ok
