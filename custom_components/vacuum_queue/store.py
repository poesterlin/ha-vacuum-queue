"""Persistence for last-cleaned timestamps and switch states."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORE_VERSION

_LOGGER = logging.getLogger(__name__)


class VacuumQueueStore:
    """Thin adapter over HA's Store: timestamps + switch states."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}_{entry_id}", private=True
        )

    async def async_load(self) -> dict[str, Any]:
        data = await self._store.async_load()
        return data or {}

    async def async_save(
        self, last_cleaned: dict[str, float], switches_on: list[str]
    ) -> None:
        await self._store.async_save(
            {"last_cleaned": last_cleaned, "switches_on": switches_on}
        )
