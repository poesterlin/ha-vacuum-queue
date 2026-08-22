# Vacuum Queue

Vacuum Queue maintains one cleaning queue per vacuum. Select Home Assistant areas, map
the raw values from a current-room tracker, and arm rooms with the generated
switches.

The queue is started explicitly with the **Start** button or
`vacuum_queue.start`. Rooms are ordered by least-recently-cleaned time, with
configuration order breaking ties. The current room is allowed to finish
before a changed queue is sent to the vacuum. The **Skip** button pauses the
vacuum, marks the current room complete, and continues with the remaining
rooms.

The integration flushes all room switches when the vacuum transitions to
returning, docked, or charging. Queue state and last-cleaned timestamps are
persisted across Home Assistant restarts.

## Setup

1. Add **Vacuum Queue** from Settings → Devices & services.
2. Select a vacuum, its current-room sensor, and the Home Assistant areas to
   clean.
3. For each room, enter the tracker state values that identify it. Values are
   case-insensitive. Segment IDs are optional and provide a fallback for
   vacuums that do not support `vacuum.clean_area`.
4. Turn on the room switches and press **Start**.

This integration replaces scripts and automations that separately start the
vacuum, skip rooms, or reset room helpers.
