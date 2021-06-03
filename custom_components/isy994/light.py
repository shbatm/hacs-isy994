"""Support for ISY994 lights."""
from __future__ import annotations

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.light import (
    DOMAIN as LIGHT,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    _LOGGER,
    CONF_RESTORE_LIGHT_STATE,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    UOM_PERCENTAGE,
)
from .entity import ISYNodeEntity
from .helpers import migrate_old_unique_ids
from .services import async_setup_light_services

ATTR_LAST_BRIGHTNESS = "last_brightness"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the ISY994 light platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    isy_options = entry.options
    restore_light_state = isy_options.get(CONF_RESTORE_LIGHT_STATE, False)

    devices = []
    for node in hass_isy_data[ISY994_NODES][LIGHT]:
        devices.append(ISYLightEntity(node, restore_light_state))

    await migrate_old_unique_ids(hass, LIGHT, devices)
    async_add_entities(devices)
    async_setup_light_services(hass)


class ISYLightEntity(ISYNodeEntity, LightEntity, RestoreEntity):
    """Representation of an ISY994 light device."""

    def __init__(self, node, restore_light_state) -> None:
        """Initialize the ISY994 light device."""
        super().__init__(node)
        self._last_brightness = None
        self._restore_light_state = restore_light_state

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 light is on."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return False
        return int(self._node.status) != 0

    @property
    def brightness(self) -> float:
        """Get the brightness of the ISY994 light."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        # Special Case for ISY Z-Wave Devices using % instead of 0-255:
        if self._node.uom == UOM_PERCENTAGE:
            return round(self._node.status * 255.0 / 100.0)
        return int(self._node.status)

    async def async_turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 light device."""
        self._last_brightness = self.brightness
        if not await self._node.turn_off():
            _LOGGER.debug("Unable to turn off light")

    @callback
    def async_on_update(self, event: object) -> None:
        """Save brightness in the update event from the ISY994 Node."""
        if self._node.status not in (0, ISY_VALUE_UNKNOWN):
            self._last_brightness = self._node.status
            if self._node.uom == UOM_PERCENTAGE:
                self._last_brightness = round(self._node.status * 255.0 / 100.0)
            else:
                self._last_brightness = self._node.status
        super().async_on_update(event)

    # pylint: disable=arguments-differ
    async def async_turn_on(self, brightness=None, **kwargs) -> None:
        """Send the turn on command to the ISY994 light device."""
        if self._restore_light_state and brightness is None and self._last_brightness:
            brightness = self._last_brightness
        # Special Case for ISY Z-Wave Devices using % instead of 0-255:
        if brightness is not None and self._node.uom == UOM_PERCENTAGE:
            brightness = round(brightness * 100.0 / 255.0)
        if not await self._node.turn_on(val=brightness):
            _LOGGER.debug("Unable to turn on light")

    @property
    def extra_state_attributes(self) -> dict:
        """Return the light attributes."""
        attribs = super().extra_state_attributes
        attribs[ATTR_LAST_BRIGHTNESS] = self._last_brightness
        return attribs

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    async def async_added_to_hass(self) -> None:
        """Restore last_brightness on restart."""
        await super().async_added_to_hass()

        self._last_brightness = self.brightness or 255
        last_state = await self.async_get_last_state()
        if not last_state:
            return

        if (
            ATTR_LAST_BRIGHTNESS in last_state.attributes
            and last_state.attributes[ATTR_LAST_BRIGHTNESS]
        ):
            self._last_brightness = last_state.attributes[ATTR_LAST_BRIGHTNESS]

    async def async_set_on_level(self, value):
        """Set the ON Level for a device."""
        await self._node.set_on_level(value)

    async def async_set_ramp_rate(self, value):
        """Set the Ramp Rate for a device."""
        await self._node.set_ramp_rate(value)
