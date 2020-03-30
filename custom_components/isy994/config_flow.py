"""Config flow for Universal Devices ISY994 integration."""
from functools import partial
import logging
from urllib.parse import urlparse

from pyisy.configuration import Configuration
from pyisy.connection import Connection
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import (
    CONF_IGNORE_STRING,
    CONF_SENSOR_STRING,
    CONF_TLS_VER,
    DEFAULT_IGNORE_STRING,
    DEFAULT_SENSOR_STRING,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_TLS_VER): vol.Coerce(float),
        vol.Optional(CONF_IGNORE_STRING, default=DEFAULT_IGNORE_STRING): str,
        vol.Optional(CONF_SENSOR_STRING, default=DEFAULT_SENSOR_STRING): str
        # Variables require yaml
    },
    extra=vol.ALLOW_EXTRA,
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    user = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    host = urlparse(data[CONF_HOST])
    tls_version = data.get(CONF_TLS_VER)

    if host.scheme == "http":
        https = False
        port = host.port or 80
    elif host.scheme == "https":
        https = True
        port = host.port or 443
    else:
        _LOGGER.error("isy994 host value in configuration is invalid")
        raise InvalidHost

    # Connect to ISY controller.
    try:
        isy_conn = await hass.async_add_executor_job(
            partial(
                Connection,
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
    except ValueError as err:
        raise InvalidAuth(err.args[0])
    else:
        isy_conf = await hass.async_add_executor_job(
            partial(Configuration, log=_LOGGER, xml=isy_conn.get_config())
        )
        # Return info that you want to store in the config entry.
        return {
            "title": f"{isy_conf['name']} ({host.hostname})",
            "uuid": isy_conf["uuid"],
        }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Universal Devices ISY994."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        info = None
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["base"] = "invalid_host"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(info["uuid"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate the host value is invalid."""


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
