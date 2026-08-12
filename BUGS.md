<!-- schema-version: 1 -->
<!-- BUGS.md SCHEMA (append only — do not rewrite existing entries)
Entry format:
## BUG-[N]: [Short title]
- **Observed**: [date or session ID]
- **File**: [path/to/file.ts:line]
- **Description**: [what the bug is]
- **Introduced by**: [this session / unknown / commit SHA]
- **Severity**: [critical / high / medium / low]
- **Proposed fix**: [one sentence]
- **Blocker for**: [what this would break]

Required fields: title, file, description, severity.
-->

# BUGS

Bugs noticed during sessions but not fixed in the current scope.

Reviewed every PR. Use `/quirk:artifacts:bug` to append. Do not edit older
entries' IDs; manual edits to fix typos are fine.

## BUG-1: Artifact lock files are not gitignored
- **Observed**: 2026-08-06
- **File**: .gitignore:6
- **Description**: artifact_append.py creates .<ARTIFACT>.lock beside each artifact file (bin/artifact_append.py:165), but .gitignore's '.lock' entry matches only a file literally named .lock, not .BUGS.md.lock. Verified: git check-ignore -v .BUGS.md.lock exits 1. artifact_init.py adds no ignore entry either, so every project adopting typed-artifacts accumulates untracked lock files in its root.
- **Introduced by**: pre-dates this session
- **Severity**: low
- **Proposed fix**: Add a '.*.lock' pattern to the templates and have artifact_init.py append it to the target project's .gitignore.
- **Resolved**: 2026-08-07. Fixed differently than proposed: locks moved to .quirk/locks/ which carries its own .gitignore of '*', so no project's root .gitignore is edited and projects that adopted artifacts earlier self-heal on their next append. artifact_init.py also removes legacy root locks. Phase 1 has no Status field, so --index still counts this entry open; see DEFER-1.

## BUG-2: artifact_append.py writes non-atomically while pm.py writes atomically
- **Observed**: 2026-08-06
- **File**: bin/artifact_append.py:175
- **Description**: The append path uses a plain target.write_text(new_text), so a crash mid-write truncates the ledger. bin/pm.py's writers use an atomic temp-file-plus-os.replace helper. Both mutate the same files, so one ledger now has two different crash-safety properties depending on which script touched it last.
- **Introduced by**: pre-dates this session; the asymmetry is new as of the pm.py work
- **Severity**: medium
- **Proposed fix**: Backport the atomic write helper to artifact_append.py.
- **Blocker for**: any claim that the ledger survives a crash mid-append

## BUG-3: Skill(quirk:adversarial-review) returns the command wrapper instead of loading its protocol
- **Observed**: 2026-08-06
- **File**: skills/adversarial-review/SKILL.md
- **Description**: Invoking the skill from a fresh session returns the routing text of commands/adversarial-review.md ('This command only routes to it - do not restate its rules here') rather than SKILL.md's protocol. A second invocation reports the instructions as 'previously loaded' while they are absent from context. subagent-driven-development Step 8 delegates its entire review gate to this skill, so the documented delegation seam does not work as written; the mechanical layer at scripts/adversarial-review had to be driven directly for all five review rounds of this branch.
- **Introduced by**: pre-dates this session
- **Severity**: high
- **Proposed fix**: Reproduce a Skill invocation from a clean session and fix whichever of the command file or the skill resolution is shadowing SKILL.md.
- **Blocker for**: subagent-driven-development's review gate being usable as documented

## BUG-4: artifact_append.py reads and writes with the platform-default encoding
- **Observed**: 2026-08-06
- **File**: bin/artifact_append.py:169
- **Description**: read_text()/write_text() are called with no encoding, so the ledger's on-disk encoding follows each host's locale. A file written on a latin-1 host is not readable as the same text on a utf-8 host. bin/pm.py had to couple its own decode order to this behaviour (platform codec first when that codec is not utf-8) to avoid silently misreading files quirk itself wrote. That coupling is a workaround; this is the root cause.
- **Introduced by**: pre-dates this session
- **Severity**: medium
- **Proposed fix**: Pin encoding='utf-8' on both calls, with a one-time migration for any ledger written under a non-utf-8 locale.

## BUG-5: MemoryError escapes _read_and_parse's OSError guard
- **Observed**: 2026-08-07
- **File**: bin/pm.py:115
- **Description**: data = f.read(max_bytes + 1) is wrapped in except OSError, but CPython pre-allocates the read buffer, so a large QUIRK_PM_MAX_FILE_BYTES (up to the permitted MAX_USABLE_FILE_BYTES of 1 GiB) can raise MemoryError, which is not an OSError. It escapes _read_and_parse and crashes pm.py, contradicting the module docstring's promise that one bad file never takes down the whole read layer. The SessionStart hook masks it as 'index unavailable'; --index/--next/--doctor run directly will traceback.
- **Introduced by**: the Phase 1 pm.py work on this branch
- **Severity**: low
- **Proposed fix**: Widen the guard to except (OSError, MemoryError).

## BUG-6: Every TEST_BACKLOG entry sorts as maximally old in --next
- **Observed**: 2026-08-07
- **File**: bin/pm.py:160
- **Description**: _age_sort_key returns the empty string whenever spec.date_field is None, and TEST_BACKLOG.md has no date field at all. The empty string precedes every ISO date lexically, so TEST entries outrank every same-priority BUG or DEFER entry permanently, regardless of real age. The 'missing date sorts oldest' rule is right for an absent value but wrong for a file that structurally has none. Visible in this repo: TEST-1 [P3] holds a top-5 slot.
- **Introduced by**: the Phase 1 pm.py work on this branch
- **Severity**: low
- **Proposed fix**: Sort date-less specs neutrally rather than oldest, or give TEST_BACKLOG a date field in schema v2.

## BUG-7: The index's doctor hint names a command no surface exposes
- **Observed**: 2026-08-07
- **File**: bin/pm.py:242
- **Description**: The index emits 'run pm.py --doctor for details', but no command, skill, hook, or README entry exposes pm.py, and no path is given - it lives at ${CLAUDE_PLUGIN_ROOT}/bin/pm.py. tech.md:1093 specifies this hint as /quirk:pm:status, which also does not exist. The one actionable line the index produces is not actionable.
- **Introduced by**: the Phase 1 pm.py work on this branch
- **Severity**: low
- **Proposed fix**: Either ship the slash command the hint names or make the hint carry a runnable absolute path.

## BUG-8: README still describes the removed SessionStart tail loading
- **Observed**: 2026-08-07
- **File**: README.md:46
- **Description**: README reads 'SessionStart loads tail of artifact files (or suggests /init if none exist)'. As of this branch the hook calls pm.py and emits an index counts line plus the --next shortlist; it has not loaded file tails since. The parenthetical also names /init rather than the actual /quirk:artifacts:init.
- **Introduced by**: the Phase 1 pm.py work on this branch
- **Severity**: low
- **Proposed fix**: Rewrite the bullet to describe the index-plus-shortlist output and correct the command name.

## BUG-9: artifact_append.py opens its lock file with mode 'w', truncating through a symlink
- **Observed**: 2026-08-10
- **File**: bin/artifact_append.py:145
- **Description**: The lock is acquired with open(lock_path, 'w'), which truncates the target and follows symlinks. .quirk/locks/ lives inside the project, so a symlink planted at .quirk/locks/BUGS.md.lock is truncated to zero bytes the moment any append runs — before the flock is even attempted. A lock file's contents are never read; only its existence and its flock matter, so the write mode buys nothing. pm.py's own lock acquisition was fixed to os.open(..., O_CREAT|O_RDWR|O_NOFOLLOW, 0o600) during Phase 2; this is the same pattern left in the older script. Not an authorization hole — the design assumes a cooperative worker and states it is not a security boundary — but it destroys a file for no benefit.
- **Introduced by**: pre-dates this session
- **Severity**: medium
- **Proposed fix**: Mirror pm.py's _acquire_ledger_lock: os.open with O_CREAT|O_RDWR|O_NOFOLLOW and no truncation. Ideally hoist the shared acquisition into artifact_lib so the two cannot drift again.
- **Blocker for**: nothing — but the two scripts now have different lock-safety properties for the same lock files

## BUG-10: parse_entries reads field values from the fence-masked text, silently blanking any HTML comment or fenced span inside a field value
- **Observed**: 2026-08-12
- **File**: bin/artifact_lib.py:140-145
- **Description**: parse_entries builds each entry's fields dict from masked_block (the fence/comment-masked copy) rather than the original block, so any field VALUE containing an HTML comment or a fenced span is stored with that span replaced by spaces. Reproduced: a Description of 'fails when the tag <!-- keep --> is present' parses as 'fails when the tag               is present', and a Probe of 'grep:<!-- TODO -->' parses as 'grep:' plus 14 spaces. The masking is correct for locating headings and field LABELS (that is what it was added for, commit 264c9fe); applying it to the captured VALUE is the defect. Blast radius is every consumer of Entry.fields, including artifact_append.py and artifact_review.py. The probe-specific consequence is the sharpest: a grep probe whose pattern contains a comment re-runs at finish as a blanked pattern, matches nothing, and delivers the entry while the symptom it tracked is still present.
- **Introduced by**: 264c9fe, which pre-dates the pm-agent Phase 2 branch
- **Severity**: high
- **Proposed fix**: Capture field values by offset from the original block using positions found in the masked block, rather than storing the masked capture. Add a round-trip fixture for a field value containing an HTML comment and one containing a fenced span.

## BUG-11: artifact_init --force follows a symlinked ledger and overwrites the external target, destroying data outside the project
- **Observed**: 2026-08-12
- **File**: bin/artifact_init.py:40-50
- **Description**: The --force path calls shutil.copy(src, dst) with dst a plain path, and shutil.copy follows symlinks, so a ledger that is a symlink has its TARGET overwritten with the template. The backup taken first is also copied through the link, so it preserves the target's content under a .bak name inside the project but the original external file is still destroyed in place. Reproduced for both ROADMAP.md and BUGS.md: create proj/BUGS.md as a symlink to ../outside.md containing 'PRECIOUS BUGS CONTENT', run artifact_init --project-dir proj --force, and outside.md now contains the BUGS.md template. This affects every entry in ROOT_TEMPLATES, so it pre-dates the pm-agent branch; that branch added ROADMAP.md to the list, which widens the blast radius by one file but is not the cause. Third member of a family: pm.py's atomic_write now refuses a symlinked ledger, BUG-9 covers artifact_append.py's lock file, and this is the init path.
- **Introduced by**: pre-dates the pm-agent Phase 2 branch; ROADMAP.md was added to ROOT_TEMPLATES by fc79a92 on it
- **Severity**: critical
- **Proposed fix**: Refuse when the destination is a symlink, matching the mistake-catcher refusal pm.py's atomic_write already implements, or open the destination with O_NOFOLLOW. Whichever is chosen should be applied uniformly across the three paths so a fourth does not drift.

