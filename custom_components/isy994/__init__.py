"""Support the ISY-994 controllers."""
import asyncio
from functools import partial
from typing import Optional
from urllib.parse import urlparse

from pyisy import ISY
from pyisy.constants import (
    COMMAND_FRIENDLY_NAME,
    EVENT_PROPS_IGNORED,
    ISY_VALUE_UNKNOWN,
    PROTO_GROUP,
    PROTO_INSTEON,
    PROTO_PROGRAM,
    PROTO_ZWAVE,
)
from pyisy.helpers import NodeProperty
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DCS,
    DOMAIN as PLATFORM_BINARY_SENSOR,
)
from homeassistant.components.climate.const import DOMAIN as PLATFORM_CLIMATE
from homeassistant.components.fan import DOMAIN as PLATFORM_FAN
from homeassistant.components.light import DOMAIN as PLATFORM_LIGHT
from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA as SENSOR_DCS,
    DOMAIN as PLATFORM_SENSOR,
)
from homeassistant.components.switch import DOMAIN as PLATFORM_SWITCH
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.typing import ConfigType, Dict

from .const import (
    _LOGGER,
    CONF_IGNORE_STRING,
    CONF_ISY_VARIABLES,
    CONF_SENSOR_STRING,
    CONF_TLS_VER,
    DEFAULT_IGNORE_STRING,
    DEFAULT_OFF_VALUE,
    DEFAULT_ON_VALUE,
    DEFAULT_SENSOR_STRING,
    DOMAIN,
    ISY994_ISY,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_VARIABLES,
    ISY_GROUP_PLATFORM,
    KEY_ACTIONS,
    KEY_FOLDER,
    KEY_MY_PROGRAMS,
    KEY_STATUS,
    MANUFACTURER,
    NODE_FILTERS,
    SUPPORTED_PLATFORMS,
    SUPPORTED_PROGRAM_PLATFORMS,
    SUPPORTED_VARIABLE_PLATFORMS,
    UNDO_UPDATE_LISTENER,
)
from .services import async_setup_services, async_unload_services

VAR_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_TYPE): vol.All(cv.positive_int, vol.In([1, 2])),
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_NAME): cv.string,
    }
)

SENSOR_VAR_SCHEMA = VAR_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): SENSOR_DCS,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)

BINARY_SENSOR_VAR_SCHEMA = VAR_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DCS,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_ON_VALUE): vol.Coerce(int),
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_OFF_VALUE): vol.Coerce(int),
    }
)

SWITCH_VAR_SCHEMA = VAR_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_ON_VALUE): vol.Coerce(int),
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_OFF_VALUE): vol.Coerce(int),
    }
)

ISY_VARIABLES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SENSORS, default=[]): vol.All(
            cv.ensure_list, [SENSOR_VAR_SCHEMA]
        ),
        vol.Optional(CONF_BINARY_SENSORS, default=[]): vol.All(
            cv.ensure_list, [BINARY_SENSOR_VAR_SCHEMA]
        ),
        vol.Optional(CONF_SWITCHES, default=[]): vol.All(
            cv.ensure_list, [SWITCH_VAR_SCHEMA]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.url,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TLS_VER): vol.Coerce(float),
                vol.Optional(
                    CONF_IGNORE_STRING, default=DEFAULT_IGNORE_STRING
                ): cv.string,
                vol.Optional(
                    CONF_SENSOR_STRING, default=DEFAULT_SENSOR_STRING
                ): cv.string,
                vol.Optional(CONF_ISY_VARIABLES, default={}): ISY_VARIABLES_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
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
            if platform == PLATFORM_FAN and str(node.address[-1]) in ["1"]:
                hass_isy_data[ISY994_NODES][PLATFORM_LIGHT].append(node)
                return True

            # Thermostats, which has a "Heat" and "Cool" sub-node on address 2 and 3
            if platform == PLATFORM_CLIMATE and str(node.address[-1]) in ["2", "3"]:
                hass_isy_data[ISY994_NODES][PLATFORM_BINARY_SENSOR].append(node)
                return True

            # IOLincs which have a sensor and relay on 2 different nodes
            if (
                platform == PLATFORM_BINARY_SENSOR
                and device_type.startswith("7.")
                and str(node.address[-1]) in ["2"]
            ):
                hass_isy_data[ISY994_NODES][PLATFORM_SWITCH].append(node)

            # Smartenit EZIO2X4
            if (
                platform == PLATFORM_SWITCH
                and device_type.startswith("7.3.255.")
                and str(node.address[-1]) in ["9", "A", "B", "C"]
            ):
                hass_isy_data[ISY994_NODES][PLATFORM_BINARY_SENSOR].append(node)

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
    if _check_for_node_def(hass_isy_data, node, single_platform=PLATFORM_BINARY_SENSOR):
        return True
    if _check_for_insteon_type(
        hass_isy_data, node, single_platform=PLATFORM_BINARY_SENSOR
    ):
        return True

    # For the next two checks, we're providing our own set of uoms that
    # represent on/off devices. This is because we can only depend on these
    # checks in the context of already knowing that this is definitely a
    # sensor device.
    if _check_for_uom_id(
        hass_isy_data,
        node,
        single_platform=PLATFORM_BINARY_SENSOR,
        uom_list=["2", "78"],
    ):
        return True
    if _check_for_states_in_uom(
        hass_isy_data,
        node,
        single_platform=PLATFORM_BINARY_SENSOR,
        states_list=["on", "off"],
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
            hass_isy_data[ISY994_NODES][PLATFORM_SENSOR].append(node)
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
                    if platform != PLATFORM_BINARY_SENSOR:
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


def _categorize_variables(
    hass_isy_data: dict, variables, platform_cfg: dict, platform: str
) -> None:
    """Categorize the ISY994 Variables."""
    if platform_cfg is None:
        return
    for isy_var in platform_cfg:
        vid = isy_var.get(CONF_ID)
        vtype = isy_var.get(CONF_TYPE)
        vname = ""
        try:
            vname = variables[vtype][vid].name
        except KeyError as err:
            _LOGGER.error("Error adding ISY Variable %s.%s: %s", vtype, vid, err)
            continue
        else:
            variable = (isy_var, vname, variables[vtype][vid])
            hass_isy_data[ISY994_VARIABLES][platform].append(variable)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the isy994 component from YAML."""
    isy_config: Optional[ConfigType] = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})
    config_entry = _async_find_matching_config_entry(hass)

    if not isy_config:
        if config_entry:
            # Config entry was created because user had configuration.yaml entry
            # They removed that, so remove entry.
            await hass.config_entries.async_remove(config_entry.entry_id)
        return True

    # Only import if we haven't before.
    if not config_entry:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=dict(isy_config),
            )
        )
        return True

    # Update the entry based on the YAML configuration, in case it changed.
    hass.config_entries.async_update_entry(config_entry, data=dict(isy_config))
    return True


@callback
def _async_find_matching_config_entry(hass):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.source == config_entries.SOURCE_IMPORT:
            return entry


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up the ISY 994 platform."""
    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options
    _async_import_options_from_data_if_missing(hass, entry)

    hass.data[DOMAIN][entry.entry_id] = {}
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]

    hass_isy_data[ISY994_NODES] = {}
    for platform in SUPPORTED_PLATFORMS:
        hass_isy_data[ISY994_NODES][platform] = []

    hass_isy_data[ISY994_PROGRAMS] = {}
    for platform in SUPPORTED_PLATFORMS:
        hass_isy_data[ISY994_PROGRAMS][platform] = []

    hass_isy_data[ISY994_VARIABLES] = {}
    for platform in SUPPORTED_VARIABLE_PLATFORMS:
        hass_isy_data[ISY994_VARIABLES][platform] = []

    isy_config = entry.data
    isy_options = entry.options

    # Required
    user = isy_config[CONF_USERNAME]
    password = isy_config[CONF_PASSWORD]
    host = urlparse(isy_config[CONF_HOST])

    # Optional
    tls_version = isy_config.get(CONF_TLS_VER)
    ignore_identifier = isy_options.get(CONF_IGNORE_STRING, DEFAULT_IGNORE_STRING)
    sensor_identifier = isy_options.get(CONF_SENSOR_STRING, DEFAULT_SENSOR_STRING)
    isy_variables = isy_config.get(CONF_ISY_VARIABLES, {})

    if host.scheme == "http":
        https = False
        port = host.port or 80
    elif host.scheme == "https":
        https = True
        port = host.port or 443
    else:
        _LOGGER.error("isy994 host value in configuration is invalid")
        return False

    # Connect to ISY controller.
    isy = await hass.async_add_executor_job(
        partial(
            ISY,
            host.hostname,
            port,
            username=user,
            password=password,
            use_https=https,
            tls_ver=tls_version,
            log=_LOGGER,
            webroot=host.path,
        )
    )
    if not isy.connected:
        return False

    _categorize_nodes(hass_isy_data, isy.nodes, ignore_identifier, sensor_identifier)
    _categorize_programs(hass_isy_data, isy.programs)
    _categorize_variables(
        hass_isy_data, isy.variables, isy_variables.get(CONF_SENSORS), PLATFORM_SENSOR
    )
    _categorize_variables(
        hass_isy_data,
        isy.variables,
        isy_variables.get(CONF_BINARY_SENSORS),
        PLATFORM_BINARY_SENSOR,
    )
    _categorize_variables(
        hass_isy_data, isy.variables, isy_variables.get(CONF_SWITCHES), PLATFORM_SWITCH
    )

    # Dump ISY Clock Information. Future: Add ISY as sensor to Hass with attrs
    _LOGGER.info(repr(isy.clock))

    hass_isy_data[ISY994_ISY] = isy
    await _async_get_or_create_isy_device_in_registry(hass, entry, isy)

    # Load platforms for the devices in the ISY controller that we support.
    for component in SUPPORTED_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    def _start_auto_update() -> None:
        """Start isy auto update."""
        _LOGGER.debug("ISY Starting Event Stream and automatic updates.")
        isy.auto_update = True

    await hass.async_add_executor_job(_start_auto_update)

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass_isy_data[UNDO_UPDATE_LISTENER] = undo_listener

    # Register Integration-wide Services:
    async_setup_services(hass)

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
):
    options = dict(entry.options)
    modified = False
    for importable_option in [CONF_IGNORE_STRING, CONF_SENSOR_STRING]:
        if importable_option not in entry.options and importable_option in entry.data:
            options[importable_option] = entry.data[importable_option]
            modified = True

    if modified:
        hass.config_entries.async_update_entry(entry, options=options)


async def _async_get_or_create_isy_device_in_registry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry, isy
) -> None:
    device_registry = await dr.async_get_registry(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, isy.configuration["uuid"])},
        identifiers={(DOMAIN, isy.configuration["uuid"])},
        manufacturer=MANUFACTURER,
        name=isy.configuration["name"],  # Exposed in PyISY-beta v2.0.0.dev136
        model=isy.configuration["model"],  # Exposed in PyISY-beta v2.0.0.dev135
        sw_version=isy.configuration["firmware"],
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in SUPPORTED_PLATFORMS
            ]
        )
    )

    hass_isy_data = hass.data[DOMAIN][entry.entry_id]

    isy = hass_isy_data[ISY994_ISY]

    def _stop_auto_update() -> None:
        """Start isy auto update."""
        _LOGGER.debug("ISY Stopping Event Stream and automatic updates.")
        isy.auto_update = False

    await hass.async_add_executor_job(_stop_auto_update)

    hass_isy_data[UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    async_unload_services(hass)

    return unload_ok


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
    def icon(self) -> str:
        """Get the icon for programs."""
        return "mdi:script-text-outline"  # Matches isy program icon

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


class ISYVariableEntity(ISYEntity):
    """Representation of an ISY994 variable-based entity."""

    def __init__(self, vcfg: dict, vname: str, vobj: object) -> None:
        """Initialize the ISY994 binary sensor program."""
        super().__init__(vobj)
        self._config = vcfg
        self._name = vcfg.get(CONF_NAME, vname)
        self._vtype = vcfg.get(CONF_TYPE)
        self._vid = vcfg.get(CONF_ID)

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        return {"init_value": int(self._node.init)}

    @property
    def icon(self):
        """Return the icon."""
        if self._config.get(CONF_ICON):
            return self._config.get(CONF_ICON)
        return "mdi:counter"
