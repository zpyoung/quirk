# Changelog

All notable changes to quirk are recorded here, newest first. Versions are
calendar-based (**CalVer**, `YYYY.M.D` unpadded); the `releasing-quirk` skill
stamps and appends each entry. Since the version no longer encodes
compatibility, breaking changes are called out in a `### ⚠️ BREAKING` subsection.

## 2026.7.9

### ⚠️ BREAKING
- **Versioning switched from semver to CalVer.** Releases are now stamped with the
  day they ship (`YYYY.M.D`, e.g. `2026.7.9`); a 2nd+ release on the same day
  appends a micro (`2026.7.9.1`). This is a deliberate one-way door — earlier
  semver releases (`≤ 5.9.0`) still sort *before* every CalVer version because
  `2026 > 5`, so upgrades stay monotonic. quirk's own `version` field is an
  opaque string to Claude Code, so installs are unaffected; the only breakage is
  for anyone who pinned quirk via a semver-*range* dependency — replace such
  constraints with an exact/date-based pin.

### Changes
- Rewrote the `releasing-quirk` skill: the version is now derived from today's
  date (via `python3`, portable across macOS/BSD) with same-day micro
  resolution, rather than judged as a patch/minor/major bump from the diff.
- Releases are now fully autonomous — compute, sync the three version files,
  write the changelog, commit, and `git push origin main` with no confirmation
  gate. Test failures and non-fast-forward pushes still stop the process.
- Added this `CHANGELOG.md`; breaking changes are surfaced here now that the
  version no longer signals them.
