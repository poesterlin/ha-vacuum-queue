# ADR-0004: Manual tracker→room map

Status: accepted (fallback; see ADR-0010)

## Context
Knowing the current room requires bridging raw tracker sensor values (`bad`,
`küche`) to area IDs. Fuzzy auto-matching was considered but rejected as
surprising when wrong.

## Decision
The user explicitly maps match values to rooms in the config/options flow. The
flow pre-fills each room's field with its slugified area name as a suggestion.
Unmapped or unavailable tracker states are ignored, never guessed.

## Consequences
Deterministic behavior, trivially debuggable; slightly more setup work once per
home.
