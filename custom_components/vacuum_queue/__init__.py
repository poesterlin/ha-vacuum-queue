"""Home Assistant integration entrypoint for Vacuum Queue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry
from homeassistant.helpers.event import async_call_later

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

CARD_PATH = "/api/{}/static/vacuum-queue-card.js".format(DOMAIN)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/list"})
@websocket_api.async_response
async def _ws_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the switch/button entities of every Vacuum Queue entry."""
    er = entity_registry.async_get(hass)
    queues = []
    for key, coordinator in hass.data.get(DOMAIN, {}).items():
        if not isinstance(coordinator, VacuumQueueCoordinator):
            continue
        switches = []
        buttons = []
        device_id = None
        for entity in er.entities.values():
            if entity.config_entry_id != coordinator.entry_id:
                continue
            if entity.domain == "switch":
                switches.append(
                    {"entity_id": entity.entity_id, "unique_id": entity.unique_id}
                )
                device_id = device_id or entity.device_id
            elif entity.domain == "button":
                buttons.append(
                    {"entity_id": entity.entity_id, "unique_id": entity.unique_id}
                )
                device_id = device_id or entity.device_id
        queues.append(
            {
                "device_id": device_id,
                "vacuum_entity_id": coordinator.vacuum_entity_id,
                "switches": sorted(switches, key=lambda item: item["entity_id"]),
                "buttons": sorted(buttons, key=lambda item: item["entity_id"]),
            }
        )
    connection.send_result(msg["id"], queues)


async def _register_ws(hass: HomeAssistant) -> None:
    """Register the WebSocket API used by the bundled card."""
    hass.data.setdefault(DOMAIN, {})
    if hass.data[DOMAIN].get("ws_registered"):
        return
    websocket_api.async_register_command(hass, _ws_list)
    hass.data[DOMAIN]["ws_registered"] = True


def _card_version() -> str:
    """Return the manifest version for cache-busting the card URL."""
    manifest = json.loads((Path(__file__).parent / "manifest.json").read_text())
    return str(manifest.get("version", "0"))


async def _register_lovelace_resource(hass: HomeAssistant, lovelace: Any) -> None:
    """Register the card as a Lovelace module resource (storage mode)."""
    url = f"{CARD_PATH}?v={_card_version()}"

    async def _register(_now: Any = None) -> None:
        if not lovelace.resources.loaded:
            async_call_later(hass, 5, _register)
            return
        for resource in lovelace.resources.async_items():
            if resource["url"].split("?")[0] == CARD_PATH:
                if resource["url"] != url:
                    await lovelace.resources.async_update_item(
                        resource["id"], {"res_type": "module", "url": url}
                    )
                return
        await lovelace.resources.async_create_item(
            {"res_type": "module", "url": url}
        )

    await _register()


async def _register_frontend(hass: HomeAssistant) -> None:
    """Serve the Lovelace card and register it with the frontend."""
    hass.data.setdefault(DOMAIN, {})
    if hass.data[DOMAIN].get("frontend_registered"):
        return
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                f"/api/{DOMAIN}/static",
                str(Path(__file__).parent / "static"),
                True,
            )
        ]
    )
    lovelace = hass.data.get("lovelace")
    if lovelace is not None and getattr(lovelace, "mode", None) == "storage":
        await _register_lovelace_resource(hass, lovelace)
    else:
        add_extra_js_url(hass, f"{CARD_PATH}?v={_card_version()}")
    hass.data[DOMAIN]["frontend_registered"] = True


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration-wide services and frontend resources."""
    await _register_frontend(hass)
    await _register_ws(hass)

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
    await _register_frontend(hass)
    await _register_ws(hass)
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
