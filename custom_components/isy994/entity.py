"""Representation of ISYEntity Types."""

from pyisy.constants import (
    COMMAND_FRIENDLY_NAME,
    EVENT_PROPS_IGNORED,
    ISY_VALUE_UNKNOWN,
    PROTO_GROUP,
    PROTO_ZWAVE,
)
from pyisy.helpers import NodeProperty

from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import Dict

from .const import _LOGGER, DOMAIN


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
        self._change_handler = self._node.status_events.subscribe(self.on_update)

        if hasattr(self._node, "control_events"):
            self._control_handler = self._node.control_events.subscribe(self.on_control)

    def on_update(self, event: object) -> None:
        """Handle the update event from the ISY994 Node."""
        self.schedule_update_ha_state()

    def on_control(self, event: NodeProperty) -> None:
        """Handle a control event from the ISY994 Node."""
        event_data = {
            "entity_id": self.entity_id,
            "control": event.control,
            "value": event.value,
            "formatted": event.formatted,
            "uom": event.uom,
            "precision": event.prec,
        }

        if event.value is None or event.control not in EVENT_PROPS_IGNORED:
            # New state attributes may be available, update the state.
            self.schedule_update_ha_state()

        self.hass.bus.fire("isy994_control", event_data)

    @property
    def device_info(self):
        """Return the device_info of the device."""
        if hasattr(self._node, "protocol") and self._node.protocol == PROTO_GROUP:
            # not a device
            return None
        uuid = self._node.isy.configuration["uuid"]
        device_info = {
            "name": self.name,
            "identifiers": {},
            "model": "Unknown",
            "manufacturer": "Unknown",
            "via_device": (DOMAIN, uuid),
        }
        if hasattr(self._node, "address"):
            device_info["name"] += f" ({self._node.address})"
        if hasattr(self._node, "primary_node"):
            device_info["identifiers"] = {(DOMAIN, f"{uuid}_{self._node.primary_node}")}
        # ISYv5 Device Types
        if hasattr(self._node, "node_def_id") and self._node.node_def_id is not None:
            device_info["model"] = self._node.node_def_id
            # Numerical Device Type
            if hasattr(self._node, "type") and self._node.type is not None:
                device_info["model"] += f" {self._node.type}"
        if hasattr(self._node, "protocol"):
            device_info["manufacturer"] = self._node.protocol
            if self._node.protocol == PROTO_ZWAVE:
                device_info[
                    "manufacturer"
                ] += f" mfr_id:{self._node.zwave_props.mfr_id}"
                device_info["model"] += (
                    f" Type:{self._node.zwave_props.mfr_id} "
                    f"ProductTypeID:{self._node.zwave_props.prod_type_id} "
                    f"ProductID:{self._node.zwave_props.product_id}"
                )
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

    @property
    def value(self) -> int:
        """Get the current value of the device."""
        return self._node.status

    @property
    def state(self):
        """Return the state of the ISY device."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN
        return super().state


class ISYNodeEntity(ISYEntity):
    """Representation of a ISY Nodebase (Node/Group) entity."""

    @property
    def device_state_attributes(self) -> Dict:
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
            # pylint: disable=protected-access
            attr["group_all_on"] = "on" if self._node.group_all_on else "off"

        self._attrs.update(attr)
        return self._attrs

    def send_node_command(self, command):
        """Respond to an entity service command call."""
        if not hasattr(self._node, command):
            _LOGGER.error(
                "Invalid Service Call %s for device %s.", command, self.entity_id
            )
            return
        getattr(self._node, command)()

    def send_raw_node_command(
        self, command, value=None, unit_of_measurement=None, parameters=None
    ):
        """Respond to an entity service raw command call."""
        if not hasattr(self._node, "send_cmd"):
            _LOGGER.error(
                "Invalid Service Call %s for device %s.", command, self.entity_id
            )
            return
        self._node.send_cmd(command, value, unit_of_measurement, parameters)


class ISYProgramEntity(ISYEntity):
    """Representation of an ISY994 program base."""

    def __init__(self, name: str, node, actions=None) -> None:
        """Initialize the ISY994 program-based entity."""
        super().__init__(node)
        self._name = name
        self._actions = actions

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        attr = {}
        if self._actions:
            attr["actions_enabled"] = self._actions.enabled
            attr["actions_last_finished"] = self._actions.last_finished
            attr["actions_last_run"] = self._actions.last_run
            attr["actions_last_update"] = self._actions.last_update
            attr["ran_else"] = self._actions.ran_else
            attr["ran_then"] = self._actions.ran_then
            attr["run_at_startup"] = self._actions.run_at_startup
            attr["running"] = self._actions.running
        attr["status_enabled"] = self._node.enabled
        attr["status_last_finished"] = self._node.last_finished
        attr["status_last_run"] = self._node.last_run
        attr["status_last_update"] = self._node.last_update
        return attr
