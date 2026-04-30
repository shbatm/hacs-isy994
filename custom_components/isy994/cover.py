"""Support for ISY covers."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyisyox.nodes import Node
from pyisyox.programs import Program

from .const import UOM_8_BIT_RANGE
from .entity import ISYNodeEntity, ISYProgramEntity, NodeEventType
from .models import IsyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IsyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ISY cover platform."""
    isy_data = entry.runtime_data
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

    def _update_cover_attrs(self) -> None:
        if self._node.status is None:
            self._attr_current_cover_position = None
            self._attr_is_closed = None
            return
        if self._node.uom == UOM_8_BIT_RANGE:
            self._attr_current_cover_position = round(
                cast(float, self._node.status) * 100.0 / 255.0
            )
        else:
            self._attr_current_cover_position = int(
                sorted((0, self._node.status, 100))[1]
            )
        self._attr_is_closed = bool(self._node.status == 0)

    async def async_added_to_hass(self) -> None:
        """Subscribe to events and set initial state."""
        await super().async_added_to_hass()
        self._update_cover_attrs()

    @callback
    def async_on_update(self, event: NodeEventType, key: str) -> None:
        """Handle a control event from the ISY Node."""
        self._update_cover_attrs()
        super().async_on_update(event, key)

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

    async def async_added_to_hass(self) -> None:
        """Subscribe to events and set initial state."""
        await super().async_added_to_hass()
        self._attr_is_closed = bool(self._node.status)

    @callback
    def async_on_update(self, event: NodeEventType, key: str) -> None:
        """Handle the update event from the ISY Node."""
        self._attr_is_closed = bool(self._node.status)
        super().async_on_update(event, key)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Send the open cover command to the ISY cover program."""
        if not await self._actions.run_then():
            raise HomeAssistantError(f"Unable to open the cover {self._node.address}")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Send the close cover command to the ISY cover program."""
        if not await self._actions.run_else():
            raise HomeAssistantError(f"Unable to close the cover {self._node.address}")
