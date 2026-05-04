# 0000. Record architecture decisions

- **Status:** accepted
- **Date:** 2026-05-04

## Context

This project benefits from recording the architectural decisions made
during its lifecycle, in a way that preserves the *why* alongside the
*what*. Memory and chat logs are unreliable; documents are durable.

## Decision

Use Architecture Decision Records (ADRs) as described by Michael Nygard
to capture significant decisions. Each ADR lives in `docs/adr/` as a
file named `NNNN-kebab-title.md`. Numbers are sequential. Once an ADR
is accepted it is immutable except for status transitions
(accepted → superseded by NNNN, etc.).

Use `/quirk:artifacts:adr "title"` to create a new ADR. Status starts
at `proposed` and is promoted by editing the file.

## Consequences

Positive — durable rationale; new contributors can read history; reviews
have a structured place to land.

Negative — small overhead per decision; risk of ADRs going stale if not
linked to status reviews.

Neutral — number space is sequential and gap-free; renumbering is a
breaking change to references.
