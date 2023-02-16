"""Representation of ISYEntity Types."""
from __future__ import annotations

from typing import Any, Union, cast

from pyisyox.constants import (
    ATTR_ACTION,
    ATTR_CONTROL,
    COMMAND_FRIENDLY_NAME,
    PROP_STATUS,
    TAG_ADDRESS,
    NodeChangeAction,
    Protocol,
)
from pyisyox.helpers.events import EventListener, NodeChangedEvent
from pyisyox.helpers.models import NodeProperty
from pyisyox.node_servers import NodeDef
from pyisyox.nodes import Group, Node
from pyisyox.nodes.nodebase import NodeBase
from pyisyox.programs import Program, ProgramDetail
from pyisyox.variables import Variable

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.util.dt import as_local

from .const import DOMAIN

NodeType = Union[Node, Group, NodeBase, Program, Variable]
NodeEventType = Union[NodeProperty, NodeChangedEvent]


class ISYEntity(Entity):
    """Representation of an ISY device."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _node: NodeType
    _change_handler: EventListener

    def __init__(
        self,
        node: NodeType,
        device_info: DeviceInfo | None = None,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the ISY/IoX entity."""
        self._node = node
        self._attr_name = node.name
        if device_info is None:
            device_info = DeviceInfo(identifiers={(DOMAIN, node.isy.uuid)})
        self._attr_device_info = device_info
        self._attr_unique_id = (
            unique_id if unique_id is not None else f"{node.isy.uuid}_{node.address}"
        )
        self._attrs: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.status_events.subscribe(
            self.async_on_update, key=self.unique_id
        )

    @callback
    def async_on_update(self, event: NodeEventType, key: str) -> None:
        """Handle the update event from the ISY Node."""
        self.async_write_ha_state()


class ISYGroupEntity(ISYEntity):
    """Representation of a ISY Group entity."""

    _node: Group

    @property
    def extra_state_attributes(self) -> dict:
        """Get the state attributes for the device."""
        return {"group_all_on": STATE_ON if self._node.group_all_on else STATE_OFF}


class ISYNodeEntity(ISYEntity):
    """Representation of a ISY Node entity."""

    _node: Node
    _control: str
    _node_def: NodeDef | None = None
    _change_handler: EventListener
    _availability_handler: EventListener

    def __init__(
        self,
        node: Node,
        control: str = PROP_STATUS,
        unique_id: str | None = None,
        description: EntityDescription | None = None,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the ISY/IoX node entity."""
        super().__init__(node, device_info=device_info, unique_id=unique_id)
        self._control = control
        if description is not None:
            self.entity_description = description

        # Determine the entity or device name to use
        name: str | None = None
        self._node_def = node.get_node_def()
        if self._node_def is not None:
            name = self._node_def.status_names.get(control)
        elif control != PROP_STATUS:
            name = COMMAND_FRIENDLY_NAME.get(control, control).replace("_", " ").title()

        if not node.is_device_root:
            name = f"{node.name} {name}" if name else node.name
            self._attr_has_entity_name = False
        else:
            self._attr_has_entity_name = True

        self._attr_name = name

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node control change events."""
        self._change_handler = self._node.control_events.subscribe(
            self.async_on_update,
            event_filter={ATTR_CONTROL: self._control},
            key=self.unique_id,
        )
        self._availability_handler = self._node.isy.nodes.platform_events.subscribe(
            self.async_on_update,
            event_filter={
                TAG_ADDRESS: self._node.address,
                ATTR_ACTION: NodeChangeAction.NODE_ENABLED,
            },
            key=self.unique_id,
        )

    @callback
    def async_on_update(self, event: NodeEventType, key: str) -> None:
        """Handle a control event from the ISY Node."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._node.enabled

    async def async_send_node_command(self, command: str) -> None:
        """Respond to an entity service command call."""
        if not hasattr(self._node, command):
            raise HomeAssistantError(
                f"Invalid service call: {command} for device {self.entity_id}"
            )
        await getattr(self._node, command)()

    async def async_send_raw_node_command(
        self,
        command: str,
        value: Any | None = None,
        unit_of_measurement: str | None = None,
        parameters: Any | None = None,
    ) -> None:
        """Respond to an entity service raw command call."""
        if not hasattr(self._node, "send_cmd"):
            raise HomeAssistantError(
                f"Invalid service call: {command} for device {self.entity_id}"
            )
        await self._node.send_cmd(command, value, unit_of_measurement, parameters)

    async def async_get_zwave_parameter(self, parameter: int) -> None:
        """Respond to an entity service command to request a Z-Wave device parameter from the ISY."""
        if self._node.protocol != Protocol.ZWAVE:
            raise HomeAssistantError(
                "Invalid service call: cannot request Z-Wave Parameter for non-Z-Wave"
                f" device {self.entity_id}"
            )
        await self._node.get_zwave_parameter(parameter)

    async def async_set_zwave_parameter(
        self, parameter: int, value: int, size: int
    ) -> None:
        """Respond to an entity service command to set a Z-Wave device parameter via the ISY."""
        if self._node.protocol != Protocol.ZWAVE:
            raise HomeAssistantError(
                "Invalid service call: cannot set Z-Wave Parameter for non-Z-Wave"
                f" device {self.entity_id}"
            )
        await self._node.set_zwave_parameter(parameter, value, size)
        await self._node.get_zwave_parameter(parameter)

    async def async_rename_node(self, name: str) -> None:
        """Respond to an entity service command to rename a node on the ISY."""
        await self._node.rename(name)


class ISYProgramEntity(ISYEntity):
    """Representation of an ISY program base."""

    _actions: Program | None
    _status: Program

    def __init__(
        self, name: str, status: Program, actions: Program | None = None
    ) -> None:
        """Initialize the ISY program-based entity."""
        super().__init__(status)
        self._attr_name = name
        self._actions = actions

    @property
    def extra_state_attributes(self) -> dict:
        """Get the state attributes for the device."""
        attr = {}
        if self._actions:
            actions_detail = cast(ProgramDetail, self._actions.detail)
            attr["actions_enabled"] = str(self._actions.enabled)
            if actions_detail.last_finish_time is not None:
                attr["actions_last_finished"] = str(
                    as_local(actions_detail.last_finish_time)
                )
            if actions_detail.last_run_time is not None:
                attr["actions_last_run"] = str(as_local(actions_detail.last_run_time))
            if self._actions.last_update is not None:
                attr["actions_last_update"] = str(as_local(self._actions.last_update))
            attr["run_at_startup"] = str(actions_detail.run_at_startup)
            attr["running"] = str(actions_detail.running)

        attr["status_enabled"] = str(self._node.enabled)
        detail = cast(ProgramDetail, self._node.detail)
        if detail.last_finish_time is not None:
            attr["status_last_finished"] = str(as_local(detail.last_finish_time))
        if detail.last_run_time is not None:
            attr["status_last_run"] = str(as_local(detail.last_run_time))
        if self._node.last_update is not None:
            attr["status_last_update"] = str(as_local(self._node.last_update))
        return attr
