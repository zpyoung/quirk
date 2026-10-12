<!-- generated from logic.json by render_spec.py — do not edit -->

# Local archive workflow

## Status & amendments

**Status:** Stage 1 approved

**Amendments:**
none

## Purpose

Describe a small, local-first archive workflow.

## Conceptual model

An archive groups selected source files with a compact index.

## Data flow

The reviewer chooses sources, then the tool writes the archive and index.

## Behavior & scenarios

### Archiving writes a portable index.

1. **SC-01**
   - **Given** The user has selected readable files.
   - **When** They create an archive.
   - **Then** An archive and compact index are written locally.
   - The index makes the result inspectable without the application.

2. **SC-02**
   - **Given** A source file becomes unreadable after selection.
   - **When** The archive is written.
   - **Then** The archive completes and reports the unreadable file by name.
   - Partial failures should not silently drop content.

3. **SC-03**
   - **Given** The user archives a large selection.
   - **When** They choose the default settings.
   - **Then** An archive and index are written.
   - **Alternatives** Skip creating an index file.
   - The default keeps the index unless the reviewer says otherwise.

4. **SC-04**
   - **Given** The destination runs out of space mid-write.
   - **When** The archive is being written.
   - **Then** The write stops and the partial archive is removed.
   - A half-written archive is worse than no archive.

### Selecting sources is explicit.

1. **SC-05**
   - **Given** The user opens the source picker.
   - **When** They select files to archive.
   - **Then** Only explicitly selected files are archived.
   - Selection stays explicit and reviewable before writing begins.

## Constraints

| ID | Kind | Text | Ruling |
|---|---|---|---|
| CON-01 | placement | Archive output goes beside the selected source directory. | approved |
| CON-02 | naming | Index entries always use forward slashes for paths, even on Windows. | rewritten |
| CON-03 | non-goal | Remote synchronization of archives is out of scope. | approved |
| CON-04 | verification | A destination permission check runs before writing begins. | approved |

## Requirements

### In scope

| ID | Area | Requirement | Summary | Detail | Group | Derived from |
|---|---|---|---|---|---|---|
| REQ-01 | Archive | Write a compressed archive of the selected files. | Create a portable archive. | Preserve relative paths so the archive is portable across machines. | min | SC-01, SC-03 |
| REQ-02 | Archive | Report unreadable source files by name instead of failing the whole archive. | Report unreadable sources. | A destination permission check runs first, then per-file read failures are reported by name. | i3 | SC-02, CON-04 |
| REQ-04 | Selection | Archive only the files the user explicitly selected. | Selection stays explicit. | The archive never includes a file the reviewer did not pick, and output is written beside the source directory. | min | SC-05, CON-01 |
| REQ-05 | Archive | Use forward slashes for index paths, even on Windows. | Normalize index path separators. | A single separator style keeps the index portable across platforms. | i3 | CON-02 |

### Conditionally in scope

| ID | Area | Condition | Requirement | Summary | Detail | Group | Derived from |
|---|---|---|---|---|---|---|---|
| REQ-03 | Archive | under-10 | Remove a partial archive when the destination runs out of space mid-write. | Clean up failed writes. | A half-written archive is removed rather than left behind for the reviewer to find. | i2 | SC-04 |

### Out of scope

| ID | Area | Requirement | Summary | Detail | Group | Derived from |
|---|---|---|---|---|---|---|
| OOS-01 | Sync | Synchronize archives to a remote service. | No remote sync. | Remote synchronization would need accounts and conflict handling, which is out of scope. | i1 | CON-03 |

## Assumptions & blind spots

### Assumptions

- **ASM-01 — Selected inputs are readable when writing starts.** (assumed)
  - Basis: The workflow selects files before creating the archive.
  - If wrong: Unreadable sources need a clear per-file error.
  - Affects: SC-01, CON-04
  - Meaning: The tool can open every selected source file.
  - Check: Try a source that becomes unreadable after selection. (cost: Low)
  - Reviewer ruling: build-on — Confirmed elsewhere; no additional check needed.

### Blind spots

- **BS-01 — Filesystem permissions**
  - The destination may not be writable even when sources are readable.
  - Sources: SC-01
  - Resolved by: CON-04
- **BS-02 — Partial writes on interruption**
  - An interrupted write can leave a corrupt archive behind.
  - Sources: SC-04
  - Reviewer acceptance: Atomic rename mitigates this; accepted without a resolving item.
  - **Research finding (2026-09-21T10:30:00Z)** Writing to a temporary file and renaming into place avoids partial archives. — A rename is atomic on the same filesystem, so an interrupted write never leaves a corrupt destination file.

## Decisions Locked

### Storage

- The archive is written beside the selected source directory.


## Industry Insights

- A portable index reduces dependence on one viewer. — https://example.test/portable-index

## Scope & non-goals

- Remote synchronization is not part of this change.

## Deferred Ideas

- [tech-spec] Add archive signing after the local format stabilizes.

## Glossary

| Term | Definition |
|---|---|
| Index | A compact listing of archive contents. |
