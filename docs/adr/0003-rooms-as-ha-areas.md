# ADR-0003: Rooms are Home Assistant areas

Status: accepted

## Context
Roborock segment IDs are device-specific numbers that users should never have to
manage. Modern HA resolves area→segment mappings internally for vacuums.

## Decision
A room is identified by its HA **area ID** everywhere (config, switches,
ordering). Cleaning is requested via the `vacuum.clean_area` action with area
IDs. As a fallback when that action fails, raw `app_segment_clean` may be sent
using optional per-room segment IDs from configuration; without them the fallback
errors out loudly.

## Consequences
No segment bookkeeping in normal use; multi-brand support comes free through the
area abstraction at the cost of one optional legacy field per room.
