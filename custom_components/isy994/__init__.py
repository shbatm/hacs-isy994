"""Support the Universal Devices ISY/IoX controllers."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import homeassistant.helpers.device_registry as dr
import voluptuous as vol
from aiohttp import CookieJar
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VARIABLES,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from pyisyox import ISY, ISYResponseParseError
from pyisyox.connection import (
    ISYConnectionError,
    ISYConnectionInfo,
    ISYInvalidAuthError,
)
from pyisyox.constants import CONFIG_NETWORKING
from pyisyox.networking import NetworkCommand

from .const import (
    _LOGGER,
    CONF_ENABLE_NETWORKING,
    CONF_ENABLE_NODESERVERS,
    CONF_ENABLE_PROGRAMS,
    CONF_ENABLE_VARIABLES,
    CONF_NETWORK,
    CONF_TLS_VER,
    DEFAULT_TLS_VERSION,
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
    SCHEME_HTTP,
    SCHEME_HTTPS,
)
from .controller_events import IsyControllerEvents
from .helpers import _categorize_nodes, _categorize_programs, _categorize_variables
from .models import IsyConfigEntry, IsyData
from .services import async_setup_services
from .util import _async_cleanup_registry_entries

CONFIG_SCHEMA = vol.Schema(
    cv.deprecated(DOMAIN),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the ISY 994 integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IsyConfigEntry) -> bool:
    """Set up the ISY 994 integration."""
    isy_data = IsyData()
    entry.runtime_data = isy_data

    isy_config = entry.data
    isy_options = entry.options

    # Required
    user = isy_config[CONF_USERNAME]
    password = isy_config[CONF_PASSWORD]
    host = urlparse(isy_config[CONF_HOST])

    # Optional
    tls_version = isy_config.get(CONF_TLS_VER)
    enable_variables = isy_options.get(CONF_ENABLE_VARIABLES, True)
    enable_nodeservers = isy_options.get(CONF_ENABLE_NODESERVERS, True)
    enable_programs = isy_options.get(CONF_ENABLE_PROGRAMS, True)
    enable_networking = isy_options.get(CONF_ENABLE_NETWORKING, False)

    if host.scheme == SCHEME_HTTP:
        session = aiohttp_client.async_create_clientsession(
            hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
        )
    elif host.scheme == SCHEME_HTTPS:
        session = aiohttp_client.async_get_clientsession(hass)
    else:
        _LOGGER.error("The ISY/IoX host value in configuration is invalid")
        return False

    # Generate configuration info
    connection_info = ISYConnectionInfo(
        isy_config[CONF_HOST],
        user,
        password,
        tls_version=tls_version if tls_version != DEFAULT_TLS_VERSION else None,
        websession=session,
    )

    # Connect to ISY controller.
    isy = ISY(connection_info)

    try:
        async with asyncio.timeout(60):
            await isy.initialize(
                nodes=True,
                clock=False,
                programs=enable_programs,
                variables=enable_variables,
                networking=enable_networking,
                node_servers=enable_nodeservers,
            )
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady(
            "Timed out initializing the ISY; device may be busy, trying again later:"
            f" {err}"
        ) from err
    except ISYInvalidAuthError as err:
        raise ConfigEntryAuthFailed(f"Invalid credentials for the ISY: {err}") from err
    except ISYConnectionError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to the ISY, please adjust settings and try again: {err}"
        ) from err
    except ISYResponseParseError as err:
        raise ConfigEntryNotReady(
            "Invalid XML response from ISY; Ensure the ISY is running the latest"
            f" firmware: {err}"
        ) from err
    except TypeError as err:
        raise ConfigEntryNotReady(
            f"Invalid response ISY, device is likely still starting: {err}"
        ) from err

    isy_data.root = isy

    _categorize_nodes(isy_data, isy.nodes, isy_options)

    if enable_programs and isy.programs.loaded:
        _categorize_programs(isy_data, isy.programs)

    if enable_variables and isy.variables.entities:
        _categorize_variables(isy_data, isy.variables)
        isy_data.devices[CONF_VARIABLES] = _create_service_device_info(
            isy, name=CONF_VARIABLES.title(), unique_id=CONF_VARIABLES
        )

    if enable_networking and isy.networking.loaded:
        isy_data.devices[CONF_NETWORK] = _create_service_device_info(
            isy, name=CONFIG_NETWORKING, unique_id=CONF_NETWORK
        )
        for resource in isy.networking.values():
            assert isinstance(resource, NetworkCommand)
            isy_data.net_resources.append(resource)

    _async_get_or_create_isy_device_in_registry(hass, entry, isy)

    # Load platforms for the devices in the ISY controller that we support.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean-up any old entities that we no longer provide.
    _async_cleanup_registry_entries(hass, entry)

    @callback
    def _async_stop_auto_update(event: Event) -> None:
        """Stop the isy auto update on Home Assistant Shutdown."""
        _LOGGER.debug("ISY Stopping Event Stream and automatic updates")
        isy.websocket.stop()

    _LOGGER.debug("ISY Starting Event Stream and automatic updates")
    isy.websocket.start()
    isy_data.controller_events = IsyControllerEvents(hass, isy_data)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_auto_update)
    )

    return True


@callback
def _async_get_or_create_isy_device_in_registry(
    hass: HomeAssistant, entry: IsyConfigEntry, isy: ISY
) -> None:
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, isy.uuid)},
        identifiers={(DOMAIN, isy.uuid)},
        manufacturer=MANUFACTURER,
        name=isy.config.name,
        model=isy.config.model,
        sw_version=isy.config.firmware,
        configuration_url=isy.conn.url,
    )


def _create_service_device_info(isy: ISY, name: str, unique_id: str) -> DeviceInfo:
    """Create device info for ISY service devices."""
    return DeviceInfo(
        identifiers={
            (
                DOMAIN,
                f"{isy.uuid}_{unique_id}",
            )
        },
        manufacturer=MANUFACTURER,
        name=f"{isy.config.name} {name}",
        model=isy.config.model,
        sw_version=isy.config.firmware,
        configuration_url=isy.conn.url,
        via_device=(DOMAIN, isy.uuid),
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_unload_entry(hass: HomeAssistant, entry: IsyConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    isy: ISY = entry.runtime_data.root

    _LOGGER.debug("ISY Stopping Event Stream and automatic updates")
    isy.websocket.stop()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: IsyConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove ISY config entry from a device."""
    return not device_entry.identifiers.intersection(
        (DOMAIN, unique_id) for unique_id in config_entry.runtime_data.devices
    )
