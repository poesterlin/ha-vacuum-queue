# Glossary

Shared vocabulary for Vacuum Queue. Design terms follow the codebase-design skill
(module, interface, seam, adapter); domain terms describe the vacuum-cleaning model.

## Domain terms

**Room** — one cleanable unit of the floor plan. Always backed by a Home Assistant
**Area ID** (see ADR-0003). The integration never sees segment numbers unless used
as a fallback command payload.

**Match value** — one raw state string that the tracker sensor can report for a room
(e.g. `bad`, `klo`, `küche`). Lowercased before matching. Several match values may
map to the same room.

**Room map** — configured dictionary `match value → area ID`. The user maintains it
manually in the config/options flow (ADR-0004).

**Tracker** — any sensor whose state reports where the vacuum currently is
(e.g. `sensor.roborock_..._current_room`). Resolved to a room via the room map;
unmapped or unavailable states are ignored.

**Queue** — the set of rooms whose switch is on and that have not been cleaned in
the current run. Materialized as `switches_on − done_this_run − {current room}`.

**Run** — one cleaning episode driven (or at least observed) by the integration,
from an explicit start until the flush on arrival home.

**Last-cleaned order** — queue ordering rule: least recently completed first, ties
broken by configuration order (ADR-0005).

**Resend** — issuing `clean_area` again with the remaining queue after a queue
mutation while cleaning, so mid-run edits take effect before the next segment
(ADR-0007). A replacement waits until the mapped current room finishes; it is
only issued while the vacuum is actively cleaning.

**Skip** — pause, mark the current room cleaned, turn its switch off, resend the
remaining queue; return home if nothing remains (ADR-0001 semantics preserved
from the original script).

**Flush** — turning every room switch off because the vacuum came home. Triggered
by a *transition* into `returning`, `docked` or `charging` (ADR-0008).
Error/paused/stopped never flush.

## Design terms

**Coordinator** (`VacuumQueueCoordinator`) — the deep module: queue state machine,
ordering, resend debounce, flush policy, persistence. Everything behavioral lives
here behind a small interface (`async_start`, `async_skip`, `async_return_home`,
`handle_room_switch`, plus internal event handlers). One per config entry/vacuum.

**Interface of the coordinator** — everything a caller must know: the four methods
above, the invariant that switches mirror `switches_on`, and that all mutations go
through the coordinator (never write its sets directly).

**Seam** — between platform/service callers and the coordinator. Switch entities,
buttons, and services are thin adapters at this seam; they contain no logic.

**Adapter** — concrete seam filler: `switch.py` (one switch per room),
`button.py` (Start / Skip / Return home), service handlers in `__init__.py`.

**Store** — persistence adapter (`store.py`) over HA's `Store` API holding
last-cleaned timestamps and switch states across restarts.
