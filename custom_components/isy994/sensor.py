"""Support for ISY994 sensors."""
import logging
from typing import Callable, Optional

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.sensor import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.typing import Dict, HomeAssistantType

from . import ISYDevice, migrate_old_unique_ids
from .const import (
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_VARIABLES,
    UOM_FRIENDLY_NAME,
    UOM_TO_STATES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 sensor platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []

    for node in hass_isy_data[ISY994_NODES][DOMAIN]:
        _LOGGER.debug("Loading %s", node.name)
        devices.append(ISYSensorDevice(node))

    for vcfg, vname, vobj in hass_isy_data[ISY994_VARIABLES][DOMAIN]:
        devices.append(ISYSensorVariableDevice(vcfg, vname, vobj))

    await migrate_old_unique_ids(hass, DOMAIN, devices)
    async_add_entities(devices)


class ISYSensorDevice(ISYDevice):
    """Representation of an ISY994 sensor device."""

    @property
    def raw_unit_of_measurement(self) -> str:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        uom = self._node.uom
        if isinstance(uom, list):
            uom = uom[0]

        friendly_name = UOM_FRIENDLY_NAME.get(uom, uom)
        if friendly_name in [TEMP_CELSIUS, TEMP_FAHRENHEIT]:
            friendly_name = self.hass.config.units.temperature_unit
        return friendly_name

    @property
    def state(self):
        """Get the state of the ISY994 sensor device."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN

        uom = self._node.uom
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


class ISYSensorVariableDevice(ISYDevice):
    """Representation of an ISY994 variable as a sensor device."""

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
        return self._config.get(CONF_ICON)

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
