# ADR-0007: Resend remaining queue on change

Status: accepted

## Context
Segment cleaning commands take a room list up front. To honor switch flips while
the vacuum runs, someone must drive sequencing and re-issue the command when the
list changes.

## Decision
The coordinator drives sequencing by *resending*: after a queue mutation during
a run it issues `clean_area` with the remaining queue in last-cleaned order.
Resends are debounced (2 s) and only sent while the vacuum is actively
`cleaning`; edits made while paused take effect at resume/skip/start.

The coordinator must finish the mapped current room before replacing the device's
active command. Queue mutations while that room is in progress are marked
pending, and the remaining queue is sent after the tracker transitions away from
the current room. This prevents adding a room from interrupting a partly-cleaned
room. Removing the current room is the explicit exception: it uses skip semantics
(pause → mark done → resend). Natural progression between rooms does not resend
unless a mutation is pending.

## Consequences
Mid-run add/remove always wins before the next segment starts, at the cost of one
command per mutation. Removing the current room mid-run degrades gracefully into
skip semantics (pause → mark done → resend).
