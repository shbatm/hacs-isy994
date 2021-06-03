"""Support for ISY994 locks."""

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.lock import DOMAIN as LOCK, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import _LOGGER, DOMAIN as ISY994_DOMAIN, ISY994_NODES, ISY994_PROGRAMS
from .entity import ISYNodeEntity, ISYProgramEntity
from .helpers import migrate_old_unique_ids

VALUE_TO_STATE = {0: False, 100: True}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the ISY994 lock platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][LOCK]:
        devices.append(ISYLockEntity(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][LOCK]:
        devices.append(ISYLockProgramEntity(name, status, actions))

    await migrate_old_unique_ids(hass, LOCK, devices)
    async_add_entities(devices)


class ISYLockEntity(ISYNodeEntity, LockEntity):
    """Representation of an ISY994 lock device."""

    @property
    def is_locked(self) -> bool:
        """Get whether the lock is in locked state."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return VALUE_TO_STATE.get(self._node.status)

    async def async_lock(self, **kwargs) -> None:
        """Send the lock command to the ISY994 device."""
        if not await self._node.secure_lock():
            _LOGGER.error("Unable to lock device")

    async def async_unlock(self, **kwargs) -> None:
        """Send the unlock command to the ISY994 device."""
        if not await self._node.secure_unlock():
            _LOGGER.error("Unable to lock device")


class ISYLockProgramEntity(ISYProgramEntity, LockEntity):
    """Representation of a ISY lock program."""

    @property
    def is_locked(self) -> bool:
        """Return true if the device is locked."""
        return bool(self._node.status)

    async def async_lock(self, **kwargs) -> None:
        """Lock the device."""
        if not await self._actions.run_then():
            _LOGGER.error("Unable to lock device")

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the device."""
        if not await self._actions.run_else():
            _LOGGER.error("Unable to unlock device")
