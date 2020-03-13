"""Support for ISY994 lights."""
import logging

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.light import DOMAIN, SUPPORT_BRIGHTNESS, Light
from homeassistant.const import STATE_UNKNOWN

from . import ISYDevice
from .const import DOMAIN as ISY994_DOMAIN, ISY994_NODES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the ISY994 light platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][DOMAIN]:
        devices.append(ISYLightDevice(node))

    async_add_entities(devices)


class ISYLightDevice(ISYDevice, Light):
    """Representation of an ISY994 light device."""

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 light is on."""
        if self.value == ISY_VALUE_UNKNOWN:
            return False
        return int(self.value) != 0

    @property
    def brightness(self) -> float:
        """Get the brightness of the ISY994 light."""
        return STATE_UNKNOWN if self.value == ISY_VALUE_UNKNOWN else int(self.value)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 light device."""
        if not self._node.turn_off():
            _LOGGER.debug("Unable to turn off light")

    # pylint: disable=arguments-differ
    def turn_on(self, brightness=None, **kwargs) -> None:
        """Send the turn on command to the ISY994 light device."""
        if not self._node.turn_on(val=brightness):
            _LOGGER.debug("Unable to turn on light")

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS
