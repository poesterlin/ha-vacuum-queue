# ADR-0002: Integration-owned switch entities instead of input_booleans

Status: accepted

## Context
The original design used manually created `input_boolean` helpers. Custom
integrations cannot create real `input_boolean` entities, and manual helper
creation contradicts "easy to configure".

## Decision
The integration exposes one `switch.*` entity per configured room. Switches are
auto-created/deleted with room configuration, grouped on a per-vacuum device,
and are the sole user-facing representation of the queue.

## Consequences
Old dashboards referencing `input_boolean.clean_*` must be re-pointed. In
exchange there is zero helper setup and no drift between rooms and helpers.
