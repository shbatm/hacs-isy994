"""Support for ISY994 locks."""
from typing import Callable

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.lock import DOMAIN as PLATFORM_DOMAIN, LockDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_LOCKED, STATE_UNKNOWN, STATE_UNLOCKED
from homeassistant.helpers.typing import HomeAssistantType

from . import migrate_old_unique_ids
from .const import _LOGGER, DOMAIN as ISY994_DOMAIN, ISY994_NODES, ISY994_PROGRAMS
from .entity import ISYNodeEntity, ISYProgramEntity
from .services import async_setup_device_services

VALUE_TO_STATE = {0: STATE_UNLOCKED, 100: STATE_LOCKED}


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 lock platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][PLATFORM_DOMAIN]:
        devices.append(ISYLockEnitity(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][PLATFORM_DOMAIN]:
        devices.append(ISYLockProgramEntity(name, status, actions))

    await migrate_old_unique_ids(hass, PLATFORM_DOMAIN, devices)
    async_add_entities(devices)
    async_setup_device_services(hass)


class ISYLockEnitity(ISYNodeEntity, LockDevice):
    """Representation of an ISY994 lock device."""

    @property
    def is_locked(self) -> bool:
        """Get whether the lock is in locked state."""
        return self.state == STATE_LOCKED

    @property
    def state(self) -> str:
        """Get the state of the lock."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN
        return VALUE_TO_STATE.get(self.value, STATE_UNKNOWN)

    def lock(self, **kwargs) -> None:
        """Send the lock command to the ISY994 device."""
        if not self._node.secure_lock():
            _LOGGER.error("Unable to lock device")

        self._node.update(0.5)

    def unlock(self, **kwargs) -> None:
        """Send the unlock command to the ISY994 device."""
        if not self._node.secure_unlock():
            _LOGGER.error("Unable to lock device")

        self._node.update(0.5)


class ISYLockProgramEntity(ISYProgramEntity, LockDevice):
    """Representation of a ISY lock program."""

    @property
    def is_locked(self) -> bool:
        """Return true if the device is locked."""
        return bool(self.value)

    @property
    def state(self) -> str:
        """Return the state of the lock."""
        return STATE_LOCKED if self.is_locked else STATE_UNLOCKED

    def lock(self, **kwargs) -> None:
        """Lock the device."""
        if not self._actions.run_then():
            _LOGGER.error("Unable to lock device")

    def unlock(self, **kwargs) -> None:
        """Unlock the device."""
        if not self._actions.run_else():
            _LOGGER.error("Unable to unlock device")
