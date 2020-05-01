"""Support for ISY994 covers."""
from typing import Callable

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.cover import DOMAIN as PLATFORM_DOMAIN, CoverDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN, STATE_UNKNOWN
from homeassistant.helpers.typing import HomeAssistantType

from . import ISYDevice, migrate_old_unique_ids
from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_PROGRAMS,
    UOM_TO_STATES,
)
from .services import async_setup_device_services


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 cover platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][PLATFORM_DOMAIN]:
        devices.append(ISYCoverDevice(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][PLATFORM_DOMAIN]:
        devices.append(ISYCoverProgram(name, status, actions))

    await migrate_old_unique_ids(hass, PLATFORM_DOMAIN, devices)
    async_add_entities(devices)
    async_setup_device_services(hass)


class ISYCoverDevice(ISYDevice, CoverDevice):
    """Representation of an ISY994 cover device."""

    @property
    def current_cover_position(self) -> int:
        """Return the current cover position."""
        if self.value in [None, ISY_VALUE_UNKNOWN]:
            return STATE_UNKNOWN
        return sorted((0, self.value, 100))[1]

    @property
    def is_closed(self) -> bool:
        """Get whether the ISY994 cover device is closed."""
        return self.state == STATE_CLOSED

    @property
    def state(self) -> str:
        """Get the state of the ISY994 cover device."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN
        return UOM_TO_STATES["97"].get(self.value, STATE_OPEN)

    def open_cover(self, **kwargs) -> None:
        """Send the open cover command to the ISY994 cover device."""
        if not self._node.turn_on(val=100):
            _LOGGER.error("Unable to open the cover")

    def close_cover(self, **kwargs) -> None:
        """Send the close cover command to the ISY994 cover device."""
        if not self._node.turn_off():
            _LOGGER.error("Unable to close the cover")


class ISYCoverProgram(ISYCoverDevice):
    """Representation of an ISY994 cover program."""

    def __init__(self, name: str, node: object, actions: object) -> None:
        """Initialize the ISY994 cover program."""
        super().__init__(node)
        self._name = name
        self._actions = actions

    @property
    def state(self) -> str:
        """Get the state of the ISY994 cover program."""
        return STATE_CLOSED if bool(self.value) else STATE_OPEN

    def open_cover(self, **kwargs) -> None:
        """Send the open cover command to the ISY994 cover program."""
        if not self._actions.run_then():
            _LOGGER.error("Unable to open the cover")

    def close_cover(self, **kwargs) -> None:
        """Send the close cover command to the ISY994 cover program."""
        if not self._actions.run_else():
            _LOGGER.error("Unable to close the cover")

    @property
    def device_state_attributes(self):
        """Get the state attributes for the device."""
        attr = {}
        if self._actions:
            attr["actions_enabled"] = self._actions.enabled
            attr["actions_last_finished"] = self._actions.last_finished
            attr["actions_last_run"] = self._actions.last_run
            attr["actions_last_update"] = self._actions.last_update
            attr["ran_else"] = self._actions.ran_else
            attr["ran_then"] = self._actions.ran_then
            attr["run_at_startup"] = self._actions.run_at_startup
            attr["running"] = self._actions.running
        attr["status_enabled"] = self._node.enabled
        attr["status_last_finished"] = self._node.last_finished
        attr["status_last_run"] = self._node.last_run
        attr["status_last_update"] = self._node.last_update
        return attr
