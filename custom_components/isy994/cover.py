"""Support for ISY covers."""
from __future__ import annotations

from typing import Any, cast

from pyisyox.nodes import Node
from pyisyox.programs import Program

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, UOM_8_BIT_RANGE
from .entity import ISYNodeEntity, ISYProgramEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY cover platform."""
    isy_data = hass.data[DOMAIN][entry.entry_id]
    entities: list[ISYCoverEntity | ISYCoverProgramEntity] = []
    devices: dict[str, DeviceInfo] = isy_data.devices
    for node in isy_data.nodes[Platform.COVER]:
        entities.append(
            ISYCoverEntity(node=node, device_info=devices.get(node.primary_node))
        )

    for name, status, actions in isy_data.programs[Platform.COVER]:
        entities.append(ISYCoverProgramEntity(name, status, actions))

    async_add_entities(entities)


class ISYCoverEntity(ISYNodeEntity, CoverEntity):
    """Representation of an ISY cover device."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )
    _node: Node

    @property
    def current_cover_position(self) -> int | None:
        """Return the current cover position."""
        if self._node.status is None:
            return None
        if self._node.uom == UOM_8_BIT_RANGE:
            return round(cast(float, self._node.status) * 100.0 / 255.0)
        return int(sorted((0, self._node.status, 100))[1])

    @property
    def is_closed(self) -> bool | None:
        """Get whether the ISY cover device is closed."""
        if self._node.status is None:
            return None
        return bool(self._node.status == 0)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Send the open cover command to the ISY cover device."""
        if not await self._node.turn_on():
            raise HomeAssistantError(f"Unable to open the cover {self._node.address}")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Send the close cover command to the ISY cover device."""
        if not await self._node.turn_off():
            raise HomeAssistantError(f"Unable to close the cover {self._node.address}")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self._node.uom == UOM_8_BIT_RANGE:
            position = round(position * 255.0 / 100.0)
        if not await self._node.turn_on(val=position):
            raise HomeAssistantError(
                f"Unable to set cover {self._node.address} position"
            )


class ISYCoverProgramEntity(ISYProgramEntity, CoverEntity):
    """Representation of an ISY cover program."""

    _actions: Program

    @property
    def is_closed(self) -> bool:
        """Get whether the ISY cover program is closed."""
        return bool(self._node.status)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Send the open cover command to the ISY cover program."""
        if not await self._actions.run_then():
            raise HomeAssistantError(f"Unable to open the cover {self._node.address}")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Send the close cover command to the ISY cover program."""
        if not await self._actions.run_else():
            raise HomeAssistantError(f"Unable to close the cover {self._node.address}")
