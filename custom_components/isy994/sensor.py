"""Support for ISY sensors."""
from __future__ import annotations

from typing import Any

from pyisyox.constants import (
    COMMAND_FRIENDLY_NAME,
    PROP_BATTERY_LEVEL,
    PROP_COMMS_ERROR,
    PROP_ENERGY_MODE,
    PROP_HEAT_COOL_STATE,
    PROP_HUMIDITY,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
    PROP_TEMPERATURE,
)
from pyisyox.helpers.models import NodeProperty
from pyisyox.nodes import Node

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    _LOGGER,
    DOMAIN,
    UOM_DOUBLE_TEMP,
    UOM_FRIENDLY_NAME,
    UOM_INDEX,
    UOM_ON_OFF,
    UOM_TO_STATES,
)
from .entity import ISYNodeEntity
from .helpers import convert_isy_value_to_hass

# Disable general purpose and redundant sensors by default
AUX_DISABLED_BY_DEFAULT_MATCH = ["DO"]
AUX_DISABLED_BY_DEFAULT_EXACT = {
    PROP_COMMS_ERROR,
    PROP_ENERGY_MODE,
    PROP_HEAT_COOL_STATE,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
}

# Reference pyisyox.constants.COMMAND_FRIENDLY_NAME for API details.
#   Note: "LUMIN"/Illuminance removed, some devices use non-conformant "%" unit
#         "VOCLVL"/VOC removed, uses qualitative UOM not ug/m^3
ISY_CONTROL_TO_DEVICE_CLASS = {
    PROP_BATTERY_LEVEL: SensorDeviceClass.BATTERY,
    PROP_HUMIDITY: SensorDeviceClass.HUMIDITY,
    PROP_TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    "BARPRES": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    "CC": SensorDeviceClass.CURRENT,
    "CO2LVL": SensorDeviceClass.CO2,
    "CPW": SensorDeviceClass.POWER,
    "CV": SensorDeviceClass.VOLTAGE,
    "DEWPT": SensorDeviceClass.TEMPERATURE,
    "DISTANC": SensorDeviceClass.DISTANCE,
    "ETO": SensorDeviceClass.PRECIPITATION_INTENSITY,
    "FATM": SensorDeviceClass.WEIGHT,
    "FREQ": SensorDeviceClass.FREQUENCY,
    "MUSCLEM": SensorDeviceClass.WEIGHT,
    "PF": SensorDeviceClass.POWER_FACTOR,
    "PM10": SensorDeviceClass.PM10,
    "PM25": SensorDeviceClass.PM25,
    "PRECIP": SensorDeviceClass.PRECIPITATION,
    "RAINRT": SensorDeviceClass.PRECIPITATION_INTENSITY,
    "RFSS": SensorDeviceClass.SIGNAL_STRENGTH,
    "SOILH": SensorDeviceClass.MOISTURE,
    "SOILT": SensorDeviceClass.TEMPERATURE,
    "SOLRAD": SensorDeviceClass.IRRADIANCE,
    "SPEED": SensorDeviceClass.SPEED,
    "TEMPEXH": SensorDeviceClass.TEMPERATURE,
    "TEMPOUT": SensorDeviceClass.TEMPERATURE,
    "TPW": SensorDeviceClass.ENERGY,
    "WATERP": SensorDeviceClass.PRESSURE,
    "WATERT": SensorDeviceClass.TEMPERATURE,
    "WATERTB": SensorDeviceClass.TEMPERATURE,
    "WATERTD": SensorDeviceClass.TEMPERATURE,
    "WEIGHT": SensorDeviceClass.WEIGHT,
    "WINDCH": SensorDeviceClass.TEMPERATURE,
}
ISY_CONTROL_TO_STATE_CLASS = {
    control: (
        SensorStateClass.MEASUREMENT
        if control != "TPW"
        else SensorStateClass.TOTAL_INCREASING
    )
    for control in ISY_CONTROL_TO_DEVICE_CLASS
}
ISY_CONTROL_TO_ENTITY_CATEGORY = {
    PROP_RAMP_RATE: EntityCategory.DIAGNOSTIC,
    PROP_ON_LEVEL: EntityCategory.DIAGNOSTIC,
    PROP_COMMS_ERROR: EntityCategory.DIAGNOSTIC,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY sensor platform."""
    isy_data = hass.data[DOMAIN][entry.entry_id]
    entities: list[ISYSensorEntity] = []
    devices: dict[str, DeviceInfo] = isy_data.devices

    entity_list: list[tuple[Node, str]] = [
        *[(node, PROP_STATUS) for node in isy_data.nodes[Platform.SENSOR]],
        *isy_data.aux_properties[Platform.SENSOR],
    ]

    def get_native_uom(
        uom: str | list, node: Node, control: str = PROP_STATUS
    ) -> tuple[str | None, dict[int, str] | None]:
        """Get the native UoM and Options Dict for the ISY sensor device."""
        # Backwards compatibility for ISYv4 Firmware:
        if isinstance(uom, list):
            return (UOM_FRIENDLY_NAME.get(uom[0], uom[0]), None)
        # Special cases for ISY UOM index units:
        if isy_states := UOM_TO_STATES.get(uom):
            return (None, isy_states)
        if (
            uom == UOM_INDEX
            and (node_def := node.get_node_def()) is not None
            and (editor := node_def.status_editors.get(control))
        ):
            return (None, editor.values)
        # Handle on/off or unlisted index types
        if uom in (UOM_ON_OFF, UOM_INDEX):
            return (None, None)
        # Assume double-temp matches current Hass unit (no way to confirm)
        if uom == UOM_DOUBLE_TEMP:
            return (hass.config.units.temperature_unit, None)
        return (UOM_FRIENDLY_NAME.get(uom), None)

    for node, control in entity_list:
        _LOGGER.debug("Loading %s %s", node.name, COMMAND_FRIENDLY_NAME.get(control))
        enabled_default = control not in AUX_DISABLED_BY_DEFAULT_EXACT and not any(
            control.startswith(match) for match in AUX_DISABLED_BY_DEFAULT_MATCH
        )

        device_class = ISY_CONTROL_TO_DEVICE_CLASS.get(control)
        state_class = ISY_CONTROL_TO_STATE_CLASS.get(control)
        native_uom = None
        options_dict = None

        if (prop := node.aux_properties.get(control)) is not None:
            if prop.uom in (UOM_ON_OFF, UOM_INDEX):
                device_class = SensorDeviceClass.ENUM
                state_class = None
            native_uom, options_dict = get_native_uom(prop.uom, node, control)
            if native_uom is None and device_class != SensorDeviceClass.ENUM:
                # Unknown UOMs will cause errors with device classes expecting numeric values
                # they will use the ISY formatted value and may or may not have a unit embedded.
                # this should only apply for new UoM that have not been added to PyISYOX yet.
                device_class = None
                state_class = None

        description = SensorEntityDescription(
            key=f"{node}_{control}",
            device_class=device_class,
            native_unit_of_measurement=native_uom,
            options=list(options_dict.values()) if options_dict else None,
            state_class=state_class,
            entity_category=ISY_CONTROL_TO_ENTITY_CATEGORY.get(control),
            entity_registry_enabled_default=enabled_default,
        )

        entity = ISYSensorEntity(
            node=node,
            control=control,
            description=description,
            unique_id=f"{isy_data.uid_base(node)}_{control}"
            if control != PROP_STATUS
            else None,
            device_info=devices.get(node.primary_node),
            options_dict=options_dict,
        )
        entities.append(entity)

    async_add_entities(entities)


class ISYSensorEntity(ISYNodeEntity, SensorEntity):
    """Representation of an ISY sensor device."""

    _options_dict: dict[int, str] | None
    entity_description: SensorEntityDescription

    def __init__(
        self,
        node: Node,
        control: str = PROP_STATUS,
        unique_id: str | None = None,
        description: SensorEntityDescription | None = None,
        device_info: DeviceInfo | None = None,
        options_dict: dict[int, str] | None = None,
    ) -> None:
        """Initialize the ISY aux sensor."""
        super().__init__(
            node=node,
            control=control,
            unique_id=unique_id,
            description=description,
            device_info=device_info,
        )
        self._options_dict = options_dict

    @property
    def target(self) -> NodeProperty | None:
        """Return target for the sensor."""
        if self._control not in self._node.aux_properties:
            # Property not yet set (i.e. no errors)
            return None
        return self._node.aux_properties[self._control]

    @property
    def target_value(self) -> Any:
        """Return the target value."""
        return None if self.target is None else self.target.value

    @property
    def native_value(self) -> float | int | str | None:
        """Get the state of the ISY sensor device."""
        if self.target is None or (value := self.target_value) is None:
            return None

        # Check if this is a known index pair UOM
        if self._options_dict is not None:
            return self._options_dict.get(value, value)

        # Check if this is an on/off or unlisted index type and get formatted value
        if self.native_unit_of_measurement is None and self.target.formatted:
            return self.target.formatted

        # Handle ISY precision and rounding
        value = convert_isy_value_to_hass(value, self.target.uom, self.target.precision)

        if value is None:
            return None

        assert isinstance(value, int | float)
        return value
