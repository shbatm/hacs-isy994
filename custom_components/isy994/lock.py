"""Support for ISY locks."""
from __future__ import annotations

from typing import Any

from pyisyox.nodes import Node
from pyisyox.programs import Program

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import _LOGGER, DOMAIN
from .entity import ISYNodeEntity, ISYProgramEntity
from .services import async_setup_lock_services

VALUE_TO_STATE = {0: False, 100: True}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY lock platform."""
    isy_data = hass.data[DOMAIN][entry.entry_id]
    devices: dict[str, DeviceInfo] = isy_data.devices
    entities: list[ISYLockEntity | ISYLockProgramEntity] = []
    for node in isy_data.nodes[Platform.LOCK]:
        entities.append(
            ISYLockEntity(node=node, device_info=devices.get(node.primary_node))
        )

    for name, status, actions in isy_data.programs[Platform.LOCK]:
        entities.append(ISYLockProgramEntity(name, status, actions))

    async_add_entities(entities)
    async_setup_lock_services(hass)


class ISYLockEntity(ISYNodeEntity, LockEntity):
    """Representation of an ISY lock device."""

    _node: Node

    @property
    def is_locked(self) -> bool | None:
        """Get whether the lock is in locked state."""
        if self._node.status is None:
            return None
        return VALUE_TO_STATE.get(self._node.status)

    async def async_lock(self, **kwargs: Any) -> None:
        """Send the lock command to the ISY device."""
        if not await self._node.secure_lock():
            _LOGGER.error("Unable to lock device")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send the unlock command to the ISY device."""
        if not await self._node.secure_unlock():
            _LOGGER.error("Unable to lock device")

    async def async_set_zwave_lock_user_code(self, user_num: int, code: int) -> None:
        """Set the ON Level for a device."""
        if not await self._node.set_zwave_lock_code(user_num, code):
            raise HomeAssistantError(
                f"Could not set user code {user_num} for {self._node.address}"
            )

    async def async_delete_zwave_lock_user_code(self, user_num: int) -> None:
        """Set the Ramp Rate for a device."""
        if not await self._node.delete_zwave_lock_code(user_num):
            raise HomeAssistantError(
                f"Could not delete user code {user_num} for {self._node.address}"
            )


class ISYLockProgramEntity(ISYProgramEntity, LockEntity):
    """Representation of a ISY lock program."""

    _actions: Program

    @property
    def is_locked(self) -> bool:
        """Return true if the device is locked."""
        return bool(self._node.status)

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        if not await self._actions.run_then():
            _LOGGER.error("Unable to lock device")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        if not await self._actions.run_else():
            _LOGGER.error("Unable to unlock device")
