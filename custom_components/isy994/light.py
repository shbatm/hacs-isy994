"""Support for ISY994 lights."""
import logging
from typing import Callable

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.light import DOMAIN, SUPPORT_BRIGHTNESS, Light
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.typing import HomeAssistantType

from . import ISYDevice, migrate_old_unique_ids
from .const import DOMAIN as ISY994_DOMAIN, ISY994_NODES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 light platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][DOMAIN]:
        devices.append(ISYLightDevice(node))

    await migrate_old_unique_ids(hass, DOMAIN, devices)
    async_add_entities(devices)


class ISYLightDevice(ISYDevice, Light):
    """Representation of an ISY994 light device."""

    def __init__(self, node) -> None:
        """Initialize the ISY994 light device."""
        super().__init__(node)
        self._last_brightness = self.brightness

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
        self._last_brightness = self.brightness
        if not self._node.turn_off():
            _LOGGER.debug("Unable to turn off light")

    def on_update(self, event: object) -> None:
        """Save brightness in the update event from the ISY994 Node."""
        if self.value not in (0, ISY_VALUE_UNKNOWN):
            self._last_brightness = self.value
        super().on_update(event)

    # pylint: disable=arguments-differ
    def turn_on(self, brightness=None, **kwargs) -> None:
        """Send the turn on command to the ISY994 light device."""
        if brightness is None and self._last_brightness is not None:
            brightness = self._last_brightness
        if not self._node.turn_on(val=brightness):
            _LOGGER.debug("Unable to turn on light")

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS
