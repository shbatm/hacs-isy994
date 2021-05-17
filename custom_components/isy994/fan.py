"""Support for ISY994 fans."""
from __future__ import annotations

import math

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_INSTEON

from homeassistant.components.fan import (
    DOMAIN as FAN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import _LOGGER, DOMAIN as ISY994_DOMAIN, ISY994_NODES, ISY994_PROGRAMS
from .entity import ISYNodeEntity, ISYProgramEntity
from .helpers import migrate_old_unique_ids
from .percentage import (
    int_states_in_range,
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

ON_SPEEDS = [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

SPEED_RANGE = (1, 255)  # off is not included


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the ISY994 fan platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []

    for node in hass_isy_data[ISY994_NODES][FAN]:
        devices.append(ISYFanEntity(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][FAN]:
        devices.append(ISYFanProgramEntity(name, status, actions))

    await migrate_old_unique_ids(hass, FAN, devices)
    async_add_entities(devices)


class ISYFanEntity(ISYNodeEntity, FanEntity):
    """Representation of an ISY994 fan device."""

    @property
    def speed(self) -> str:
        """Return the current speed."""
        pecentage = self.percentage
        if pecentage is None:
            return None
        if pecentage == 0:
            return SPEED_OFF
        return percentage_to_ordered_list_item(ON_SPEEDS, self.percentage)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self._node.status)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def is_on(self) -> bool:
        """Get if the fan is on."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return self._node.status != 0

    async def async_set_percentage(self, percentage: int) -> None:
        """Set node to speed percentage for the ISY994 fan device."""
        if percentage == 0:
            await self._node.turn_off()
            return

        isy_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))

        await self._node.turn_on(val=isy_speed)

    async def async_set_speed(self, speed: str) -> None:
        """Send the set speed command to the ISY994 fan device."""
        await self.async_set_percentage(
            ordered_list_item_to_percentage(ON_SPEEDS, speed)
        )

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Send the turn on command to the ISY994 fan device."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 fan device."""
        await self._node.turn_off()

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, *ON_SPEEDS]

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED


class ISYFanProgramEntity(ISYProgramEntity, FanEntity):
    """Representation of an ISY994 fan program."""

    @property
    def speed(self) -> str:
        """Return the current speed."""
        pecentage = self.percentage
        if pecentage is None:
            return None
        if pecentage == 0:
            return SPEED_OFF
        return percentage_to_ordered_list_item(ON_SPEEDS, self.percentage)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self._node.status)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if self._node.protocol == PROTO_INSTEON:
            return 3
        return int_states_in_range(SPEED_RANGE)

    @property
    def is_on(self) -> bool:
        """Get if the fan is on."""
        return self._node.status != 0

    async def async_turn_off(self, **kwargs) -> None:
        """Send the turn on command to ISY994 fan program."""
        if not await self._actions.run_then():
            _LOGGER.error("Unable to turn off the fan")

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Send the turn off command to ISY994 fan program."""
        if not await self._actions.run_else():
            _LOGGER.error("Unable to turn on the fan")
