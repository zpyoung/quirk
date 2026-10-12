<!-- generated from logic.json by render_spec.py — do not edit -->

# Local archive workflow

## Status & amendments

**Status:** Draft

**Amendments:**
- 2026-09-20 — Clarified that source selection is explicit.

## Purpose

Describe a small, local-first archive workflow.

## Conceptual model

An archive groups selected source files with a compact index.

## Data flow

The reviewer chooses sources, then the tool writes the archive and index.

## Behavior & scenarios

1. **SC-01**
   - **Given** The user has selected readable files.
   - **When** They create an archive.
   - **Then** An archive and compact index are written locally.
   - **Alternatives** Write a compact index.
   - The index makes the result inspectable without the application.
   - **Requirements** REQ-01, REQ-02

## Requirements

### In scope

| ID | Area | Requirement | Summary | Detail | Group | Provenance |
|---|---|---|---|---|---|---|
| REQ-01 | Archive | Write a compressed archive of selected files. | Create a portable archive. | Preserve relative paths and report files that cannot be read. | min | claude |
| REQ-02 | Selection | Let the user choose the source files before archiving. | Select archive inputs. | Selection is explicit and can be changed until writing begins. | i3 | you-chose |

### Conditionally in scope

| ID | Area | Condition | Requirement | Summary | Detail | Group | Provenance |
|---|---|---|---|---|---|---|---|
| REQ-03 | Compression | under-30 | Support a lower-compression setting for large inputs. | Allow faster compression. | The setting trades smaller output for faster completion. | i2 | you-recommended |

### Out of scope

| ID | Area | Requirement | Summary | Detail | Group | Provenance |
|---|---|---|---|---|---|---|
| OOS-01 | Sync | Synchronize archives to a remote service. | Upload archives. | The service would need accounts and conflict handling. | i1 | you-chose |

## Assumptions & blind spots

### Assumptions

- **ASM-01 — Selected inputs are readable when writing starts.** (assumed)
  - Basis: The workflow selects files before creating the archive.
  - If wrong: Unreadable sources need a clear per-file error.
  - Affects: REQ-01
  - Meaning: The tool can open every selected source file.
  - Check: Try a source that becomes unreadable after selection. (cost: Low)

### Blind spots

- **BS-01 — Filesystem permissions**
  - The destination may not be writable even when sources are readable.
  - Sources: REQ-01
  - Resolved by: REQ-03
  - **Research finding (2026-09-21T10:30:00Z)** The destination permission check can be performed before writing. — A preflight check catches common read-only destinations, though permissions can still change before the write.

## Decisions Locked

### Storage

- The archive is written beside the selected source directory.

### Review

- The index remains readable without the application.


## Industry Insights

- A portable index reduces dependence on one viewer. — https://example.test/portable-index

## Scope & non-goals

- Remote synchronization is not part of this change.

## Deferred Ideas

- [tech-spec] Add archive signing after the local format stabilizes.
- Offer a graphical progress indicator.

## Glossary

| Term | Definition |
|---|---|
| Index | A compact listing of archive contents. |
