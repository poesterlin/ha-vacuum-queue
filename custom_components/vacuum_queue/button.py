"""Action buttons for Vacuum Queue."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
        self._remove_listener = coordinator.async_add_listener(self._changed)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._coordinator.entry_id)},
            name=f"Vacuum Queue ({self._coordinator.vacuum_entity_id})",
            manufacturer="Vacuum Queue",
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose queue context to dashboards and custom cards."""
        current_area = self._coordinator.current_area
        return {
            "current_area": current_area,
            "current_room": (
                self._coordinator.room_name(current_area) if current_area else None
            ),
            "queue_active": self._coordinator.is_active,
        }

    @callback
    def _changed(self) -> None:
        self.async_write_ha_state()

    async def async_press(self) -> None:
        await getattr(self._coordinator, f"async_{self._action}")()

    async def async_will_remove_from_hass(self) -> None:
        self._remove_listener()
