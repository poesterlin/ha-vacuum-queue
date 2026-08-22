# ADR-0009: Persist queue state across restarts

Status: accepted

## Context
HA restarts mid-run must not lose the queue or the LRU history.

## Decision
Last-cleaned timestamps and switch states persist through HA's `Store` API
(debounced writes). On restart the coordinator restores them and treats the run
as inactive; the unconditional home-flush (ADR-0008) still cleans up whenever the
vacuum next docks.

## Consequences
Restarts are invisible to the user; worst case after a restart mid-run is that
start must be pressed again to continue remaining rooms.
