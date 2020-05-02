"""ISY Services and Commands."""

from typing import Any

from pyisy.constants import COMMAND_FRIENDLY_NAME
import voluptuous as vol

from homeassistant.const import ATTR_COMMAND
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import _LOGGER, DOMAIN, ISY994_ISY

# Common Services for All Platforms:
SERVICE_SYSTEM_QUERY = "system_query"
SERVICE_SEND_COMMAND = "send_cmd"

# Device specific methods (valid for most Groups/ISY Scenes, Lights, Switches, Fans)
SERVICE_BEEP = "beep"
SERVICE_BRIGHTEN = "brighten"
SERVICE_DEVICE_QUERY = "query"
SERVICE_DIM = "dim"
SERVICE_DISABLE = "disable"
SERVICE_ENABLE = "enable"
SERVICE_FADE_DOWN = "fade_down"
SERVICE_FADE_STOP = "fade_stop"
SERVICE_FADE_UP = "fade_up"
SERVICE_FAST_OFF = "fast_off"
SERVICE_FAST_ON = "fast_on"

# Services valid only for dimmable lights.
SERVICE_SET_ON_LEVEL = "set_on_level"
SERVICE_SET_RAMP_RATE = "set_ramp_rate"
SERVICE_START_MANUAL_DIMMING = "start_manual_dimming"
SERVICE_STOP_MANUAL_DIMMING = "stop_manual_dimming"

ISY994_SERVICES = [
    SERVICE_BEEP,
    SERVICE_BRIGHTEN,
    SERVICE_DEVICE_QUERY,
    SERVICE_DIM,
    SERVICE_DISABLE,
    SERVICE_ENABLE,
    SERVICE_FADE_DOWN,
    SERVICE_FADE_STOP,
    SERVICE_FADE_UP,
    SERVICE_FAST_OFF,
    SERVICE_FAST_ON,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_ON_LEVEL,
    SERVICE_SET_RAMP_RATE,
    SERVICE_START_MANUAL_DIMMING,
    SERVICE_STOP_MANUAL_DIMMING,
    SERVICE_SYSTEM_QUERY,
]

ATTR_ADDRESS = "address"
ATTR_PARAMETERS = "parameters"
ATTR_UOM = "uom"
ATTR_VALUE = "value"

SERVICE_SYSTEM_QUERY_SCHEMA = vol.Schema({vol.Optional(ATTR_ADDRESS): cv.string})

SERVICE_SET_RAMP_RATE_SCHEMA = {
    vol.Required(ATTR_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 31))
}

SERVICE_SET_VALUE_SCHEMA = {
    vol.Required(ATTR_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 255))
}


def valid_isy_commands(value: Any) -> str:
    """Validate the command is valid."""
    value = str(value).upper()
    if value in COMMAND_FRIENDLY_NAME.keys():
        return value
    raise vol.Invalid("Invalid ISY Command.")


SERVICE_SEND_COMMAND_SCHEMA = {
    vol.Required(ATTR_COMMAND): vol.All(cv.string, valid_isy_commands),
    vol.Optional(ATTR_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 255)),
    vol.Optional(ATTR_UOM): vol.All(vol.Coerce(int), vol.Range(0, 120)),
    vol.Optional(ATTR_PARAMETERS, default={}): {cv.string: cv.string},
}


@callback
def async_setup_services(hass: HomeAssistantType):
    """Create and register services for the ISY integration."""
    if hass.services.async_services().get(DOMAIN):
        return

    async def async_system_query_service_handler(service):
        """Handle a system query service call."""
        address = service.data.get(ATTR_ADDRESS)

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
                # TODO: Enable once PyISY is updated with PR#94
                # await hass.async_add_executor_job(isy.query, address)
                return
            _LOGGER.debug(
                "Requesting system query of ISY %s", isy.configuration["uuid"]
            )
            # TODO: Enable once PyISY is updated with PR#94
            # await hass.async_add_executor_job(isy.query)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SYSTEM_QUERY,
        service_func=async_system_query_service_handler,
        schema=SERVICE_SYSTEM_QUERY_SCHEMA,
    )


@callback
def async_unload_services(hass: HomeAssistantType):
    """Unload services for the ISY integration."""
    if hass.data[DOMAIN]:
        # There is still another config entry for this domain, don't remove services.
        return

    _LOGGER.info("Unloading ISY994 Services.")
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SYSTEM_QUERY)


@callback
def async_setup_device_services(hass: HomeAssistantType):
    """Create device-specific services for the ISY Integration."""
    platform = entity_platform.current_platform.get()

    async def device_service_handler(entity, service_call):
        """Handle device-specific service calls."""
        # pylint: disable=protected-access
        if not hasattr(entity, "_node") or not hasattr(
            entity._node, service_call.service
        ):
            _LOGGER.warning(
                "Invalid Service Call %s for device %s.",
                service_call.service,
                entity.entity_id,
            )
            return

        if service_call.service == SERVICE_SEND_COMMAND:
            command = service_call.data.get(ATTR_COMMAND)
            value = service_call.data.get(ATTR_VALUE)
            parameters = service_call.data.get(ATTR_PARAMETERS)
            uom = service_call.data.get(ATTR_UOM)
            _LOGGER.debug("Sending command %s to device %s.", command, entity.entity_id)
            await hass.async_add_executor_job(
                entity._node.send_cmd, command, value, uom, parameters
            )

            return

        _LOGGER.debug(
            "Sending command %s to device %s.", service_call.service, entity.entity_id
        )
        await hass.async_add_executor_job(getattr(entity._node, service_call.service))

    platform.async_register_entity_service(
        SERVICE_SEND_COMMAND, SERVICE_SEND_COMMAND_SCHEMA, device_service_handler
    )
    platform.async_register_entity_service(SERVICE_BEEP, {}, device_service_handler)
    platform.async_register_entity_service(SERVICE_BRIGHTEN, {}, device_service_handler)
    platform.async_register_entity_service(
        SERVICE_DEVICE_QUERY, {}, device_service_handler
    )
    platform.async_register_entity_service(SERVICE_DIM, {}, device_service_handler)
    platform.async_register_entity_service(SERVICE_DISABLE, {}, device_service_handler)
    platform.async_register_entity_service(SERVICE_ENABLE, {}, device_service_handler)
    platform.async_register_entity_service(
        SERVICE_FADE_DOWN, {}, device_service_handler
    )
    platform.async_register_entity_service(
        SERVICE_FADE_STOP, {}, device_service_handler
    )
    platform.async_register_entity_service(SERVICE_FADE_UP, {}, device_service_handler)
    platform.async_register_entity_service(SERVICE_FAST_OFF, {}, device_service_handler)
    platform.async_register_entity_service(SERVICE_FAST_ON, {}, device_service_handler)


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
    platform.async_register_entity_service(
        SERVICE_START_MANUAL_DIMMING, {}, SERVICE_START_MANUAL_DIMMING
    )
    platform.async_register_entity_service(
        SERVICE_STOP_MANUAL_DIMMING, {}, SERVICE_STOP_MANUAL_DIMMING
    )
