#!/usr/bin/env bash
# Builds the native fixture into <dir>/UALAFixture.app and prints the .app path as the last line.
# Usage: build.sh [output-dir]   (default: a fresh temp dir)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${1:-$(mktemp -d "${TMPDIR:-/tmp}/uala-fixture.XXXXXX")}"
mkdir -p "$out"
app="$out/UALAFixture.app"

rm -rf "$app"
mkdir -p "$app/Contents/MacOS"

cat > "$app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>UALAFixture</string>
  <key>CFBundleIdentifier</key><string>dev.quirk.uala.fixture</string>
  <key>CFBundleName</key><string>UALAFixture</string>
  <key>CFBundleDisplayName</key><string>UALA Fixture</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSPrincipalClass</key><string>NSApplication</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

swiftc -parse-as-library -O -o "$app/Contents/MacOS/UALAFixture" "$here/FixtureApp.swift" >&2
codesign --force --sign - "$app" >&2 2>/dev/null || true

echo "$app"
