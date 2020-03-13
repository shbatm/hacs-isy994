"""Support the ISY-994 controllers."""
import asyncio
from collections import namedtuple
import logging
from urllib.parse import urlparse

from pyisy import ISY
from pyisy.constants import (
    COMMAND_FRIENDLY_NAME,
    EVENT_PROPS_IGNORED,
    ISY_VALUE_UNKNOWN,
    PROTO_GROUP,
    PROTO_INSTEON,
    PROTO_ZWAVE,
)
from pyisy.helpers import NodeProperty
from pyisy.nodes import Group
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DCS,
)
from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA as SENSOR_DCS
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
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
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import Dict

from .const import (
    CONF_ENABLE_CLIMATE,
    CONF_IGNORE_STRING,
    CONF_ISY_VARIABLES,
    CONF_SENSOR_STRING,
    CONF_TLS_VER,
    DEFAULT_IGNORE_STRING,
    DEFAULT_OFF_VALUE,
    DEFAULT_ON_VALUE,
    DEFAULT_SENSOR_STRING,
    DOMAIN,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_VARIABLES,
    ISY994_WEATHER,
    KEY_ACTIONS,
    KEY_FOLDER,
    KEY_MY_PROGRAMS,
    KEY_STATUS,
    NODE_FILTERS,
    SCENE_DOMAIN,
    SUPPORTED_DOMAINS,
    SUPPORTED_PROGRAM_DOMAINS,
    SUPPORTED_VARIABLE_DOMAINS,
)

_LOGGER = logging.getLogger(__name__)

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
                vol.Optional(CONF_ENABLE_CLIMATE, default=True): cv.boolean,
                vol.Optional(CONF_ISY_VARIABLES, default={}): ISY_VARIABLES_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

WeatherNode = namedtuple("WeatherNode", ("status", "name", "uom"))


def _check_for_node_def(
    hass: HomeAssistant, entry: ConfigEntry, node, single_domain: str = None
) -> bool:
    """Check if the node matches the node_def_id for any domains.

    This is only present on the 5.0 ISY firmware, and is the most reliable
    way to determine a device's type.
    """
    if not hasattr(node, "node_def_id") or node.node_def_id is None:
        # Node doesn't have a node_def (pre 5.0 firmware most likely)
        return False

    node_def_id = node.node_def_id
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]

    domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
    for domain in domains:
        if node_def_id in NODE_FILTERS[domain]["node_def_id"]:
            hass_isy_data[ISY994_NODES][domain].append(node)
            return True

    return False


def _check_for_insteon_type(
    hass: HomeAssistant, entry: ConfigEntry, node, single_domain: str = None
) -> bool:
    """Check if the node matches the Insteon type for any domains.

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
    domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]
    for domain in domains:
        if any(
            [
                device_type.startswith(t)
                for t in set(NODE_FILTERS[domain]["insteon_type"])
            ]
        ):

            # Hacky special-cases for certain devices with different domains
            # included as subnodes. Note that special-cases are not necessary
            # on ISY 5.x firmware as it uses the superior NodeDefs method

            # FanLinc, which has a light module as one of its nodes.
            if domain == "fan" and str(node.address[-1]) in ["1"]:
                hass_isy_data[ISY994_NODES]["light"].append(node)
                return True

            # Thermostats, which has a "Heat" and "Cool" sub-node on address 2 and 3
            if domain == "climate" and str(node.address[-1]) in ["2", "3"]:
                hass_isy_data[ISY994_NODES]["binary_sensor"].append(node)
                return True

            # IOLincs which have a sensor and relay on 2 different nodes
            if (
                domain == "binary_sensor"
                and device_type.startswith("7.")
                and str(node.address[-1]) in ["2"]
            ):
                hass_isy_data[ISY994_NODES]["switch"].append(node)

            # Smartenit EZIO2X4
            if (
                domain == "switch"
                and device_type.startswith("7.3.255.")
                and str(node.address[-1]) in ["9", "A", "B", "C"]
            ):
                hass_isy_data[ISY994_NODES]["binary_sensor"].append(node)

            hass_isy_data[ISY994_NODES][domain].append(node)
            return True

    return False


def _check_for_zwave_cat(
    hass: HomeAssistant, entry: ConfigEntry, node, single_domain: str = None
) -> bool:
    """Check if the node matches the ISY Z-Wave Category for any domains.

    This is for (presumably) every version of the ISY firmware, but only
    works for Z-Wave Devices with the devtype.cat property.
    """
    if not hasattr(node, "protocol") or node.protocol != PROTO_ZWAVE:
        return False

    if not hasattr(node, "devtype_cat") or node.devtype_cat is None:
        # Node doesn't have a device type category (non-Z-Wave device)
        return False

    device_type = node.devtype_cat
    domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]
    for domain in domains:
        if any(
            [device_type.startswith(t) for t in set(NODE_FILTERS[domain]["zwave_cat"])]
        ):

            hass_isy_data[ISY994_NODES][domain].append(node)
            return True

    return False


def _check_for_uom_id(
    hass: HomeAssistant,
    entry: ConfigEntry,
    node,
    single_domain: str = None,
    uom_list: list = None,
) -> bool:
    """Check if a node's uom matches any of the domains uom filter.

    This is used for versions of the ISY firmware that report uoms as a single
    ID. We can often infer what type of device it is by that ID.
    """
    if not hasattr(node, "uom") or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]

    if uom_list:
        if node_uom.intersection(uom_list):
            hass_isy_data[ISY994_NODES][single_domain].append(node)
            return True
    else:
        domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
        for domain in domains:
            if node_uom.intersection(NODE_FILTERS[domain]["uom"]):
                hass_isy_data[ISY994_NODES][domain].append(node)
                return True

    return False


def _check_for_states_in_uom(
    hass: HomeAssistant,
    entry: ConfigEntry,
    node,
    single_domain: str = None,
    states_list: list = None,
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
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]

    if states_list:
        if node_uom == set(states_list):
            hass_isy_data[ISY994_NODES][single_domain].append(node)
            return True
    else:
        domains = SUPPORTED_DOMAINS if not single_domain else [single_domain]
        for domain in domains:
            if node_uom == set(NODE_FILTERS[domain]["states"]):
                hass_isy_data[ISY994_NODES][domain].append(node)
                return True

    return False


def _is_sensor_a_binary_sensor(hass: HomeAssistant, entry: ConfigEntry, node) -> bool:
    """Determine if the given sensor node should be a binary_sensor."""
    if _check_for_node_def(hass, entry, node, single_domain="binary_sensor"):
        return True
    if _check_for_insteon_type(hass, entry, node, single_domain="binary_sensor"):
        return True

    # For the next two checks, we're providing our own set of uoms that
    # represent on/off devices. This is because we can only depend on these
    # checks in the context of already knowing that this is definitely a
    # sensor device.
    if _check_for_uom_id(
        hass, entry, node, single_domain="binary_sensor", uom_list=["2", "78"]
    ):
        return True
    if _check_for_states_in_uom(
        hass, entry, node, single_domain="binary_sensor", states_list=["on", "off"]
    ):
        return True

    return False


def _categorize_nodes(
    hass: HomeAssistant,
    entry: ConfigEntry,
    nodes,
    ignore_identifier: str,
    sensor_identifier: str,
) -> None:
    """Sort the nodes to their proper domains."""
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]
    for (path, node) in nodes:
        ignored = ignore_identifier in path or ignore_identifier in node.name
        if ignored:
            # Don't import this node as a device at all
            continue

        if isinstance(node, Group):
            hass_isy_data[ISY994_NODES][SCENE_DOMAIN].append(node)
            continue

        if sensor_identifier in path or sensor_identifier in node.name:
            # User has specified to treat this as a sensor. First we need to
            # determine if it should be a binary_sensor.
            if _is_sensor_a_binary_sensor(hass, entry, node):
                continue
            hass_isy_data[ISY994_NODES]["sensor"].append(node)
            continue

        # We have a bunch of different methods for determining the device type,
        # each of which works with different ISY firmware versions or device
        # family. The order here is important, from most reliable to least.
        if _check_for_node_def(hass, entry, node):
            continue
        if _check_for_insteon_type(hass, entry, node):
            continue
        if _check_for_zwave_cat(hass, entry, node):
            continue
        if _check_for_uom_id(hass, entry, node):
            continue
        if _check_for_states_in_uom(hass, entry, node):
            continue


def _categorize_programs(
    hass: HomeAssistant, entry: ConfigEntry, programs: dict
) -> None:
    """Categorize the ISY994 programs."""
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]
    for domain in SUPPORTED_PROGRAM_DOMAINS:
        try:
            folder = programs[KEY_MY_PROGRAMS][f"HA.{domain}"]
        except KeyError:
            pass
        else:
            for dtype, _, node_id in folder.children:
                if dtype != KEY_FOLDER:
                    continue
                entity_folder = folder[node_id]
                try:
                    status = entity_folder[KEY_STATUS]
                    assert status.dtype == "program", "Not a program"
                    if domain != "binary_sensor":
                        actions = entity_folder[KEY_ACTIONS]
                        assert actions.dtype == "program", "Not a program"
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
                hass_isy_data[ISY994_PROGRAMS][domain].append(entity)


def _categorize_variables(
    hass: HomeAssistant,
    entry: ConfigEntry,
    variables: dict,
    domain_cfg: dict,
    domain: str,
) -> None:
    """Categorize the ISY994 Variables."""
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]
    if domain_cfg is None:
        return
    for isy_var in domain_cfg:
        vid = isy_var.get(CONF_ID)
        vtype = isy_var.get(CONF_TYPE)
        _, vname, _ = next(
            (var for i, var in enumerate(variables[vtype].children) if var[2] == vid),
            None,
        )
        if vname is None:
            _LOGGER.error(
                "ISY Variable Not Found in ISY List; "
                "check your config for Variable %s.%s",
                vtype,
                vid,
            )
            continue
        variable = (isy_var, vname, variables[vtype][vid])
        hass_isy_data[ISY994_VARIABLES][domain].append(variable)


def _categorize_weather(hass: HomeAssistant, entry: ConfigEntry, climate) -> None:
    """Categorize the ISY994 weather data."""
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]
    climate_attrs = dir(climate)
    weather_nodes = [
        WeatherNode(
            getattr(climate, attr),
            attr.replace("_", " "),
            getattr(climate, f"{attr}_units"),
        )
        for attr in climate_attrs
        if f"{attr}_units" in climate_attrs
    ]
    hass_isy_data[ISY994_WEATHER].extend(weather_nodes)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the isy994 component from YAML."""

    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the ISY 994 platform."""

    hass.data[DOMAIN][entry.entry_id] = {}
    hass_isy_data = hass.data[DOMAIN][entry.entry_id]
    hass_isy_data[ISY994_NODES] = {}
    for domain in SUPPORTED_DOMAINS:
        hass_isy_data[ISY994_NODES][domain] = []

    hass_isy_data[ISY994_WEATHER] = []

    hass_isy_data[ISY994_PROGRAMS] = {}
    for domain in SUPPORTED_DOMAINS:
        hass_isy_data[ISY994_PROGRAMS][domain] = []

    hass_isy_data[ISY994_VARIABLES] = {}
    for domain in SUPPORTED_VARIABLE_DOMAINS:
        hass_isy_data[ISY994_VARIABLES][domain] = []

    isy_config = entry.data

    user = isy_config.get(CONF_USERNAME)
    password = isy_config.get(CONF_PASSWORD)
    tls_version = isy_config.get(CONF_TLS_VER)
    host = urlparse(isy_config.get(CONF_HOST))
    ignore_identifier = isy_config.get(CONF_IGNORE_STRING)
    sensor_identifier = isy_config.get(CONF_SENSOR_STRING)
    enable_climate = isy_config.get(CONF_ENABLE_CLIMATE)
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
    isy = ISY(
        host.hostname,
        port,
        username=user,
        password=password,
        use_https=https,
        tls_ver=tls_version,
        log=_LOGGER,
    )
    if not isy.connected:
        return False

    _categorize_nodes(hass, entry, isy.nodes, ignore_identifier, sensor_identifier)
    _categorize_programs(hass, entry, isy.programs)
    _categorize_variables(
        hass, entry, isy.variables, isy_variables.get(CONF_SENSORS), "sensor"
    )
    _categorize_variables(
        hass,
        entry,
        isy.variables,
        isy_variables.get(CONF_BINARY_SENSORS),
        "binary_sensor",
    )
    _categorize_variables(
        hass, entry, isy.variables, isy_variables.get(CONF_SWITCHES), "switch"
    )

    # Dump ISY Clock Information. Future: Add ISY as sensor to Hass with attrs
    _LOGGER.info(repr(isy.clock))

    if enable_climate and isy.configuration.get("Weather Information"):
        _categorize_weather(hass, entry, isy.climate)

    async def start(event: object) -> None:
        """Start ISY auto updates."""
        _LOGGER.debug("ISY Starting Event Stream and automatic updates.")
        isy.auto_update = True

    async def stop(event: object) -> None:
        """Stop ISY auto updates."""
        isy.auto_update = False

    # only start fetching data after HA boots to prevent delaying the boot
    # process
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start)

    # Listen for HA stop to disconnect.
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    # Load platforms for the devices in the ISY controller that we support.
    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in SUPPORTED_DOMAINS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class ISYDevice(Entity):
    """Representation of an ISY994 device."""

    _name: str = None

    def __init__(self, node) -> None:
        """Initialize the insteon device."""
        self._node = node
        self._attrs = {}
        self._change_handler = None
        self._group_change_handler = None
        self._control_handler = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.status.subscribe("changed", self.on_update)

        if hasattr(self._node, "group_all_on"):
            self._group_change_handler = self._node.group_all_on.subscribe(
                "changed", self.on_update
            )

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

        device_info = {"name": self.name}
        if hasattr(self._node, "address"):
            device_address = self._node.address[:-2]  # remove trailing .[0-9AF]
            device_info["identifiers"] = {(DOMAIN, device_address)}
        if hasattr(self._node, "protocol"):
            device_info["model"] = self._node.protocol
        # PyISY does not expose the software version
        # if this is added we can add the sw_version
        _LOGGER.debug("device info: %s %s", self._node, device_info)
        return device_info

    @property
    def unique_id(self) -> str:
        """Get the unique identifier of the device."""
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
        # pylint: disable=protected-access
        return self._node.status._val

    @property
    def state(self):
        """Return the state of the ISY device."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN
        return super().state

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

        # Add the ISY Address as a attribute.
        if hasattr(self._node, "address"):
            attr["isy994_address"] = self._node.address

        # Add the device protocol as an attribute
        if hasattr(self._node, "protocol"):
            attr["isy994_protocol"] = self._node.protocol

        # If a Group/Scene, set a property if the entire scene is on/off
        if hasattr(self._node, "group_all_on"):
            # pylint: disable=protected-access
            attr["group_all_on"] = "on" if self._node.group_all_on._val else "off"

        self._attrs.update(attr)
        return self._attrs
