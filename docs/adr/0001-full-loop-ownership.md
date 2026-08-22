# ADR-0001: The integration fully owns the cleaning loop

Status: accepted

## Context
The previous setup spread the loop over three HA objects: a "skip current room"
script, a "reset toggles on finish" automation and a "turn off toggle on room
transition" automation, plus an external `script.start_vacuuming_in_order`.
State was scattered across Jinja templates; every rule duplicated room knowledge.

## Decision
One config entry per vacuum owns start, sequencing, skip, return-home and queue
reset. The three automations and the start script are replaced by coordinator
logic. No external scripts are called.

## Consequences
All behavior is local to one module (locality); deleting it deletes the whole
feature (deletion test passes). Users must remove their old script/automations.
