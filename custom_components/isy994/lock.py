"""Support for ISY994 locks."""
import logging

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.lock import DOMAIN, LockDevice
from homeassistant.const import STATE_LOCKED, STATE_UNKNOWN, STATE_UNLOCKED

from . import ISYDevice
from .const import DOMAIN as ISY994_DOMAIN, ISY994_NODES, ISY994_PROGRAMS

_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {0: STATE_UNLOCKED, 100: STATE_LOCKED}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the ISY994 lock platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][DOMAIN]:
        devices.append(ISYLockDevice(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][DOMAIN]:
        devices.append(ISYLockProgram(name, status, actions))

    async_add_entities(devices)


class ISYLockDevice(ISYDevice, LockDevice):
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


class ISYLockProgram(ISYLockDevice):
    """Representation of a ISY lock program."""

    def __init__(self, name: str, node, actions) -> None:
        """Initialize the lock."""
        super().__init__(node)
        self._name = name
        self._actions = actions

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
