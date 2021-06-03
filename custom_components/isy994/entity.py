"""Representation of ISYEntity Types."""
from __future__ import annotations

from pyisy.constants import (
    COMMAND_FRIENDLY_NAME,
    EMPTY_TIME,
    EVENT_PROPS_IGNORED,
    PROTO_GROUP,
    PROTO_ZWAVE,
)
from pyisy.helpers import NodeProperty

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class ISYEntity(Entity):
    """Representation of an ISY994 device."""

    _name: str = None

    def __init__(self, node) -> None:
        """Initialize the insteon device."""
        self._node = node
        self._attrs = {}
        self._change_handler = None
        self._control_handler = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.status_events.subscribe(self.async_on_update)

        if hasattr(self._node, "control_events"):
            self._control_handler = self._node.control_events.subscribe(
                self.async_on_control
            )

    @callback
    def async_on_update(self, event: object) -> None:
        """Handle the update event from the ISY994 Node."""
        self.async_write_ha_state()

    @callback
    def async_on_control(self, event: NodeProperty) -> None:
        """Handle a control event from the ISY994 Node."""
        event_data = {
            "entity_id": self.entity_id,
            "control": event.control,
            "value": event.value,
            "formatted": event.formatted,
            "uom": event.uom,
            "precision": event.prec,
        }

        if event.control not in EVENT_PROPS_IGNORED:
            # New state attributes may be available, update the state.
            self.async_write_ha_state()

        self.hass.bus.fire("isy994_control", event_data)

    @property
    def device_info(self):
        """Return the device_info of the device."""
        if hasattr(self._node, "protocol") and self._node.protocol == PROTO_GROUP:
            # not a device
            return None
        uuid = self._node.isy.configuration["uuid"]
        node = self._node
        basename = self.name

        if hasattr(self._node, "parent_node") and self._node.parent_node is not None:
            # This is not the parent node, get the parent node.
            node = self._node.parent_node
            basename = node.name

        device_info = {
            "name": basename,
            "identifiers": {},
            "model": "Unknown",
            "manufacturer": "Unknown",
            "via_device": (DOMAIN, uuid),
        }

        if hasattr(node, "address"):
            device_info["name"] += f" ({node.address})"
        if hasattr(node, "primary_node"):
            device_info["identifiers"] = {(DOMAIN, f"{uuid}_{node.address}")}
        # ISYv5 Device Types
        if hasattr(node, "node_def_id") and node.node_def_id is not None:
            device_info["model"] = node.node_def_id
            # Numerical Device Type
            if hasattr(node, "type") and node.type is not None:
                device_info["model"] += f" {node.type}"
        if hasattr(node, "protocol"):
            device_info["manufacturer"] = node.protocol
            if node.protocol == PROTO_ZWAVE:
                # Get extra information for Z-Wave Devices
                device_info["manufacturer"] += f" MfrID:{node.zwave_props.mfr_id}"
                device_info["model"] += (
                    f" Type:{node.zwave_props.devtype_gen} "
                    f"ProductTypeID:{node.zwave_props.prod_type_id} "
                    f"ProductID:{node.zwave_props.product_id}"
                )
        if hasattr(node, "folder") and node.folder is not None:
            device_info["suggested_area"] = node.folder
        # Note: sw_version is not exposed by the ISY for the individual devices.

        return device_info

    @property
    def unique_id(self) -> str:
        """Get the unique identifier of the device."""
        if hasattr(self._node, "address"):
            return f"{self._node.isy.configuration['uuid']}_{self._node.address}"
        return None

    @property
    def old_unique_id(self) -> str:
        """Get the old unique identifier of the device."""
        if hasattr(self._node, "address"):
            return self._node.address
        return None

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._name or str(self._node.name)

    @property
    def should_poll(self) -> bool:
        """No polling required since we're using the subscription."""
        return False


class ISYNodeEntity(ISYEntity):
    """Representation of a ISY Nodebase (Node/Group) entity."""

    @property
    def extra_state_attributes(self) -> dict:
        """Get the state attributes for the device.

        The 'aux_properties' in the pyisy Node class are combined with the
        other attributes which have been picked up from the event stream and
        the combined result are returned as the device state attributes.
        """
        attr = {}
        if hasattr(self._node, "aux_properties"):
            # Cast as list due to RuntimeError if a new property is added while running.
            for name, value in list(self._node.aux_properties.items()):
                attr_name = COMMAND_FRIENDLY_NAME.get(name, name)
                attr[attr_name] = str(value.formatted).lower()

        # If a Group/Scene, set a property if the entire scene is on/off
        if hasattr(self._node, "group_all_on"):
            attr["group_all_on"] = STATE_ON if self._node.group_all_on else STATE_OFF

        self._attrs.update(attr)
        return self._attrs

    async def async_send_node_command(self, command):
        """Respond to an entity service command call."""
        if not hasattr(self._node, command):
            raise HomeAssistantError(
                f"Invalid service call: {command} for device {self.entity_id}"
            )
        await getattr(self._node, command)()

    async def async_send_raw_node_command(
        self, command, value=None, unit_of_measurement=None, parameters=None
    ):
        """Respond to an entity service raw command call."""
        if not hasattr(self._node, "send_cmd"):
            raise HomeAssistantError(
                f"Invalid service call: {command} for device {self.entity_id}"
            )
        await self._node.send_cmd(command, value, unit_of_measurement, parameters)

    async def async_get_zwave_parameter(self, parameter):
        """Repsond to an entity service command to request a Z-Wave device parameter from the ISY."""
        if not hasattr(self._node, "protocol") or self._node.protocol != PROTO_ZWAVE:
            raise HomeAssistantError(
                f"Invalid service call: cannot request Z-Wave Parameter for non-Z-Wave device {self.entity_id}"
            )
        await self._node.get_zwave_parameter(parameter)

    async def async_set_zwave_parameter(self, parameter, value, size):
        """Repsond to an entity service command to set a Z-Wave device parameter via the ISY."""
        if not hasattr(self._node, "protocol") or self._node.protocol != PROTO_ZWAVE:
            raise HomeAssistantError(
                f"Invalid service call: cannot set Z-Wave Parameter for non-Z-Wave device {self.entity_id}"
            )
        await self._node.set_zwave_parameter(parameter, value, size)
        await self._node.get_zwave_parameter(parameter)

    async def async_rename_node(self, name):
        """Repsond to an entity service command to rename a node on the ISY."""
        await self._node.rename(name)


class ISYProgramEntity(ISYEntity):
    """Representation of an ISY994 program base."""

    def __init__(self, name: str, status, actions=None) -> None:
        """Initialize the ISY994 program-based entity."""
        super().__init__(status)
        self._name = name
        self._actions = actions

    @property
    def extra_state_attributes(self) -> dict:
        """Get the state attributes for the device."""
        attr = {}
        if self._actions:
            attr["actions_enabled"] = self._actions.enabled
            if self._actions.last_finished != EMPTY_TIME:
                attr["actions_last_finished"] = self._actions.last_finished
            if self._actions.last_run != EMPTY_TIME:
                attr["actions_last_run"] = self._actions.last_run
            if self._actions.last_update != EMPTY_TIME:
                attr["actions_last_update"] = self._actions.last_update
            attr["ran_else"] = self._actions.ran_else
            attr["ran_then"] = self._actions.ran_then
            attr["run_at_startup"] = self._actions.run_at_startup
            attr["running"] = self._actions.running
        attr["status_enabled"] = self._node.enabled
        if self._node.last_finished != EMPTY_TIME:
            attr["status_last_finished"] = self._node.last_finished
        if self._node.last_run != EMPTY_TIME:
            attr["status_last_run"] = self._node.last_run
        if self._node.last_update != EMPTY_TIME:
            attr["status_last_update"] = self._node.last_update
        return attr
