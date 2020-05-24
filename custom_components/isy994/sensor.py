"""Support for ISY994 sensors."""
from typing import Callable, Dict, Union

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_VARIABLES,
    UOM_DOUBLE_TEMP,
    UOM_FRIENDLY_NAME,
    UOM_INDEX,
    UOM_TO_STATES,
)
from .entity import ISYEntity, ISYNodeEntity
from .helpers import convert_isy_value_to_hass, migrate_old_unique_ids
from .services import async_setup_device_services


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 sensor platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []

    for node in hass_isy_data[ISY994_NODES][SENSOR]:
        _LOGGER.debug("Loading %s", node.name)
        devices.append(ISYSensorEntity(node))

    for vname, vobj in hass_isy_data[ISY994_VARIABLES]:
        devices.append(ISYSensorVariableEntity(vname, vobj))

    await migrate_old_unique_ids(hass, SENSOR, devices)
    async_add_entities(devices)
    async_setup_device_services(hass)


class ISYSensorEntity(ISYNodeEntity):
    """Representation of an ISY994 sensor device."""

    @property
    def raw_unit_of_measurement(self) -> Union[dict, str]:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        uom = self._node.uom

        # Backwards compatibility for ISYv4 Firmware:
        if isinstance(uom, list):
            return UOM_FRIENDLY_NAME.get(uom[0], uom[0])

        # Special cases for ISY UOM index units:
        isy_states = UOM_TO_STATES.get(uom)
        if isy_states:
            return isy_states

        return UOM_FRIENDLY_NAME.get(uom)

    @property
    def state(self) -> str:
        """Get the state of the ISY994 sensor device."""
        value = self._node.status
        if value == ISY_VALUE_UNKNOWN:
            return None

        # Get the translated ISY Unit of Measurement
        uom = self.raw_unit_of_measurement

        # Check if this is a known index pair UOM
        if isinstance(uom, dict):
            return uom.get(value, value)

        # Check if this is an index type and get formatted value
        if uom == UOM_INDEX and hasattr(self._node, "formatted"):
            return self._node.formatted

        # Handle ISY precision and rounding
        value = convert_isy_value_to_hass(value, uom, self._node.prec)

        # Convert temperatures to Home Assistant's unit
        if uom in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
            value = self.hass.config.units.temperature(value, uom)

        return value

    @property
    def unit_of_measurement(self) -> str:
        """Get the Home Assistant unit of measurement for the device."""
        raw_units = self.raw_unit_of_measurement
        # Check if this is a known index pair UOM
        if isinstance(raw_units, dict) or raw_units == UOM_INDEX:
            return None
        if raw_units in (TEMP_FAHRENHEIT, TEMP_CELSIUS, UOM_DOUBLE_TEMP):
            return self.hass.config.units.temperature_unit
        return raw_units


class ISYSensorVariableEntity(ISYEntity):
    """Representation of an ISY994 variable as a sensor device."""

    def __init__(self, vname: str, vobj: object) -> None:
        """Initialize the ISY994 binary sensor program."""
        super().__init__(vobj)
        self._name = vname

    @property
    def state(self):
        """Return the state of the variable."""
        return self._node.status

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        return {
            "init_value": int(self._node.init),
            "last_edited": self._node.last_edited,
        }

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:counter"
