#!/usr/bin/env bash
# Regenerate the astryx token block that assets/report.html inlines.
#
# The report is a single self-contained file opened from file://, so the tokens
# cannot be a <link>. This prints the block to stdout; paste it between the
# BEGIN/END astryx-tokens markers in assets/report.html.
#
#   scripts/vendor_astryx_tokens.sh ~/path/to/node_modules > /tmp/tokens.css
set -euo pipefail

MODULES="${1:?usage: vendor_astryx_tokens.sh <path-to-node_modules>}"
THEME="$MODULES/@astryxdesign/theme-neutral/dist/theme.css"
CORE="$MODULES/@astryxdesign/core/dist/astryx.css"

for file in "$THEME" "$CORE"; do
    [ -r "$file" ] || { echo "missing: $file" >&2; exit 1; }
done

version() { node -p "require('$MODULES/@astryxdesign/$1/package.json').version"; }

# Build the whole block first so a failed extraction never leaves a half-written one on stdout.
extract() {
    local label="$1" out
    shift
    out="$("$@")" || true
    [ -n "$out" ] || { echo "vendor_astryx_tokens: no $label found in $CORE" >&2; exit 1; }
    printf '%s\n' "$out"
}

THEME_VERSION="$(version theme-neutral)"
CORE_VERSION="$(version core)"
[ -n "$THEME_VERSION" ] && [ -n "$CORE_VERSION" ] || { echo "vendor_astryx_tokens: could not read package versions" >&2; exit 1; }

SPACING="$(extract "--spacing tokens" grep -oE -- '--spacing-[0-9-]+:[^;]*;' "$CORE" | sort -u -t: -k1,1V | sed 's/^/  /')"
WEIGHT="$(extract "--font-weight tokens" grep -oE -- '--font-weight-[a-z]+:[^;]*;' "$CORE" | sort -u | sed 's/^/  /')"
SIZE="$(extract "--size-element tokens" grep -oE -- '--size-element-[a-z0-9]+:[^;]*;' "$CORE" | sort -u | sed 's/^/  /')"

# theme.css opens with a generated banner of varying length; the first @layer starts the real content.
THEME_BODY="$(awk '/^@layer /{found=1} found' "$THEME")"
[ -n "$THEME_BODY" ] || { echo "vendor_astryx_tokens: no @layer found in $THEME" >&2; exit 1; }

cat <<HEADER
/* astryx design tokens — vendored verbatim, do not hand-edit.
 * theme:  @astryxdesign/theme-neutral@$THEME_VERSION  dist/theme.css
 * base:   @astryxdesign/core@$CORE_VERSION           dist/astryx.css (:root scale tokens only)
 * refresh: scripts/vendor_astryx_tokens.sh <path-to-node_modules>
 * license: MIT, https://github.com/facebook/astryx
 */
HEADER

# The scale tokens theme.css references but does not define: they live on :root
# in core's StyleX output, mixed in with atomic classes we do not want.
echo '@layer astryx-base {'
echo ':root {'
printf '%s\n%s\n%s\n' "$SPACING" "$WEIGHT" "$SIZE"
echo '}'
echo '}'
echo
printf '%s\n' "$THEME_BODY"
