"""Sorting helpers for ISY994 device classifications."""

from pyisy.constants import PROTO_GROUP, PROTO_INSTEON, PROTO_PROGRAM, PROTO_ZWAVE

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.climate.const import DOMAIN as CLIMATE
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.helpers.entity_registry import async_get_registry

from .const import (
    _LOGGER,
    DOMAIN,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_VARIABLES,
    ISY_BIN_SENS_DEVICE_TYPES,
    ISY_GROUP_PLATFORM,
    KEY_ACTIONS,
    KEY_FOLDER,
    KEY_MY_PROGRAMS,
    KEY_STATUS,
    NODE_FILTERS,
    SUPPORTED_PLATFORMS,
    SUPPORTED_PROGRAM_PLATFORMS,
    ZWAVE_BIN_SENS_DEVICE_TYPES,
)


def _check_for_node_def(hass_isy_data: dict, node, single_platform: str = None) -> bool:
    """Check if the node matches the node_def_id for any platforms.

    This is only present on the 5.0 ISY firmware, and is the most reliable
    way to determine a device's type.
    """
    if not hasattr(node, "node_def_id") or node.node_def_id is None:
        # Node doesn't have a node_def (pre 5.0 firmware most likely)
        return False

    node_def_id = node.node_def_id

    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_def_id in NODE_FILTERS[platform]["node_def_id"]:
            hass_isy_data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_insteon_type(
    hass_isy_data: dict, node, single_platform: str = None
) -> bool:
    """Check if the node matches the Insteon type for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Insteon device. "Node Server" (v5+) and Z-Wave and others will
    not have a type.
    """
    if not hasattr(node, "protocol") or node.protocol != PROTO_INSTEON:
        return False
    if not hasattr(node, "type") or node.type is None:
        # Node doesn't have a type (non-Insteon device most likely)
        return False

    device_type = node.type
    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if any(
            [
                device_type.startswith(t)
                for t in set(NODE_FILTERS[platform]["insteon_type"])
            ]
        ):

            # Hacky special-cases for certain devices with different platforms
            # included as subnodes. Note that special-cases are not necessary
            # on ISY 5.x firmware as it uses the superior NodeDefs method

            # FanLinc, which has a light module as one of its nodes.
            if platform == FAN and str(node.address[-1]) in ["1"]:
                hass_isy_data[ISY994_NODES][LIGHT].append(node)
                return True

            # Thermostats, which has a "Heat" and "Cool" sub-node on address 2 and 3
            if platform == CLIMATE and str(node.address[-1]) in ["2", "3"]:
                hass_isy_data[ISY994_NODES][BINARY_SENSOR].append(node)
                return True

            # IOLincs which have a sensor and relay on 2 different nodes
            if (
                platform == BINARY_SENSOR
                and device_type.startswith("7.")
                and str(node.address[-1]) in ["2"]
            ):
                hass_isy_data[ISY994_NODES][SWITCH].append(node)
                return True

            # Smartenit EZIO2X4
            if (
                platform == SWITCH
                and device_type.startswith("7.3.255.")
                and str(node.address[-1]) in ["9", "A", "B", "C"]
            ):
                hass_isy_data[ISY994_NODES][BINARY_SENSOR].append(node)
                return True

            hass_isy_data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_zwave_cat(
    hass_isy_data: dict, node, single_platform: str = None
) -> bool:
    """Check if the node matches the ISY Z-Wave Category for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Z-Wave Devices with the devtype.cat property.
    """
    if not hasattr(node, "protocol") or node.protocol != PROTO_ZWAVE:
        return False

    if not hasattr(node, "zwave_props") or node.zwave_props is None:
        # Node doesn't have a device type category (non-Z-Wave device)
        return False

    device_type = node.zwave_props.category
    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if any(
            [
                device_type.startswith(t)
                for t in set(NODE_FILTERS[platform]["zwave_cat"])
            ]
        ):

            hass_isy_data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_uom_id(
    hass_isy_data: dict, node, single_platform: str = None, uom_list: list = None
) -> bool:
    """Check if a node's uom matches any of the platforms uom filter.

    This is used for versions of the ISY firmware that report uoms as a single
    ID. We can often infer what type of device it is by that ID.
    """
    if not hasattr(node, "uom") or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))

    if uom_list:
        if node_uom.intersection(uom_list):
            hass_isy_data[ISY994_NODES][single_platform].append(node)
            return True
    else:
        platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
        for platform in platforms:
            if node_uom.intersection(NODE_FILTERS[platform]["uom"]):
                hass_isy_data[ISY994_NODES][platform].append(node)
                return True

    return False


def _check_for_states_in_uom(
    hass_isy_data: dict, node, single_platform: str = None, states_list: list = None
) -> bool:
    """Check if a list of uoms matches two possible filters.

    This is for versions of the ISY firmware that report uoms as a list of all
    possible "human readable" states. This filter passes if all of the possible
    states fit inside the given filter.
    """
    if not hasattr(node, "uom") or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))

    if states_list:
        if node_uom == set(states_list):
            hass_isy_data[ISY994_NODES][single_platform].append(node)
            return True
    else:
        platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
        for platform in platforms:
            if node_uom == set(NODE_FILTERS[platform]["states"]):
                hass_isy_data[ISY994_NODES][platform].append(node)
                return True

    return False


def _is_sensor_a_binary_sensor(hass_isy_data: dict, node) -> bool:
    """Determine if the given sensor node should be a binary_sensor."""
    if _check_for_node_def(hass_isy_data, node, single_platform=BINARY_SENSOR):
        return True
    if _check_for_insteon_type(hass_isy_data, node, single_platform=BINARY_SENSOR):
        return True

    # For the next two checks, we're providing our own set of uoms that
    # represent on/off devices. This is because we can only depend on these
    # checks in the context of already knowing that this is definitely a
    # sensor device.
    if _check_for_uom_id(
        hass_isy_data, node, single_platform=BINARY_SENSOR, uom_list=["2", "78"]
    ):
        return True
    if _check_for_states_in_uom(
        hass_isy_data, node, single_platform=BINARY_SENSOR, states_list=["on", "off"]
    ):
        return True

    return False


def _categorize_nodes(
    hass_isy_data: dict, nodes, ignore_identifier: str, sensor_identifier: str
) -> None:
    """Sort the nodes to their proper platforms."""
    for (path, node) in nodes:
        ignored = ignore_identifier in path or ignore_identifier in node.name
        if ignored:
            # Don't import this node as a device at all
            continue

        if hasattr(node, "protocol") and node.protocol == PROTO_GROUP:
            hass_isy_data[ISY994_NODES][ISY_GROUP_PLATFORM].append(node)
            continue

        if sensor_identifier in path or sensor_identifier in node.name:
            # User has specified to treat this as a sensor. First we need to
            # determine if it should be a binary_sensor.
            if _is_sensor_a_binary_sensor(hass_isy_data, node):
                continue
            hass_isy_data[ISY994_NODES][SENSOR].append(node)
            continue

        # We have a bunch of different methods for determining the device type,
        # each of which works with different ISY firmware versions or device
        # family. The order here is important, from most reliable to least.
        if _check_for_node_def(hass_isy_data, node):
            continue
        if _check_for_insteon_type(hass_isy_data, node):
            continue
        if _check_for_zwave_cat(hass_isy_data, node):
            continue
        if _check_for_uom_id(hass_isy_data, node):
            continue
        if _check_for_states_in_uom(hass_isy_data, node):
            continue


def _categorize_programs(hass_isy_data: dict, programs: dict) -> None:
    """Categorize the ISY994 programs."""
    for platform in SUPPORTED_PROGRAM_PLATFORMS:
        try:
            folder = programs[KEY_MY_PROGRAMS][f"HA.{platform}"]
        except KeyError:
            pass
        else:
            for dtype, _, node_id in folder.children:
                if dtype != KEY_FOLDER:
                    continue
                entity_folder = folder[node_id]
                try:
                    status = entity_folder[KEY_STATUS]
                    assert status.dtype == PROTO_PROGRAM, "Not a program"
                    if platform != BINARY_SENSOR:
                        actions = entity_folder[KEY_ACTIONS]
                        assert actions.dtype == PROTO_PROGRAM, "Not a program"
                    else:
                        actions = None
                except (AttributeError, KeyError, AssertionError):
                    _LOGGER.warning(
                        "Program entity '%s' not loaded due "
                        "to invalid folder structure.",
                        entity_folder.name,
                    )
                    continue

                entity = (entity_folder.name, status, actions)
                hass_isy_data[ISY994_PROGRAMS][platform].append(entity)


def _categorize_variables(hass_isy_data: dict, variables, identifier: str) -> None:
    """Gather the ISY994 Variables to be added as sensors."""
    try:
        var_to_add = [
            (vtype, vname, vid)
            for (vtype, vname, vid) in variables.children
            if identifier in vname
        ]
    except KeyError as err:
        _LOGGER.error("Error adding ISY Variables: %s", err)
    else:
        for vtype, vname, vid in var_to_add:
            hass_isy_data[ISY994_VARIABLES].append((vname, variables[vtype][vid]))


def _detect_device_type_and_class(node) -> (str, str):
    try:
        device_type = node.type
    except AttributeError:
        # The type attribute didn't exist in the ISY's API response
        return (None, None)

    # Z-Wave Devices:
    if node.protocol == PROTO_ZWAVE:
        device_type = "Z{}".format(node.zwave_props.category)
        for device_class in [*ZWAVE_BIN_SENS_DEVICE_TYPES]:
            if node.zwave_props.category in ZWAVE_BIN_SENS_DEVICE_TYPES[device_class]:
                return device_class, device_type
    else:  # Other devices (incl Insteon.)
        for device_class in [*ISY_BIN_SENS_DEVICE_TYPES]:
            if any(
                [
                    device_type.startswith(t)
                    for t in set(ISY_BIN_SENS_DEVICE_TYPES[device_class])
                ]
            ):
                return device_class, device_type

    return (None, device_type)


async def migrate_old_unique_ids(hass, platform, devices):
    """Migrate to new controller-specific unique ids."""
    registry = await async_get_registry(hass)

    for device in devices:
        old_entity_id = registry.async_get_entity_id(
            platform, DOMAIN, device.old_unique_id
        )
        if old_entity_id is not None:
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                device.old_unique_id,
                device.unique_id,
            )
            registry.async_update_entity(old_entity_id, new_unique_id=device.unique_id)

        old_entity_id_2 = registry.async_get_entity_id(
            platform, DOMAIN, device.unique_id.replace(":", "")
        )
        if old_entity_id_2 is not None:
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                device.unique_id.replace(":", ""),
                device.unique_id,
            )
            registry.async_update_entity(
                old_entity_id_2, new_unique_id=device.unique_id
            )
