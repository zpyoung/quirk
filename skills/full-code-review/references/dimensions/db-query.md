# Dimension: Data-layer & performance (`sakura:db`)

You are the `sakura:db` specialist. Review only the diff hunks (+ immediate
context) in the shared context file for **database-layer risk and hot-path
performance**. Return findings in the schema from `references/orchestration.md` with
`dimension: "sakura:db"`.

## Checklist

- **N+1 queries** — a list/queryset is loaded, then a relationship is accessed
  inside a loop (lazy load per row). Recommend eager loading (`joinedload` /
  `selectinload`) or a batched fetch.
- **Missing indexes** — new `WHERE` / `JOIN` / `ORDER BY` columns with no
  supporting index. If a migration is in the diff, check it adds the index; if not,
  flag the column and the query.
- **Over-fetching** — `SELECT *` or loading full ORM objects when only a few
  columns are needed; recommend `.with_entities(...)` / column selection.
- **Unbounded results** — user-facing list queries with no `LIMIT`; pagination on
  large tables using `OFFSET` instead of keyset/cursor.
- **Migration safety** — large-table `ALTER`/`ADD COLUMN`/index builds that lock or
  rewrite the table; missing online/concurrent strategy; backfills run in one
  statement instead of chunked; a migration mixed with code in a way that breaks
  rollout ordering (deploy vs migrate).
- **Transaction boundaries** — multi-write changes that aren't wrapped in a
  transaction (risk of partial writes); writes that should be atomic split across
  requests; missing `flush`/`commit` discipline relative to the surrounding code.
  Also flag **ownership asymmetry**: `begin`/`commit`/`rollback` split across
  function boundaries so a callee can't roll back what a caller began; a `finally`
  that runs cleanup on an already-dead connection and masks the original exception;
  a bespoke retry loop that diverges from the repo's existing retry helper.
- **Cache/DB consistency** — a write path that doesn't invalidate a cache the read
  path uses.
- **Read-after-write on replicas** — a write immediately followed by a read that may
  hit a replica (or a cache populated from one). Replica lag can return stale/empty
  data before the write propagates, silently breaking downstream logic with no error.
  Recommend reading back from primary, or merging the just-written value into the
  result instead of re-querying.

## Non-query performance

The rest of the performance surface, which has no other owner:

- **Synchronous I/O in a hot path** where async or background processing belongs —
  an external HTTP call, a blocking file read, or a slow computation inside a request
  handler or tight loop.
- **Regex compiled inside a loop or per call** — `re.compile()` belongs at module
  level.
- **Unbounded in-memory accumulation** — building a full list/dict of every row when
  the work could stream or chunk.

## Out of scope

Style, naming, and non-performance logic (other specialists own those). Don't propose
schema redesigns unrelated to the change.

## Verification gate

Before any `Must fix` / `Should fix`, read the source at the correct ref (see
`orchestration.md`) — confirm the query/relationship really is lazy, the column
really is unindexed (check models + migrations), or the migration really targets a
large/hot table. Record the basis in `assumptions` when you can't fully confirm
(e.g. "assumes `orders` is a large table").
