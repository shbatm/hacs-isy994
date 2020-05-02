"""Support for ISY994 fans."""
from typing import Callable

from homeassistant.components.fan import (
    DOMAIN as PLATFORM_DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import ISYDevice, migrate_old_unique_ids
from .const import _LOGGER, DOMAIN as ISY994_DOMAIN, ISY994_NODES, ISY994_PROGRAMS
from .services import async_setup_device_services

VALUE_TO_STATE = {
    0: SPEED_OFF,
    63: SPEED_LOW,
    64: SPEED_LOW,
    190: SPEED_MEDIUM,
    191: SPEED_MEDIUM,
    255: SPEED_HIGH,
}

STATE_TO_VALUE = {}
for key in VALUE_TO_STATE:
    STATE_TO_VALUE[VALUE_TO_STATE[key]] = key


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 fan platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []

    for node in hass_isy_data[ISY994_NODES][PLATFORM_DOMAIN]:
        devices.append(ISYFanDevice(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][PLATFORM_DOMAIN]:
        devices.append(ISYFanProgram(name, status, actions))

    await migrate_old_unique_ids(hass, PLATFORM_DOMAIN, devices)
    async_add_entities(devices)
    await async_setup_device_services(hass)


class ISYFanDevice(ISYDevice, FanEntity):
    """Representation of an ISY994 fan device."""

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return VALUE_TO_STATE.get(self.value)

    @property
    def is_on(self) -> bool:
        """Get if the fan is on."""
        return self.value != 0

    def set_speed(self, speed: str) -> None:
        """Send the set speed command to the ISY994 fan device."""
        self._node.turn_on(val=STATE_TO_VALUE.get(speed, 255))

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Send the turn on command to the ISY994 fan device."""
        self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 fan device."""
        self._node.turn_off()

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED


class ISYFanProgram(ISYFanDevice):
    """Representation of an ISY994 fan program."""

    def __init__(self, name: str, node, actions) -> None:
        """Initialize the ISY994 fan program."""
        super().__init__(node)
        self._name = name
        self._actions = actions

    def turn_off(self, **kwargs) -> None:
        """Send the turn on command to ISY994 fan program."""
        if not self._actions.run_then():
            _LOGGER.error("Unable to turn off the fan")

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Send the turn off command to ISY994 fan program."""
        if not self._actions.run_else():
            _LOGGER.error("Unable to turn on the fan")

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0

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
