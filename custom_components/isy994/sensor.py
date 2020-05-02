"""Support for ISY994 sensors."""
from typing import Callable, Optional

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import ISYNodeEntity, ISYVariableEntity, migrate_old_unique_ids
from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_VARIABLES,
    UOM_FRIENDLY_NAME,
    UOM_TO_STATES,
)
from .services import async_setup_device_services


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 sensor platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []

    for node in hass_isy_data[ISY994_NODES][PLATFORM_DOMAIN]:
        _LOGGER.debug("Loading %s", node.name)
        devices.append(ISYSensorEntity(node))

    for vcfg, vname, vobj in hass_isy_data[ISY994_VARIABLES][PLATFORM_DOMAIN]:
        devices.append(ISYSensorVariableEntity(vcfg, vname, vobj))

    await migrate_old_unique_ids(hass, PLATFORM_DOMAIN, devices)
    async_add_entities(devices)
    async_setup_device_services(hass)


class ISYSensorEntity(ISYNodeEntity):
    """Representation of an ISY994 sensor device."""

    @property
    def raw_unit_of_measurement(self) -> str:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        uom = self._node.uom

        # Backwards compatibility for ISYv4 Firmware:
        if isinstance(uom, list):
            return UOM_FRIENDLY_NAME.get(uom[0], uom[0])
        return UOM_FRIENDLY_NAME.get(uom)

    @property
    def state(self):
        """Get the state of the ISY994 sensor device."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN

        uom = self._node.uom
        # Backwards compatibility for ISYv4 Firmware:
        if isinstance(uom, list):
            uom = uom[0]
        if not uom:
            return STATE_UNKNOWN

        states = UOM_TO_STATES.get(uom)
        if states and states.get(self.value):
            return states.get(self.value)
        if self._node.prec and int(self._node.prec) != 0:
            str_val = str(self.value)
            int_prec = int(self._node.prec)
            decimal_part = str_val[-int_prec:]
            whole_part = str_val[: len(str_val) - int_prec]
            val = float(f"{whole_part}.{decimal_part}")
            raw_units = self.raw_unit_of_measurement
            if raw_units in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
                val = self.hass.config.units.temperature(val, raw_units)
            return val
        return self.value

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement for the ISY994 sensor device."""
        raw_units = self.raw_unit_of_measurement
        if raw_units in (TEMP_FAHRENHEIT, TEMP_CELSIUS):
            return self.hass.config.units.temperature_unit
        return raw_units


class ISYSensorVariableEntity(ISYVariableEntity):
    """Representation of an ISY994 variable as a sensor device."""

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def state(self):
        """Return the state of the variable."""
        return self.value

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._config.get(CONF_UNIT_OF_MEASUREMENT)
