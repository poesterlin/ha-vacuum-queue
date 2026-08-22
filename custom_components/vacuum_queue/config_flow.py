"""Config and options flows for Vacuum Queue."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, selector
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar

from .const import (
    CONF_AREA_ID,
    CONF_MATCH_VALUES,
    CONF_ROOMS,
    CONF_SEGMENT_IDS,
    CONF_TRACKER_ENTITY,
    CONF_VACUUM_ENTITY,
    DOMAIN,
)

_AREA_IDS = "area_ids"
_MATCH_PREFIX = "match_"
_SEGMENT_PREFIX = "segments_"


def _slugify(value: str) -> str:
    """Create the tracker-friendly default suggested by an area name."""
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _as_list(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,\n]", value) if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _area_ids(value: Any) -> list[str]:
    return list(dict.fromkeys(_as_list(value)))


def _room_schema(
    hass: HomeAssistant, area_ids: list[str], existing: dict[str, dict[str, Any]]
) -> vol.Schema:
    """Build one match/segment form row per selected area."""
    registry = ar.async_get(hass)
    schema: dict[Any, Any] = {}
    for area_id in area_ids:
        area = registry.async_get_area(area_id)
        name = area.name if area else area_id
        old = existing.get(area_id, {})
        default_matches = ", ".join(
            old.get(CONF_MATCH_VALUES, []) or [_slugify(name)]
        )
        default_segments = ", ".join(
            str(segment_id) for segment_id in old.get(CONF_SEGMENT_IDS, [])
        )
        schema[vol.Required(f"{_MATCH_PREFIX}{area_id}", default=default_matches)] = str
        schema[
            vol.Optional(f"{_SEGMENT_PREFIX}{area_id}", default=default_segments)
        ] = str
    return vol.Schema(schema)


def _rooms_from_input(
    hass: HomeAssistant, area_ids: list[str], user_input: dict[str, Any]
) -> list[dict[str, Any]]:
    registry = ar.async_get(hass)
    rooms: list[dict[str, Any]] = []
    for area_id in area_ids:
        area = registry.async_get_area(area_id)
        name = area.name if area else area_id
        raw_matches = user_input.get(f"{_MATCH_PREFIX}{area_id}", _slugify(name))
        raw_segments = user_input.get(f"{_SEGMENT_PREFIX}{area_id}", "")
        segment_ids = [int(value) for value in _as_list(raw_segments)]
        rooms.append(
            {
                CONF_AREA_ID: area_id,
                "name": name,
                CONF_MATCH_VALUES: _as_list(raw_matches),
                CONF_SEGMENT_IDS: segment_ids,
            }
        )
    return rooms


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial configuration."""

    VERSION = 1

    def __init__(self) -> None:
        self._base: dict[str, Any] = {}
        self._area_ids: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the vacuum, tracker, and cleanable areas."""
        if user_input is not None:
            self._area_ids = _area_ids(user_input.pop(_AREA_IDS, []))
            self._base = user_input
            if not self._area_ids:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(),
                    errors={_AREA_IDS: "no_rooms"},
                )
            await self.async_set_unique_id(self._base[CONF_VACUUM_ENTITY])
            self._abort_if_unique_id_configured()
            return await self.async_step_rooms()

        return self.async_show_form(step_id="user", data_schema=self._user_schema())

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Map tracker values to each selected area."""
        if user_input is not None:
            try:
                rooms = _rooms_from_input(self.hass, self._area_ids, user_input)
            except ValueError:
                return self.async_show_form(
                    step_id="rooms",
                    data_schema=_room_schema(self.hass, self._area_ids, {}),
                    errors={"base": "invalid_segments"},
                )
            return self.async_create_entry(
                title=self._base[CONF_VACUUM_ENTITY],
                data={**self._base, CONF_ROOMS: rooms},
            )
        return self.async_show_form(
            step_id="rooms", data_schema=_room_schema(self.hass, self._area_ids, {})
        )

    @staticmethod
    def _user_schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_VACUUM_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="vacuum")
                ),
                vol.Required(CONF_TRACKER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(_AREA_IDS): selector.AreaSelector(
                    selector.AreaSelectorConfig(multiple=True)
                ),
            }
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Return the options flow for an existing entry."""
        return VacuumQueueOptionsFlow()


class VacuumQueueOptionsFlow(config_entries.OptionsFlowWithReload):
    """Edit vacuum, tracker, and room mappings."""

    def __init__(self) -> None:
        self._base: dict[str, Any] = {}
        self._area_ids: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the current set of areas."""
        settings = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            self._area_ids = _area_ids(user_input.pop(_AREA_IDS, []))
            self._base = user_input
            if not self._area_ids:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(settings),
                    errors={_AREA_IDS: "no_rooms"},
                )
            return await self.async_step_rooms()

        return self.async_show_form(
            step_id="init",
            data_schema=self._schema(settings),
        )

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit tracker match values and fallback segments."""
        settings = {**self.config_entry.data, **self.config_entry.options}
        existing = {
            room[CONF_AREA_ID]: room for room in settings.get(CONF_ROOMS, [])
        }
        if user_input is not None:
            try:
                rooms = _rooms_from_input(self.hass, self._area_ids, user_input)
            except ValueError:
                return self.async_show_form(
                    step_id="rooms",
                    data_schema=_room_schema(self.hass, self._area_ids, existing),
                    errors={"base": "invalid_segments"},
                )
            return self.async_create_entry(
                title="",
                data={**self._base, CONF_ROOMS: rooms},
            )
        return self.async_show_form(
            step_id="rooms",
            data_schema=_room_schema(self.hass, self._area_ids, existing),
        )

    @staticmethod
    def _schema(settings: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(
                    CONF_VACUUM_ENTITY,
                    default=settings.get(CONF_VACUUM_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="vacuum")
                ),
                vol.Required(
                    CONF_TRACKER_ENTITY,
                    default=settings.get(CONF_TRACKER_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    _AREA_IDS,
                    default=[
                        room[CONF_AREA_ID] for room in settings.get(CONF_ROOMS, [])
                    ],
                ): selector.AreaSelector(selector.AreaSelectorConfig(multiple=True)),
            }
        )
