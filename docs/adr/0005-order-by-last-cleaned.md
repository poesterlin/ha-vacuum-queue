# ADR-0005: Queue order is last-cleaned (LRU)

Status: accepted

## Context
The original script was named `start_vacuuming_in_order` with a hand-maintained
order. A fixed configured order rots as cleaning needs change.

## Decision
Rooms are cleaned least-recently-completed first. Completion timestamps are
recorded when the vacuum leaves a room for another (tracker transition) or when
it is skipped, and are persisted via the Store. Ties break by configuration
order; never-cleaned rooms sort before all cleaned ones.

## Consequences
No ordering UI to maintain; behavior adapts itself. Ordering is only applied at
send time, so resends re-sort automatically.
