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

cat <<HEADER
/* astryx design tokens — vendored verbatim, do not hand-edit.
 * theme:  @astryxdesign/theme-neutral@$(version theme-neutral)  dist/theme.css
 * base:   @astryxdesign/core@$(version core)           dist/astryx.css (:root scale tokens only)
 * refresh: scripts/vendor_astryx_tokens.sh <path-to-node_modules>
 * license: MIT, https://github.com/facebook/astryx
 */
HEADER

# The scale tokens theme.css references but does not define: they live on :root
# in core's StyleX output, mixed in with atomic classes we do not want.
echo '@layer astryx-base {'
echo ':root {'
grep -oE -- '--spacing-[0-9-]+:[^;]*;' "$CORE" | sort -u -t: -k1,1V | sed 's/^/  /'
grep -oE -- '--font-weight-[a-z]+:[^;]*;' "$CORE" | sort -u | sed 's/^/  /'
grep -oE -- '--size-element-[a-z0-9]+:[^;]*;' "$CORE" | sort -u | sed 's/^/  /'
echo '}'
echo '}'

# Drop theme.css's own @generated banner; the header above supersedes it.
tail -n +8 "$THEME"
