"""The queue state machine for one vacuum."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry
from homeassistant.helpers import event as event_helper

from .const import (
    CONF_AREA_ID,
    CONF_MATCH_VALUES,
    CONF_SEGMENT_IDS,
    FLUSH_ACTIVITIES,
    LOGGER,
    RESEND_DEBOUNCE_SECONDS,
    VACUUM_RETURN_TO_BASE,
)
from .mapping import DerivedMapping, async_derive_mapping
from .store import VacuumQueueStore

Listener = Callable[[], None]


class VacuumQueueCoordinator:
    """Own all queue behavior for a single configured vacuum.

    The public interface is deliberately small. Callers mutate switches or
    request an action; they never manipulate the queue sets directly.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        vacuum_entity_id: str,
        tracker_entity_id: str,
        rooms: Iterable[dict[str, Any]],
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.vacuum_entity_id = vacuum_entity_id
        self.tracker_entity_id = tracker_entity_id
        self.rooms = tuple(dict(room) for room in rooms)
        self._rooms_by_area = {
            room[CONF_AREA_ID]: room for room in self.rooms if room.get(CONF_AREA_ID)
        }
        self._match_to_area = {
            value.strip().casefold(): room[CONF_AREA_ID]
            for room in self.rooms
            for value in room.get(CONF_MATCH_VALUES, [])
            if value.strip() and room.get(CONF_AREA_ID)
        }

        self._store = VacuumQueueStore(hass, entry_id)
        self._derived = DerivedMapping()
        self._switches_on: set[str] = set()
        self._last_cleaned: dict[str, float] = {}
        self._done_this_run: set[str] = set()
        self._current_area: str | None = None
        self._run_active = False
        self._vacuum_activity: str | None = None
        self._resend_pending = False
        self._listeners: set[Listener] = set()
        self._unsubscribers: list[Callable[[], None]] = []
        self._save_task: asyncio.Task[None] | None = None
        self._resend_task: asyncio.Task[None] | None = None

    async def async_initialize(self) -> None:
        """Restore persisted queue state and begin observing HA state."""
        data = await self._store.async_load()
        configured_areas = set(self._rooms_by_area)
        self._switches_on = {
            area_id
            for area_id in data.get("switches_on", [])
            if area_id in configured_areas
        }
        self._last_cleaned = {
            area_id: float(timestamp)
            for area_id, timestamp in data.get("last_cleaned", {}).items()
            if area_id in configured_areas
        }

        self._rebuild_derived()
        tracker_state = self.hass.states.get(self.tracker_entity_id)
        self._current_area = self._area_for_tracker_state(
            tracker_state.state if tracker_state else None
        )
        vacuum_state = self.hass.states.get(self.vacuum_entity_id)
        self._vacuum_activity = (
            vacuum_state.state.casefold() if vacuum_state else None
        )
        self._unsubscribers.extend(
            (
                event_helper.async_track_state_change_event(
                    self.hass,
                    [self.tracker_entity_id],
                    self._async_tracker_changed,
                ),
                event_helper.async_track_state_change_event(
                    self.hass,
                    [self.vacuum_entity_id],
                    self._async_vacuum_changed,
                ),
                event_helper.async_track_entity_registry_updated_event(
                    self.hass,
                    [self.vacuum_entity_id],
                    self._async_registry_updated,
                ),
                self.hass.bus.async_listen(
                    area_registry.EVENT_AREA_REGISTRY_UPDATED,
                    self._async_area_registry_changed,
                ),
            )
        )

    async def async_unload(self) -> None:
        """Stop listeners and finish the last persistence write."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        for task in (self._resend_task, self._save_task):
            if task:
                task.cancel()
        for task in (self._resend_task, self._save_task):
            if task:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        await self._store.async_save(
            dict(self._last_cleaned), sorted(self._switches_on)
        )

    @property
    def room_ids(self) -> tuple[str, ...]:
        """Return configured areas in configuration order."""
        return tuple(self._rooms_by_area)

    @property
    def is_active(self) -> bool:
        """Whether an explicit run is currently owned by the coordinator."""
        return self._run_active

    @property
    def current_area(self) -> str | None:
        """Return the mapped area reported by the tracker."""
        return self._current_area

    def room_name(self, area_id: str) -> str:
        """Return a configured room name, falling back to the area ID."""
        room = self._rooms_by_area.get(area_id, {})
        return str(room.get("name") or area_id)

    def room_icon(self, area_id: str) -> str | None:
        """Return the configured HA area icon for a room."""
        area = area_registry.async_get(self.hass).async_get_area(area_id)
        return area.icon if area else None

    @callback
    def _async_area_registry_changed(self, event: Event) -> None:
        """Refresh room entities when their area is updated."""
        area_id = event.data.get("area_id")
        if area_id is None or area_id in self._rooms_by_area:
            self._notify()

    def is_room_on(self, area_id: str) -> bool:
        """Return the switch state for one configured room."""
        return area_id in self._switches_on

    @callback
    def async_add_listener(self, listener: Listener) -> Callable[[], None]:
        """Subscribe an entity to queue state changes."""
        self._listeners.add(listener)

        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    async def async_start(self) -> None:
        """Start a run and send the currently remaining queue."""
        self._run_active = True
        self._done_this_run.clear()
        self._resend_pending = False
        await self._send_remaining_or_return()
        self._schedule_save()
        self._notify()

    async def async_skip(self) -> None:
        """Skip the current room and continue with the remaining queue."""
        if not self._run_active:
            return
        await self._pause()
        if self._current_area:
            self._complete_room(self._current_area)
        await self._send_remaining_or_return()
        self._schedule_save()
        self._notify()

    async def async_return_home(self) -> None:
        """Request that the vacuum returns home."""
        await self.hass.services.async_call(
            "vacuum",
            VACUUM_RETURN_TO_BASE,
            {"entity_id": self.vacuum_entity_id},
            blocking=True,
        )

    async def handle_room_switch(self, area_id: str, is_on: bool) -> None:
        """Apply a switch mutation and, when appropriate, resend the queue."""
        if area_id not in self._rooms_by_area:
            return
        skipped_current = False
        if is_on:
            self._switches_on.add(area_id)
        else:
            self._switches_on.discard(area_id)
            if self._run_active and area_id == self._current_area:
                await self._pause()
                self._complete_room(area_id)
                self._resend_pending = False
                skipped_current = True

        self._schedule_save()
        self._notify()
        if skipped_current:
            await self._send_remaining_or_return()
        elif self._run_active and self._is_cleaning():
            # Never replace the device's active command while a mapped room
            # is in progress. The next command is sent after its tracker
            # transition, so adding a room cannot interrupt that room.
            if self._current_area:
                self._resend_pending = True
            else:
                # Without a mapped current room there is no safe completion
                # boundary. Defer until the tracker reports one again.
                self._resend_pending = True

    async def _async_tracker_changed(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        old_area = self._current_area
        self._current_area = self._area_for_tracker_state(
            new_state.state if new_state else None
        )
        if (
            self._run_active
            and old_area
            and self._current_area
            and old_area != self._current_area
        ):
            self._complete_room(old_area)
            self._schedule_save()
            self._notify()
            if self._resend_pending and self._is_cleaning():
                self._resend_pending = False
                self._schedule_resend()

    async def _async_vacuum_changed(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        old_activity = self._vacuum_activity
        new_activity = new_state.state.casefold() if new_state else None
        self._vacuum_activity = new_activity
        if (
            new_activity in FLUSH_ACTIVITIES
            and new_activity != old_activity
            and self._switches_on
        ):
            self._switches_on.clear()
            self._done_this_run.clear()
            self._run_active = False
            self._resend_pending = False
            self._schedule_save()
            self._notify()

    @callback
    def _async_registry_updated(self, event: Event) -> None:
        """Re-derive the segment mapping after robot-config changes."""
        self._rebuild_derived()

    def _rebuild_derived(self) -> None:
        self._derived = async_derive_mapping(self.hass, self.vacuum_entity_id)

    def _area_for_tracker_state(self, state: str | None) -> str | None:
        if not state or state in ("unknown", "unavailable"):
            return None
        key = state.strip().casefold()
        return self._match_to_area.get(key) or self._derived.value_to_area.get(key)

    def _complete_room(self, area_id: str) -> None:
        self._done_this_run.add(area_id)
        self._switches_on.discard(area_id)
        self._last_cleaned[area_id] = time.time()

    def _remaining_areas(self) -> list[str]:
        remaining = (
            self._switches_on - self._done_this_run - {self._current_area}
        )
        return sorted(
            remaining,
            key=lambda area_id: (
                self._last_cleaned.get(area_id, float("-inf")),
                self.room_ids.index(area_id),
            ),
        )

    async def _send_remaining_or_return(self) -> None:
        areas = self._remaining_areas()
        if not areas:
            self._run_active = False
            await self.async_return_home()
            return
        await self._clean_areas(areas)

    async def _clean_areas(self, areas: list[str]) -> None:
        try:
            await self.hass.services.async_call(
                "vacuum",
                "clean_area",
                {"entity_id": self.vacuum_entity_id, "cleaning_area_id": areas},
                blocking=True,
            )
            return
        except HomeAssistantError as err:
            LOGGER.warning("clean_area failed for %s: %s", areas, err)

        segment_ids: list[str] = []
        for area_id in areas:
            room = self._rooms_by_area[area_id]
            candidates = [
                *room.get(CONF_SEGMENT_IDS, []),
                *self._derived.area_to_segments.get(area_id, []),
            ]
            segment_ids.extend(
                str(segment)
                for segment in candidates
                if str(segment) not in segment_ids
            )
        if not segment_ids:
            raise HomeAssistantError(
                "vacuum.clean_area failed and no fallback segment IDs are available"
            )
        await self.hass.services.async_call(
            "vacuum",
            "send_command",
            {
                "entity_id": self.vacuum_entity_id,
                "command": "app_segment_clean",
                "params": [{"segments": segment_ids, "repeat": 1}],
            },
            blocking=True,
        )

    async def _pause(self) -> None:
        await self.hass.services.async_call(
            "vacuum", "pause", {"entity_id": self.vacuum_entity_id}, blocking=True
        )

    def _is_cleaning(self) -> bool:
        return self._vacuum_activity == "cleaning"

    def _schedule_resend(self) -> None:
        if self._resend_task and not self._resend_task.done():
            self._resend_task.cancel()
        self._resend_task = asyncio.create_task(self._async_delayed_resend())

    async def _async_delayed_resend(self) -> None:
        try:
            await asyncio.sleep(RESEND_DEBOUNCE_SECONDS)
            if self._run_active and self._is_cleaning():
                # The current mapped room has finished. Pause so the device's
                # active command can be safely replaced with the updated queue
                # (adding a room must not interrupt a partly-cleaned room).
                await self._pause()
                await self._send_remaining_or_return()
        except asyncio.CancelledError:
            raise

    def _schedule_save(self) -> None:
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
        self._save_task = asyncio.create_task(self._async_delayed_save())

    async def _async_delayed_save(self) -> None:
        try:
            await asyncio.sleep(0.2)
            await self._store.async_save(
                dict(self._last_cleaned), sorted(self._switches_on)
            )
        except asyncio.CancelledError:
            raise

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()
