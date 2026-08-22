# ADR-0010: Derive the tracker map from the vacuum's segment configuration

Status: accepted

## Context
ADR-0004 made users type every tracker match value by hand. Meanwhile HA core
(≥ 2026.3) resolves `vacuum.clean_area` through a mapping stored on the vacuum
entity's registry entry options under the `vacuum` key: `area_mapping`
(`area ID → segment IDs`) and `last_seen_segments` (`[{id, name, group}]`),
edited via the frontend segment dialog. Trackers such as Roborock's diagnostic
current-room sensor report exactly that segment identity: the device room name,
or a raw segment ID.

## Decision
The mapping is reversed automatically instead of being configured. A derived
mapping matches tracker states against segment IDs, names, and slugified names
from `last_seen_segments`, then resolves them to areas via the inverted
`area_mapping`. The coordinator rebuilds it whenever the vacuum entity's
registry entry changes; manual match values keep precedence over derived ones.
The config flow skips the room-mapping step entirely when derivation covers all
selected areas and otherwise pre-fills the form with derived suggestions.

## Consequences
Zero extra configuration when the robot's own mapping dialog is set up; the
derived map follows renames there automatically. Same-named rooms on different
maps remain ambiguous to name-based trackers, so explicit match values stay
available as an override. Vacuums without the segment dialog behave exactly as
before (ADR-0004 remains the fallback).
