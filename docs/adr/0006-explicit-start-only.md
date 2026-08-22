# ADR-0006: Explicit start only

Status: accepted

## Context
Should flipping a room switch while docked immediately start cleaning?

## Decision
No. Switches mark intent only; a run begins via the explicit **Start** button or
`vacuum_queue.start` service. Skip and Return home are likewise explicit
(buttons/services).

## Consequences
No accidental 3 a.m. cleanings from dashboard fiddling; arming rooms while
docked is always safe. One extra press per run.
