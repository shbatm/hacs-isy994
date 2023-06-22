"""Support for ISY switches."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pyisyox.nodes import Group, Node
from pyisyox.nodes.nodebase import NodeBase
from pyisyox.programs import Program

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ISYGroupEntity, ISYNodeEntity, ISYProgramEntity
from .models import IsyData


@dataclass
class ISYSwitchEntityDescription(SwitchEntityDescription):
    """Describes IST switch."""

    # ISYEnableSwitchEntity does not support UNDEFINED or None,
    # restrict the type to str.
    name: str = ""


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY switch platform."""
    isy_data: IsyData = hass.data[DOMAIN][entry.entry_id]
    entities: list[
        ISYSwitchEntity
        | ISYGroupSwitchEntity
        | ISYSwitchProgramEntity
        | ISYEnableSwitchEntity
    ] = []
    device_info = isy_data.devices
    for node in isy_data.nodes[Platform.SWITCH]:
        entities.append(
            ISYSwitchEntity(node=node, device_info=device_info.get(node.primary_node))
        )

    for group in isy_data.groups:
        device = None
        if len(group.controllers) == 1:
            # If Group has only 1 Controller, link to that device instead of the hub
            controller = cast(Node, isy_data.root.nodes.entities[group.controllers[0]])
            device = device_info.get(controller.primary_node)
        entities.append(ISYGroupSwitchEntity(node=group, device_info=device))

    for name, status, actions in isy_data.programs[Platform.SWITCH]:
        entities.append(ISYSwitchProgramEntity(name, status, actions))

    for node, control in isy_data.aux_properties[Platform.SWITCH]:
        # Currently only used for enable switches, will need to be updated for
        # NS support by making sure control == TAG_ENABLED
        description = ISYSwitchEntityDescription(
            key=control,
            device_class=SwitchDeviceClass.SWITCH,
            name=control.title(),
            entity_category=EntityCategory.CONFIG,
        )
        entities.append(
            ISYEnableSwitchEntity(
                node=node,
                control=control,
                unique_id=f"{isy_data.uid_base(node)}_{control}",
                description=description,
                device_info=device_info.get(node.primary_node),
            )
        )
    async_add_entities(entities)


class ISYSwitchEntityMixin(SwitchEntity):
    """Representation of an ISY switch device."""

    _node: NodeBase

    @property
    def is_on(self) -> bool | None:
        """Get whether the ISY device is in the on state."""
        if self._node.status is None:
            return None
        return bool(self._node.status)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY switch."""
        if not await self._node.turn_off():
            raise HomeAssistantError(f"Unable to turn off switch {self._node.address}")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the turn on command to the ISY switch."""
        if not await self._node.turn_on():
            raise HomeAssistantError(f"Unable to turn on switch {self._node.address}")


class ISYGroupSwitchEntity(ISYGroupEntity, ISYSwitchEntityMixin):
    """Representation of an ISY group switch device."""

    _node: Group
    _attr_icon: str = "mdi:google-circles-communities"


class ISYSwitchEntity(ISYNodeEntity, ISYSwitchEntityMixin):
    """Representation of an ISY switch device."""

    _node: Node


class ISYSwitchProgramEntity(ISYProgramEntity, SwitchEntity):
    """A representation of an ISY program switch."""

    _actions: Program
    _attr_icon: str = "mdi:script-text-outline"  # Matches isy program icon

    @property
    def is_on(self) -> bool:
        """Get whether the ISY switch program is on."""
        return bool(self._node.status)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the turn on command to the ISY switch program."""
        if not await self._actions.run_then():
            raise HomeAssistantError(
                f"Unable to run 'then' clause on program switch {self._actions.address}"
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY switch program."""
        if not await self._actions.run_else():
            raise HomeAssistantError(
                f"Unable to run 'else' clause on program switch {self._actions.address}"
            )


class ISYEnableSwitchEntity(ISYNodeEntity, SwitchEntity):
    """A representation of an ISY enable/disable switch."""

    def __init__(
        self,
        node: Node,
        control: str,
        unique_id: str,
        description: ISYSwitchEntityDescription,
        device_info: DeviceInfo | None,
    ) -> None:
        """Initialize the ISY Aux Control Number entity."""
        super().__init__(
            node=node,
            control=control,
            unique_id=unique_id,
            description=description,
            device_info=device_info,
        )
        self._attr_name = description.name  # Override super

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True  # Enable switch is always available

    @property
    def is_on(self) -> bool | None:
        """Get whether the ISY device is in the on state."""
        return bool(self._node.enabled)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY switch."""
        if not await self._node.disable():
            raise HomeAssistantError(f"Unable to disable device {self._node.address}")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the turn on command to the ISY switch."""
        if not await self._node.enable():
            raise HomeAssistantError(f"Unable to enable device {self._node.address}")
