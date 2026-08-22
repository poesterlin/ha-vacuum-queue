"""Home Assistant integration entrypoint for Vacuum Queue."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ROOMS,
    CONF_TRACKER_ENTITY,
    CONF_VACUUM_ENTITY,
    DOMAIN,
    PLATFORMS,
    SERVICE_RETURN_HOME,
    SERVICE_SKIP,
    SERVICE_START,
)
from .coordinator import VacuumQueueCoordinator

SERVICE_SCHEMA = vol.Schema({vol.Required(CONF_VACUUM_ENTITY): cv.entity_id})


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration-wide services and frontend resources."""
    hass.data.setdefault(DOMAIN, {})
    if not hass.data[DOMAIN].get("frontend_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    f"/api/{DOMAIN}/static",
                    str(Path(__file__).parent / "static"),
                    True,
                )
            ]
        )
        hass.data[DOMAIN]["frontend_registered"] = True

    if hass.data[DOMAIN].get("services_registered"):
        return True

    async def handle_start(call: ServiceCall) -> None:
        await _call_coordinators(hass, call, "async_start")

    async def handle_skip(call: ServiceCall) -> None:
        await _call_coordinators(hass, call, "async_skip")

    async def handle_return_home(call: ServiceCall) -> None:
        await _call_coordinators(hass, call, "async_return_home")

    hass.services.async_register(
        DOMAIN, SERVICE_START, handle_start, schema=SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SKIP, handle_skip, schema=SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RETURN_HOME,
        handle_return_home,
        schema=SERVICE_SCHEMA,
    )
    hass.data[DOMAIN]["services_registered"] = True
    return True


async def _call_coordinators(
    hass: HomeAssistant, call: ServiceCall, method_name: str
) -> None:
    """Dispatch a service call to its configured vacuum."""
    vacuum_entity_id = call.data[CONF_VACUUM_ENTITY]
    coordinators = [
        coordinator
        for key, coordinator in hass.data.get(DOMAIN, {}).items()
        if key != "services_registered"
        and isinstance(coordinator, VacuumQueueCoordinator)
        and coordinator.vacuum_entity_id == vacuum_entity_id
    ]
    if not coordinators:
        raise HomeAssistantError(f"No Vacuum Queue entry uses {vacuum_entity_id}")
    await getattr(coordinators[0], method_name)()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one Vacuum Queue config entry."""
    settings = {**entry.data, **entry.options}
    coordinator = VacuumQueueCoordinator(
        hass,
        entry.entry_id,
        settings[CONF_VACUUM_ENTITY],
        settings[CONF_TRACKER_ENTITY],
        settings.get(CONF_ROOMS, []),
    )
    await coordinator.async_initialize()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one Vacuum Queue config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if coordinator:
        await coordinator.async_unload()
    return unloaded
