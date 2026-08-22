"""Action buttons for Vacuum Queue."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import VacuumQueueCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create Start, Skip, and Return home buttons."""
    coordinator: VacuumQueueCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            VacuumQueueActionButton(coordinator, "start", "Start", "mdi:play"),
            VacuumQueueActionButton(coordinator, "skip", "Skip", "mdi:skip-next"),
            VacuumQueueActionButton(
                coordinator, "return_home", "Return home", "mdi:home-import-outline"
            ),
        ]
    )


class VacuumQueueActionButton(ButtonEntity):
    """A thin entity adapter for one coordinator action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VacuumQueueCoordinator,
        action: str,
        name: str,
        icon: str,
    ) -> None:
        self._coordinator = coordinator
        self._action = action
        self._attr_unique_id = f"{coordinator.entry_id}_{action}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._coordinator.entry_id)},
            name=f"Vacuum Queue ({self._coordinator.vacuum_entity_id})",
            manufacturer="Vacuum Queue",
        )

    async def async_press(self) -> None:
        await getattr(self._coordinator, f"async_{self._action}")()
