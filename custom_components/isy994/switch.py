"""Support for ISY994 switches."""
from typing import Callable

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_GROUP

from homeassistant.components.switch import DOMAIN as PLATFORM_DOMAIN, SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PAYLOAD_OFF, CONF_PAYLOAD_ON, STATE_UNKNOWN
from homeassistant.helpers.typing import HomeAssistantType

from . import ISYNodeEntity, ISYProgramEntity, ISYVariableEntity, migrate_old_unique_ids
from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_VARIABLES,
)
from .services import async_setup_device_services


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 switch platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][PLATFORM_DOMAIN]:
        devices.append(ISYSwitchDevice(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][PLATFORM_DOMAIN]:
        devices.append(ISYSwitchProgram(name, status, actions))

    for vcfg, vname, vobj in hass_isy_data[ISY994_VARIABLES][PLATFORM_DOMAIN]:
        devices.append(ISYSwitchVariable(vcfg, vname, vobj))

    await migrate_old_unique_ids(hass, PLATFORM_DOMAIN, devices)
    async_add_entities(devices)
    async_setup_device_services(hass)


class ISYSwitchDevice(ISYNodeEntity, SwitchDevice):
    """Representation of an ISY994 switch device."""

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 device is in the on state."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN
        return bool(self.value)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch."""
        if not self._node.turn_off():
            _LOGGER.debug("Unable to turn off switch.")

    def turn_on(self, **kwargs) -> None:
        """Send the turn oon command to the ISY994 switch."""
        if not self._node.turn_on():
            _LOGGER.debug("Unable to turn on switch.")

    @property
    def icon(self) -> str:
        """Get the icon for groups."""
        if hasattr(self._node, "protocol") and self._node.protocol == PROTO_GROUP:
            return "mdi:google-circles-communities"  # Matches isy scene icon
        return super().icon


class ISYSwitchProgram(ISYProgramEntity, SwitchDevice):
    """A representation of an ISY994 program switch."""

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 switch program is on."""
        return bool(self.value)

    def turn_on(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch program."""
        if not self._actions.run_then():
            _LOGGER.error("Unable to turn on switch")

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch program."""
        if not self._actions.run_else():
            _LOGGER.error("Unable to turn off switch")


class ISYSwitchVariable(ISYVariableEntity, SwitchDevice):
    """Representation of an ISY994 variable as a sensor device."""

    def __init__(self, vcfg: dict, vname: str, vobj: object) -> None:
        """Initialize the ISY994 binary sensor program."""
        super().__init__(vcfg, vname, vobj)
        self._on_value = vcfg.get(CONF_PAYLOAD_ON)
        self._off_value = vcfg.get(CONF_PAYLOAD_OFF)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN
        if self.value == self._on_value:
            return True
        if self.value == self._off_value:
            return False
        return None

    def turn_off(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch."""
        self._node.set_value(self._off_value)

    def turn_on(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch."""
        self._node.set_value(self._on_value)
