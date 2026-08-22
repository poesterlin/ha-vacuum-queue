# Vacuum Queue

Vacuum Queue maintains one cleaning queue per vacuum. Select Home Assistant areas, map
the raw values from a current-room tracker, and arm rooms with the generated
switches.

You start the queue with the **Start** button or `vacuum_queue.start`. The
queue orders rooms by least-recently-cleaned time. Configuration order breaks
ties. The mapped current room finishes before the changed queue goes to the vacuum.
The **Skip** button pauses the vacuum, marks the current room complete, and
continues with the remaining rooms.

The integration flushes all room switches when the vacuum transitions to
returning, docked, or charging. Queue state and last-cleaned timestamps persist
across Home Assistant restarts.

## Setup

1. Add **Vacuum Queue** from Settings → Devices & services.
2. Select a vacuum, its current-room sensor, and the Home Assistant areas to
   clean.
3. For each room, enter the tracker state values that identify it. Values are
   not case-sensitive. Segment IDs are optional and provide a fallback for
   vacuums that do not support `vacuum.clean_area`.
4. Turn on the room switches and press **Start**.

This integration replaces scripts and automations that separately start the
vacuum, skip rooms, or reset room helpers.

## Install with HACS

This repository is not in the default HACS catalog. Add it as a custom
repository:

1. Open HACS and select the three-dot menu.
2. Select **Custom repositories**.
3. Enter `https://github.com/poesterlin/ha-vacuum-queue`.
4. Select **Integration** as the repository type, then select **Add**.
5. Download **Vacuum Queue**, restart Home Assistant, and add it from
   **Settings → Devices & services**.

## Dashboard card

The integration includes a custom Lovelace card that automatically discovers
the room switches and action buttons. Add the following resource once in
Settings → Dashboards → Resources:

```yaml
url: /api/vacuum_queue/static/vacuum-queue-card.js
type: module
```

Then add one card to the dashboard:

```yaml
type: custom:vacuum-queue-card
show_return_home: false
labels:
  rooms: Räume
  actions: Aktionen
  start: James starten
  skip: Raum überspringen
  no_current_room: Kein aktueller Raum
```

If one Vacuum Queue device exists, the card finds it automatically. With
multiple queues, set `device_id` to the Vacuum Queue device ID.
