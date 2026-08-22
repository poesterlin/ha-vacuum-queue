"""Room switch entities."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import VacuumQueueCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one switch per configured room."""
    coordinator: VacuumQueueCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            VacuumQueueRoomSwitch(coordinator, area_id, order)
            for order, area_id in enumerate(coordinator.room_ids)
        ]
    )


class VacuumQueueRoomSwitch(SwitchEntity):
    """A switch that represents whether a room is queued."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: VacuumQueueCoordinator, area_id: str, order: int = 0
    ) -> None:
        self._coordinator = coordinator
        self._area_id = area_id
        self._order = order
        self._remove_listener = coordinator.async_add_listener(self._changed)
        self._attr_unique_id = f"{coordinator.entry_id}_{area_id}"
        self._attr_name = coordinator.room_name(area_id)
        self._attr_icon = "mdi:home-floor-1"
        self._attr_suggested_area = area_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._coordinator.entry_id)},
            name=f"Vacuum Queue ({self._coordinator.vacuum_entity_id})",
            manufacturer="Vacuum Queue",
        )

    @property
    def is_on(self) -> bool:
        return self._coordinator.is_room_on(self._area_id)

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        """Expose configuration order to the bundled dashboard card."""
        return {"queue_order": self._order}

    async def async_turn_on(self, **kwargs: object) -> None:
        await self._coordinator.handle_room_switch(self._area_id, True)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self._coordinator.handle_room_switch(self._area_id, False)

    @callback
    def _changed(self) -> None:
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        self._remove_listener()
