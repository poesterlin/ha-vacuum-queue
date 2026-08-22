"""Derivation of tracker-to-room mappings from the vacuum's segment config."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_VACUUM_OPTIONS_KEY = "vacuum"
_AREA_MAPPING = "area_mapping"
_LAST_SEEN_SEGMENTS = "last_seen_segments"


def slugify(value: str) -> str:
    """Create a tracker-friendly variant of an area or segment name."""
    value = value.casefold().replace("ß", "ss")
    value = value.translate(str.maketrans({"ä": "a", "ö": "o", "ü": "u"}))
    value = unicodedata.normalize("NFKD", value)
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


@dataclass(slots=True)
class DerivedMapping:
    """Tracker values and fallback segments reversed from the vacuum entity.

    ``values_by_area`` maps every area ID to the raw tracker states that
    identify it; ``value_to_area`` is their inverted lookup table;
    ``area_to_segments`` carries the vacuum's own segment IDs per area.
    """

    values_by_area: dict[str, list[str]] = field(default_factory=dict)
    value_to_area: dict[str, str] = field(default_factory=dict)
    area_to_segments: dict[str, list[str]] = field(default_factory=dict)

    def covers(self, area_ids: list[str]) -> bool:
        """Whether every given area has at least one derived tracker value."""
        return all(self.values_by_area.get(area_id) for area_id in area_ids)


def async_derive_mapping(
    hass: HomeAssistant, vacuum_entity_id: str
) -> DerivedMapping:
    """Reverse the vacuum's own area-to-segment mapping into tracker matches.

    Area-capable vacuums store the user's segment mapping on the vacuum
    entity's registry entry options under the ``vacuum`` key:
    ``area_mapping`` ({area ID: [segment IDs]}) and ``last_seen_segments``
    ([{id, name, group}]). Matching a tracker state against the segment
    identity (ID or name) resolves the room without any manual setup.
    """
    mapping = DerivedMapping()
    entry = er.async_get(hass).async_get(vacuum_entity_id)
    if entry is None:
        return mapping
    options: dict[str, Any] = entry.options.get(_VACUUM_OPTIONS_KEY, {})
    area_mapping: dict[str, list[str]] | None = options.get(_AREA_MAPPING)
    segments: list[dict[str, Any]] | None = options.get(_LAST_SEEN_SEGMENTS)
    if not area_mapping or not segments:
        return mapping
    segment_to_area = {
        str(segment_id): area_id
        for area_id, segment_ids in area_mapping.items()
        for segment_id in segment_ids or []
    }
    for segment in segments:
        segment_id = str(segment.get("id") or "").strip()
        area_id = segment_to_area.get(segment_id)
        if not segment_id or area_id is None:
            continue
        name = str(segment.get("name") or "").strip()
        candidates = (
            segment_id.casefold(),
            name.casefold(),
            slugify(name),
        )
        known = mapping.values_by_area.setdefault(area_id, [])
        for value in dict.fromkeys(value for value in candidates if value):
            if value not in mapping.value_to_area:
                mapping.value_to_area[value] = area_id
                known.append(value)
        room_segments = mapping.area_to_segments.setdefault(area_id, [])
        if segment_id not in room_segments:
            room_segments.append(segment_id)
    return mapping
