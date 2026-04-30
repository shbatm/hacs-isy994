"""Provide info to system health."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from pyisyox import ISY

from .const import DOMAIN, ISY_URL_POSTFIX
from .models import IsyConfigEntry


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    health_info = {}

    # Get first config entry (only first ISY is supported for now)
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return health_info

    entry: IsyConfigEntry = entries[0]  # type: ignore[assignment]
    isy_data = entry.runtime_data
    isy: ISY = isy_data.root

    health_info["host_reachable"] = await system_health.async_check_can_reach_url(
        hass, f"{entry.data[CONF_HOST]}{ISY_URL_POSTFIX}"
    )
    health_info["device_connected"] = str(isy.connected)
    health_info["last_heartbeat"] = str(isy.websocket.last_heartbeat)
    health_info["websocket_status"] = isy.websocket.status

    return health_info
