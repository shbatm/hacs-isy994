"""Support for ISY994 covers."""

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_PROGRAMS,
    UOM_8_BIT_RANGE,
    UOM_BARRIER,
)
from .entity import ISYNodeEntity, ISYProgramEntity
from .helpers import migrate_old_unique_ids


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the ISY994 cover platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []
    for node in hass_isy_data[ISY994_NODES][COVER]:
        devices.append(ISYCoverEntity(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][COVER]:
        devices.append(ISYCoverProgramEntity(name, status, actions))

    await migrate_old_unique_ids(hass, COVER, devices)
    async_add_entities(devices)


class ISYCoverEntity(ISYNodeEntity, CoverEntity):
    """Representation of an ISY994 cover device."""

    @property
    def current_cover_position(self) -> int:
        """Return the current cover position."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        if self._node.uom == UOM_8_BIT_RANGE:
            return round(self._node.status * 100.0 / 255.0)
        return sorted((0, self._node.status, 100))[1]

    @property
    def is_closed(self) -> bool:
        """Get whether the ISY994 cover device is closed."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return self._node.status == 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    async def async_open_cover(self, **kwargs) -> None:
        """Send the open cover command to the ISY994 cover device."""
        val = 100 if self._node.uom == UOM_BARRIER else None
        if not await self._node.turn_on(val=val):
            _LOGGER.error("Unable to open the cover")

    async def async_close_cover(self, **kwargs) -> None:
        """Send the close cover command to the ISY994 cover device."""
        if not await self._node.turn_off():
            _LOGGER.error("Unable to close the cover")

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self._node.uom == UOM_8_BIT_RANGE:
            position = round(position * 255.0 / 100.0)
        if not await self._node.turn_on(val=position):
            _LOGGER.error("Unable to set cover position")


class ISYCoverProgramEntity(ISYProgramEntity, CoverEntity):
    """Representation of an ISY994 cover program."""

    @property
    def is_closed(self) -> bool:
        """Get whether the ISY994 cover program is closed."""
        return bool(self._node.status)

    async def async_open_cover(self, **kwargs) -> None:
        """Send the open cover command to the ISY994 cover program."""
        if not await self._actions.run_then():
            _LOGGER.error("Unable to open the cover")

    async def async_close_cover(self, **kwargs) -> None:
        """Send the close cover command to the ISY994 cover program."""
        if not await self._actions.run_else():
            _LOGGER.error("Unable to close the cover")
