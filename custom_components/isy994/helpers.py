"""Sorting helpers for ISY device classifications."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, cast

from pyisyox.constants import (
    BACKLIGHT_SUPPORT,
    CMD_BACKLIGHT,
    PROP_BUSY,
    PROP_COMMS_ERROR,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
    TAG_ENABLED,
    UOM_INDEX,
    Protocol,
)
from pyisyox.nodes import Group, Node, Nodes
from pyisyox.programs import Programs
from pyisyox.variables import Variables

from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, Platform
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    _LOGGER,
    CONF_ENABLE_NODESERVERS,
    CONF_IGNORE_STRING,
    CONF_SENSOR_STRING,
    DEFAULT_IGNORE_STRING,
    DEFAULT_PROGRAM_STRING,
    DEFAULT_SENSOR_STRING,
    DOMAIN,
    FILTER_INSTEON_TYPE,
    FILTER_NODE_DEF_ID,
    FILTER_STATES,
    FILTER_UOM,
    FILTER_ZWAVE_CAT,
    KEY_ACTIONS,
    KEY_STATUS,
    NODE_AUX_FILTERS,
    NODE_FILTERS,
    NODE_PLATFORMS,
    PROGRAM_PLATFORMS,
    SUBNODE_CLIMATE_COOL,
    SUBNODE_CLIMATE_HEAT,
    SUBNODE_EZIO2X4_SENSORS,
    SUBNODE_FANLINC_LIGHT,
    SUBNODE_IOLINC_RELAY,
    TYPE_CATEGORY_SENSOR_ACTUATORS,
    TYPE_EZIO2X4,
    UOM_DOUBLE_TEMP,
    UOM_ISYV4_DEGREES,
)
from .models import IsyData

BINARY_SENSOR_UOMS = ["2", "78"]
BINARY_SENSOR_ISY_STATES = ["on", "off"]
ROOT_AUX_CONTROLS = {
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
}
SKIP_AUX_PROPS = {PROP_BUSY, PROP_COMMS_ERROR, PROP_STATUS, *ROOT_AUX_CONTROLS}


def _check_for_node_def(
    isy_data: IsyData, node: Node, single_platform: Platform | None = None
) -> bool:
    """Check if the node matches the node_def_id for any platforms.

    This is only present on the 5.0 ISY firmware, and is the most reliable
    way to determine a device's type.
    """
    if not hasattr(node, "node_def_id") or node.node_def_id is None:
        # Node doesn't have a node_def (pre 5.0 firmware most likely)
        return False

    node_def_id = node.node_def_id

    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_def_id in NODE_FILTERS[platform][FILTER_NODE_DEF_ID]:
            isy_data.nodes[platform].append(node)
            return True

    return False


def _check_for_node_server_def(isy_data: IsyData, node: Node) -> bool:
    """Check if the node is a Node Server node with assigned platforms.

    Node Servers can provide their own definitions of devices so we
    test what they support if advanced configuration is enabled.
    """
    # FUTURE: Move sorting here to check for binary_sensor, sensor, switch
    return False


def _check_for_insteon_type(
    isy_data: IsyData, node: Node, single_platform: Platform | None = None
) -> bool:
    """Check if the node matches the Insteon type for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Insteon device. "Node Server" (v5+) and Z-Wave and others will
    not have a type.
    """
    if node.protocol != Protocol.INSTEON:
        return False
    if not hasattr(node, "type") or node.type_ is None:
        # Node doesn't have a type (non-Insteon device most likely)
        return False

    device_type = node.type_
    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if any(
            device_type.startswith(t)
            for t in set(NODE_FILTERS[platform][FILTER_INSTEON_TYPE])
        ):
            # Hacky special-cases for certain devices with different platforms
            # included as subnodes. Note that special-cases are not necessary
            # on ISY 5.x firmware as it uses the superior NodeDefs method
            subnode_id = int(node.address.split(" ")[-1], 16)

            # FanLinc, which has a light module as one of its nodes.
            if platform == Platform.FAN and subnode_id == SUBNODE_FANLINC_LIGHT:
                isy_data.nodes[Platform.LIGHT].append(node)
                return True

            # Thermostats, which has a "Heat" and "Cool" sub-node on address 2 and 3
            if platform == Platform.CLIMATE and subnode_id in (
                SUBNODE_CLIMATE_COOL,
                SUBNODE_CLIMATE_HEAT,
            ):
                isy_data.nodes[Platform.BINARY_SENSOR].append(node)
                return True

            # IOLincs which have a sensor and relay on 2 different nodes
            if (
                platform == Platform.BINARY_SENSOR
                and device_type.startswith(TYPE_CATEGORY_SENSOR_ACTUATORS)
                and subnode_id == SUBNODE_IOLINC_RELAY
            ):
                isy_data.nodes[Platform.SWITCH].append(node)
                return True

            # Smartenit EZIO2X4
            if (
                platform == Platform.SWITCH
                and device_type.startswith(TYPE_EZIO2X4)
                and subnode_id in SUBNODE_EZIO2X4_SENSORS
            ):
                isy_data.nodes[Platform.BINARY_SENSOR].append(node)
                return True

            isy_data.nodes[platform].append(node)
            return True

    return False


def _check_for_zwave_cat(
    isy_data: IsyData, node: Node, single_platform: Platform | None = None
) -> bool:
    """Check if the node matches the ISY Z-Wave Category for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Z-Wave Devices with the devtype.cat property.
    """
    if node.protocol != Protocol.ZWAVE:
        return False

    if not hasattr(node, "zwave_props") or node.zwave_props is None:
        # Node doesn't have a device type category (non-Z-Wave device)
        return False

    device_type = node.zwave_props.category
    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if any(
            device_type.startswith(t)
            for t in set(NODE_FILTERS[platform][FILTER_ZWAVE_CAT])
        ):
            isy_data.nodes[platform].append(node)
            return True

    return False


def _check_for_uom_id(
    isy_data: IsyData,
    node: Node,
    single_platform: Platform | None = None,
    uom_list: list[str] | None = None,
) -> bool:
    """Check if a node's uom matches any of the platforms uom filter.

    This is used for versions of the ISY firmware that report uoms as a single
    ID. We can often infer what type of device it is by that ID.
    """
    if not hasattr(node, "uom") or node.uom in (None, ""):
        # Node doesn't have a uom (Scenes for example)
        return False

    # Backwards compatibility for ISYv4 Firmware:
    node_uom = node.uom
    if isinstance(node.uom, list):
        node_uom = node.uom[0]

    if uom_list and single_platform:
        if node_uom in uom_list:
            isy_data.nodes[single_platform].append(node)
            return True
        return False

    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_uom in NODE_FILTERS[platform][FILTER_UOM]:
            isy_data.nodes[platform].append(node)
            return True

    return False


def _check_for_states_in_uom(
    isy_data: IsyData,
    node: Node,
    single_platform: Platform | None = None,
    states_list: list[str] | None = None,
) -> bool:
    """Check if a list of uoms matches two possible filters.

    This is for versions of the ISY firmware that report uoms as a list of all
    possible "human readable" states. This filter passes if all of the possible
    states fit inside the given filter.
    """
    if not hasattr(node, "uom") or node.uom in (None, ""):
        # Node doesn't have a uom (Scenes for example)
        return False

    # This only works for ISYv4 Firmware where uom is a list of states:
    if not isinstance(node.uom, list):
        return False

    node_uom = set(map(str.lower, node.uom))

    if states_list and single_platform:
        if node_uom == set(states_list):
            isy_data.nodes[single_platform].append(node)
            return True
        return False

    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_uom == set(NODE_FILTERS[platform][FILTER_STATES]):
            isy_data.nodes[platform].append(node)
            return True

    return False


def _is_sensor_a_binary_sensor(isy_data: IsyData, node: Node) -> bool:
    """Determine if the given sensor node should be a binary_sensor."""
    if _check_for_node_def(isy_data, node, single_platform=Platform.BINARY_SENSOR):
        return True
    if _check_for_insteon_type(isy_data, node, single_platform=Platform.BINARY_SENSOR):
        return True

    # For the next two checks, we're providing our own set of uoms that
    # represent on/off devices. This is because we can only depend on these
    # checks in the context of already knowing that this is definitely a
    # sensor device.
    if _check_for_uom_id(
        isy_data,
        node,
        single_platform=Platform.BINARY_SENSOR,
        uom_list=BINARY_SENSOR_UOMS,
    ):
        return True
    if _check_for_states_in_uom(
        isy_data,
        node,
        single_platform=Platform.BINARY_SENSOR,
        states_list=BINARY_SENSOR_ISY_STATES,
    ):
        return True

    return False


def _add_backlight_if_supported(isy_data: IsyData, node: Node) -> None:
    """Check if a node supports setting a backlight and add entity."""
    if (not getattr(node, "is_backlight_supported", False)) or not node.node_def_id:
        return
    if BACKLIGHT_SUPPORT[node.node_def_id] == UOM_INDEX:
        isy_data.aux_properties[Platform.SELECT].append((node, CMD_BACKLIGHT))
        return
    isy_data.aux_properties[Platform.NUMBER].append((node, CMD_BACKLIGHT))


def _generate_device_info(node: Node) -> DeviceInfo:
    """Generate the device info for a root node device."""
    isy = node.isy
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{isy.uuid}_{node.address}")},
        manufacturer=node.protocol.name.replace("_", " ").title(),
        name=node.name,
        via_device=(DOMAIN, isy.uuid),
        configuration_url=isy.conn.url,
        suggested_area=isy.nodes.get_folder(node.address),
    )

    # ISYv5 Device Types can provide model and manufacturer
    model: str = str(node.address).rpartition(" ")[0] or node.address
    if node.node_def_id is not None:
        model += f": {node.node_def_id}"

    # Numerical Device Type
    if node.type_ is not None:
        model += f" ({node.type_})"

    # Get extra information for Z-Wave Devices
    if (
        node.protocol == Protocol.ZWAVE
        and node.zwave_props is not None
        and node.zwave_props.mfr_id != "0x0000"
    ):
        device_info[ATTR_MANUFACTURER] = f"Z-Wave MfrID:{node.zwave_props.mfr_id}"
        model += (
            f"Type:{node.zwave_props.prod_type_id} "
            f"Product:{node.zwave_props.product_id}"
        )
    device_info[ATTR_MODEL] = model

    return device_info


def _categorize_nodes(
    isy_data: IsyData, nodes: Nodes, isy_options: MappingProxyType[str, Any]
) -> None:
    """Sort the nodes to their proper platforms."""
    ignore_identifier = isy_options.get(CONF_IGNORE_STRING, DEFAULT_IGNORE_STRING)
    sensor_identifier = isy_options.get(CONF_SENSOR_STRING, DEFAULT_SENSOR_STRING)
    enable_nodeservers = isy_options.get(CONF_ENABLE_NODESERVERS, False)
    directory = nodes.get_directory()
    for path, node in directory.items():
        if ignore_identifier in path or node.protocol == Protocol.NODE_FOLDER:
            # Don't import this node as a device at all
            continue

        if isinstance(node, Node) and node.is_device_root:
            # This is a physical device / parent node
            isy_data.devices[node.address] = _generate_device_info(node)
            isy_data.root_nodes[Platform.BUTTON].append(node)
            # Any parent node can have communication errors:
            isy_data.aux_properties[Platform.SENSOR].append((node, PROP_COMMS_ERROR))
            # Add Ramp Rate and On Levels for Dimmable Load devices
            if getattr(node, "is_dimmable", False):
                aux_controls = ROOT_AUX_CONTROLS.intersection(node.aux_properties)
                for control in aux_controls:
                    platform = NODE_AUX_FILTERS[control]
                    isy_data.aux_properties[platform].append((node, control))
            if hasattr(node, TAG_ENABLED):
                isy_data.aux_properties[Platform.SWITCH].append((node, TAG_ENABLED))
            _add_backlight_if_supported(isy_data, node)

        if isinstance(node, Group):
            isy_data.groups.append(node)
            continue

        for control in node.aux_properties:
            if control in SKIP_AUX_PROPS:
                continue
            platform = Platform.SENSOR
            if node.aux_properties[control].uom in BINARY_SENSOR_UOMS:
                platform = Platform.BINARY_SENSOR
            isy_data.aux_properties[platform].append((node, control))

        if sensor_identifier in path or sensor_identifier in node.name:
            # User has specified to treat this as a sensor. First we need to
            # determine if it should be a binary_sensor.
            if _is_sensor_a_binary_sensor(isy_data, node):
                continue
            isy_data.nodes[Platform.SENSOR].append(node)
            continue

        # We have a bunch of different methods for determining the device type,
        # each of which works with different ISY firmware versions or device
        # family. The order here is important, from most reliable to least.
        if _check_for_node_def(isy_data, node):
            continue
        if _check_for_insteon_type(isy_data, node):
            continue
        if _check_for_zwave_cat(isy_data, node):
            continue
        if enable_nodeservers and _check_for_node_server_def(isy_data, node):
            continue
        if _check_for_uom_id(isy_data, node):
            continue
        if _check_for_states_in_uom(isy_data, node):
            continue

        # Fallback as as sensor, e.g. for un-sortable items like NodeServer nodes.
        isy_data.nodes[Platform.SENSOR].append(node)


def _categorize_programs(isy_data: IsyData, programs: Programs) -> None:
    """Categorize the ISY programs."""
    directory = programs.get_directory()
    for platform in PROGRAM_PLATFORMS:
        folder_name = f"{DEFAULT_PROGRAM_STRING}{platform}/"
        try:
            entities = {
                path.partition(folder_name)[2]: entity
                for path, entity in directory.items()
                if folder_name in path
            }
        except KeyError:
            continue

        if not entities:
            continue

        status_programs = {
            path.rstrip(f"/{KEY_STATUS}"): status
            for path, status in entities.items()
            if path.endswith(KEY_STATUS)
        }
        action_programs = {
            path.rstrip(f"/{KEY_ACTIONS}"): action
            for path, action in entities.items()
            if path.endswith(KEY_ACTIONS)
        }

        for name, program in status_programs.items():
            if platform != Platform.BINARY_SENSOR and name not in action_programs:
                _LOGGER.warning(
                    (
                        "Program %s entity '%s' not loaded, invalid/missing actions"
                        " program"
                    ),
                    platform,
                    name,
                )
            entity = (name, program, action_programs.get(name))
            isy_data.programs[platform].append(entity)


def _categorize_variables(
    isy_data: IsyData, variables: Variables, identifier: str
) -> None:
    """Gather the ISY Variables to be added as sensors."""
    try:
        if not (variables.loaded and variables.entities):
            return

        numbers = isy_data.variables[Platform.NUMBER]
        for variable in variables.values():
            numbers.append(variable)
    except KeyError as err:
        _LOGGER.error("Error adding ISY Variables: %s", err)


def convert_isy_value_to_hass(
    value: int | float | None,
    uom: str | list | None,
    precision: int | str,
    fallback_precision: int | None = None,
) -> float | int | None:
    """Fix ISY Reported Values.

    ISY provides float values as an integer and precision component.
    Correct by shifting the decimal place left by the value of precision.
    (e.g. value=2345, prec="2" == 23.45)

    Insteon Thermostats report temperature in 0.5-deg precision as an int
    by sending a value of 2 times the Temp. Correct by dividing by 2 here.
    """
    if value is None or value is None:
        return None
    if uom in (UOM_DOUBLE_TEMP, UOM_ISYV4_DEGREES):
        return round(float(value) / 2.0, 1)
    if precision not in ("0", 0):
        return cast(float, round(float(value) / 10 ** int(precision), int(precision)))
    if fallback_precision:
        return round(float(value), fallback_precision)
    return value
