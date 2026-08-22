"""Constants for Vacuum Queue."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "vacuum_queue"
LOGGER: Final = logging.getLogger(__package__)

PLATFORMS: Final = [Platform.BUTTON, Platform.SWITCH]

CONF_VACUUM_ENTITY: Final = "vacuum_entity_id"
CONF_TRACKER_ENTITY: Final = "tracker_entity_id"
CONF_ROOMS: Final = "rooms"
CONF_AREA_ID: Final = "area_id"
CONF_MATCH_VALUES: Final = "match_values"
CONF_SEGMENT_IDS: Final = "segment_ids"

SERVICE_START: Final = "start"
SERVICE_SKIP: Final = "skip"
SERVICE_RETURN_HOME: Final = "return_home"
VACUUM_RETURN_TO_BASE: Final = "return_to_base"

# Activities that count as "came home" and flush the queue (ADR-0008).
FLUSH_ACTIVITIES: Final[frozenset[str]] = frozenset(
    {"returning", "returning_to_dock", "docked", "charging"}
)

# Debounce window before a resend of the remaining queue is issued (ADR-0007).
RESEND_DEBOUNCE_SECONDS: Final = 2.0

STORE_VERSION: Final = 1
