# ADR-0008: Home flush policy

Status: accepted

## Context
Which vacuum states should wipe the queue? Original automations flushed on
`returning_to_dock` and `charging`.

## Decision
Flush (turn all room switches off) on any *transition into* `returning`,
`docked` or `charging`. Transitions, not states: re-reports of an unchanged
state never flush. `error`, `stopped`, `paused`, `idle` and unknown activities
keep the queue so a run can be resumed. Flushing is skipped when nothing is
switched on.

## Consequences
Matches the old mental model exactly. Pre-arming switches while docked is safe
(no transition occurs). If the vacuum completes a *vendor-app* run and docks,
pre-armed switches are wiped — identical to the previous automations.
