"""ISY Services and Commands."""

from typing import Any

from pyisy.constants import COMMAND_FRIENDLY_NAME
import voluptuous as vol

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND,
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import _LOGGER, DOMAIN, ISY994_ISY

# Common Services for All Platforms:
SERVICE_SYSTEM_QUERY = "system_query"
SERVICE_SET_VARIABLE = "set_variable"
SERVICE_SEND_PROGRAM_COMMAND = "send_program_command"
SERVICE_RUN_NETWORK_RESOURCE = "run_network_resource"

# Entity specific methods (valid for most Groups/ISY Scenes, Lights, Switches, Fans)
SERVICE_SEND_RAW_NODE_COMMAND = "send_raw_node_command"
SERVICE_SEND_NODE_COMMAND = "send_node_command"

# Services valid only for dimmable lights.
SERVICE_SET_ON_LEVEL = "set_on_level"
SERVICE_SET_RAMP_RATE = "set_ramp_rate"

CONF_PARAMETERS = "parameters"
CONF_VALUE = "value"
CONF_INIT = "init"

VALID_NODE_COMMANDS = [
    "beep",
    "brighten",
    "dim",
    "disable",
    "enable",
    "fade_down",
    "fade_stop",
    "fade_up",
    "fast_off",
    "fast_on",
    "query",
]
VALID_PROGRAM_COMMANDS = [
    "run",
    "run_then",
    "run_else",
    "stop",
    "enable",
    "disable",
    "enable_run_at_startup",
    "disable_run_at_startup",
]


def valid_isy_commands(value: Any) -> str:
    """Validate the command is valid."""
    value = str(value).upper()
    if value in COMMAND_FRIENDLY_NAME.keys():
        return value
    raise vol.Invalid("Invalid ISY Command.")


SCHEMA_GROUP = "name-address"

SERVICE_SYSTEM_QUERY_SCHEMA = vol.Schema({vol.Optional(CONF_ADDRESS): cv.string})

SERVICE_SET_RAMP_RATE_SCHEMA = {
    vol.Required(CONF_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 31))
}

SERVICE_SET_VALUE_SCHEMA = {
    vol.Required(CONF_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 255))
}

SERVICE_SEND_RAW_NODE_COMMAND_SCHEMA = {
    vol.Required(CONF_COMMAND): vol.All(cv.string, valid_isy_commands),
    vol.Optional(CONF_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 255)),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): vol.All(vol.Coerce(int), vol.Range(0, 120)),
    vol.Optional(CONF_PARAMETERS, default={}): {cv.string: cv.string},
}

SERVICE_SEND_NODE_COMMAND_SCHEMA = {
    vol.Required(CONF_COMMAND): vol.In(VALID_NODE_COMMANDS)
}

SERVICE_SET_VARIABLE_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_ADDRESS, CONF_TYPE, CONF_NAME),
    vol.Schema(
        {
            vol.Exclusive(CONF_NAME, SCHEMA_GROUP): cv.string,
            vol.Inclusive(CONF_ADDRESS, SCHEMA_GROUP): vol.Coerce(int),
            vol.Inclusive(CONF_TYPE, SCHEMA_GROUP): vol.All(
                vol.Coerce(int), vol.Range(1, 2)
            ),
            vol.Optional(CONF_INIT, default=False): bool,
            vol.Required(CONF_VALUE): vol.Coerce(int),
        }
    ),
)

SERVICE_SEND_PROGRAM_COMMAND_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_ADDRESS, CONF_NAME),
    vol.Schema(
        {
            vol.Exclusive(CONF_NAME, SCHEMA_GROUP): cv.string,
            vol.Exclusive(CONF_ADDRESS, SCHEMA_GROUP): cv.string,
            vol.Required(CONF_COMMAND): vol.In(VALID_PROGRAM_COMMANDS),
        }
    ),
)

SERVICE_RUN_NETWORK_RESOURCE_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_ADDRESS, CONF_NAME),
    vol.Schema(
        {
            vol.Exclusive(CONF_NAME, SCHEMA_GROUP): cv.string,
            vol.Exclusive(CONF_ADDRESS, SCHEMA_GROUP): vol.Coerce(int),
        }
    ),
)


@callback
def async_setup_services(hass: HomeAssistantType):
    """Create and register services for the ISY integration."""
    if hass.services.async_services().get(DOMAIN):
        return

    async def async_system_query_service_handler(service):
        """Handle a system query service call."""
        address = service.data.get(CONF_ADDRESS)

        for entry in hass.data[DOMAIN]:
            isy = hass.data[DOMAIN][entry][ISY994_ISY]
            # If an address is provided, make sure we query the correct ISY.
            # Otherwise, query the whole system on all ISY's connected.
            if address and isy.nodes.get_by_id(address) is not None:
                _LOGGER.debug(
                    "Requesting query of device %s on ISY %s",
                    address,
                    isy.configuration["uuid"],
                )
                hass.async_add_executor_job(isy.query, address)
                return
            _LOGGER.debug(
                "Requesting system query of ISY %s", isy.configuration["uuid"]
            )
            hass.async_add_executor_job(isy.query)

    async def async_run_network_resource_service_handler(service):
        """Handle a network resource service call."""
        address = service.data.get(CONF_ADDRESS)
        name = service.data.get(CONF_NAME)

        for entry in hass.data[DOMAIN]:
            isy = hass.data[DOMAIN][entry][ISY994_ISY]
            if not hasattr(isy, "networking"):
                continue
            command = None
            if address:
                command = isy.networking.get_by_id(address)
            if name:
                command = isy.networking.get_by_name(name)
            if command is not None:
                hass.async_add_executor_job(command.run)
                return
        _LOGGER.error(
            "Could not run network resource command. Not found or enabled on the ISY."
        )

    async def async_send_program_command_service_handler(service):
        """Handle a send program command service call."""
        address = service.data.get(CONF_ADDRESS)
        name = service.data.get(CONF_NAME)
        command = service.data.get(CONF_COMMAND)

        for entry in hass.data[DOMAIN]:
            isy = hass.data[DOMAIN][entry][ISY994_ISY]
            program = None
            if address:
                program = isy.programs.get_by_id(address)
            if name:
                program = isy.programs.get_by_name(name)
            if program is not None:
                hass.async_add_executor_job(getattr(program, command))
                return
        _LOGGER.error(
            "Could not send program command. Not found or enabled on the ISY."
        )

    async def async_set_variable_service_handler(service):
        """Handle a set variable service call."""
        address = service.data.get(CONF_ADDRESS)
        vtype = service.data.get(CONF_TYPE)
        name = service.data.get(CONF_NAME)
        value = service.data.get(CONF_VALUE)
        init = service.data.get(CONF_INIT, False)

        for entry in hass.data[DOMAIN]:
            isy = hass.data[DOMAIN][entry][ISY994_ISY]
            variable = None
            if name:
                variable = isy.variables.get_by_name(name)
            if address and vtype:
                variable = isy.variables.vobjs[vtype].get(address)
            if variable is not None:
                hass.async_add_executor_job(variable.set_value, value, init)
                return
        _LOGGER.error("Could not set variable value. Not found or enabled on the ISY.")

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SYSTEM_QUERY,
        service_func=async_system_query_service_handler,
        schema=SERVICE_SYSTEM_QUERY_SCHEMA,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_RUN_NETWORK_RESOURCE,
        service_func=async_run_network_resource_service_handler,
        schema=SERVICE_RUN_NETWORK_RESOURCE_SCHEMA,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SEND_PROGRAM_COMMAND,
        service_func=async_send_program_command_service_handler,
        schema=SERVICE_SEND_PROGRAM_COMMAND_SCHEMA,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_VARIABLE,
        service_func=async_set_variable_service_handler,
        schema=SERVICE_SET_VARIABLE_SCHEMA,
    )


@callback
def async_unload_services(hass: HomeAssistantType):
    """Unload services for the ISY integration."""
    if hass.data[DOMAIN]:
        # There is still another config entry for this domain, don't remove services.
        return

    _LOGGER.info("Unloading ISY994 Services.")
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SYSTEM_QUERY)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_RUN_NETWORK_RESOURCE)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SEND_PROGRAM_COMMAND)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SET_VARIABLE)


@callback
def async_setup_device_services(hass: HomeAssistantType):
    """Create device-specific services for the ISY Integration."""
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SEND_RAW_NODE_COMMAND,
        SERVICE_SEND_RAW_NODE_COMMAND_SCHEMA,
        SERVICE_SEND_RAW_NODE_COMMAND,
    )
    platform.async_register_entity_service(
        SERVICE_SEND_NODE_COMMAND,
        SERVICE_SEND_NODE_COMMAND_SCHEMA,
        SERVICE_SEND_NODE_COMMAND,
    )


@callback
def async_setup_light_services(hass: HomeAssistantType):
    """Create device-specific services for the ISY Integration."""
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_ON_LEVEL, SERVICE_SET_VALUE_SCHEMA, SERVICE_SET_ON_LEVEL
    )
    platform.async_register_entity_service(
        SERVICE_SET_RAMP_RATE, SERVICE_SET_RAMP_RATE_SCHEMA, SERVICE_SET_RAMP_RATE
    )
