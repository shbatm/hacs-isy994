"""Support for ISY select entities."""
from __future__ import annotations

from pyisyox.constants import (
    ATTR_ACTION,
    BACKLIGHT_INDEX,
    CMD_BACKLIGHT,
    COMMAND_FRIENDLY_NAME,
    INSTEON_RAMP_RATES,
    PROP_RAMP_RATE,
    TAG_ADDRESS,
    UOM_INDEX as ISY_UOM_INDEX,
    UOM_TO_STATES,
    NodeChangeAction,
)
from pyisyox.helpers.events import ATTR_EVENT_INFO, EventListener, NodeChangedEvent
from pyisyox.helpers.models import NodeProperty
from pyisyox.nodes import Node

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import _LOGGER, BACKLIGHT_MEMORY_FILTER, DOMAIN, UOM_INDEX
from .entity import ISYNodeEntity
from .models import IsyData


def time_string(i: float) -> str:
    """Return a formatted ramp rate time string."""
    if i >= 60.0:
        return f"{(i/60.0):.1f} {UnitOfTime.MINUTES}"
    return f"{i} {UnitOfTime.SECONDS}"


RAMP_RATE_OPTIONS = [time_string(rate) for rate in INSTEON_RAMP_RATES.values()]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ISY/IoX select entities from config entry."""
    isy_data: IsyData = hass.data[DOMAIN][config_entry.entry_id]
    device_info = isy_data.devices
    entities: list[
        ISYAuxControlIndexSelectEntity
        | ISYRampRateSelectEntity
        | ISYBacklightSelectEntity
    ] = []

    for node, control in isy_data.aux_properties[Platform.SELECT]:
        name = COMMAND_FRIENDLY_NAME.get(control, control).replace("_", " ").title()
        if node.address != node.primary_node:
            name = f"{node.name} {name}"

        options = []
        if control == PROP_RAMP_RATE:
            options = RAMP_RATE_OPTIONS
        elif control == CMD_BACKLIGHT:
            options = BACKLIGHT_INDEX
        else:
            if (uom := node.aux_properties[control].uom) == UOM_INDEX:
                if options_dict := UOM_TO_STATES.get(uom):
                    options = list(options_dict.values())

        description = SelectEntityDescription(
            key=f"{node.address}_{control}",
            name=name,
            entity_category=EntityCategory.CONFIG,
            options=options,
        )
        entity_detail: dict = {
            "node": node,
            "control": control,
            "unique_id": f"{isy_data.uid_base(node)}_{control}",
            "description": description,
            "device_info": device_info.get(node.primary_node),
        }

        if control == PROP_RAMP_RATE:
            entities.append(ISYRampRateSelectEntity(**entity_detail))
            continue
        if control == CMD_BACKLIGHT:
            entities.append(ISYBacklightSelectEntity(**entity_detail))
            continue
        if node.uom == UOM_INDEX and options:
            entities.append(ISYAuxControlIndexSelectEntity(**entity_detail))
            continue
        # Future: support Node Server custom index UOMs
        _LOGGER.debug(
            "ISY missing node index unit definitions for %s: %s", node.name, name
        )
    async_add_entities(entities)


class ISYRampRateSelectEntity(ISYNodeEntity, SelectEntity):
    """Representation of a ISY/IoX Aux Control Ramp Rate Select entity."""

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        node_prop: NodeProperty = self._node.aux_properties[self._control]
        if node_prop.value is None:
            return None

        return RAMP_RATE_OPTIONS[int(node_prop.value)]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        await self._node.set_ramp_rate(RAMP_RATE_OPTIONS.index(option))


class ISYAuxControlIndexSelectEntity(ISYNodeEntity, SelectEntity):
    """Representation of a ISY/IoX Aux Control Index Select entity."""

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        node_prop: NodeProperty = self._node.aux_properties[self._control]
        if node_prop.value is None:
            return None

        if options_dict := UOM_TO_STATES.get(node_prop.uom):
            return options_dict.get(str(node_prop.value), str(node_prop.value))
        return node_prop.formatted

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        node_prop: NodeProperty = self._node.aux_properties[self._control]

        await self._node.send_cmd(
            self._control, val=self.options.index(option), uom=node_prop.uom
        )


class ISYBacklightSelectEntity(ISYNodeEntity, SelectEntity, RestoreEntity):
    """Representation of a ISY/IoX Backlight Select entity."""

    _assumed_state = True  # Backlight values aren't read from device

    def __init__(
        self,
        node: Node,
        control: str,
        unique_id: str,
        description: SelectEntityDescription,
        device_info: DeviceInfo | None,
    ) -> None:
        """Initialize the ISY Backlight Select entity."""
        super().__init__(
            node=node,
            control=control,
            unique_id=unique_id,
            description=description,
            device_info=device_info,
        )
        self._memory_change_handler: EventListener | None = None
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        """Load the last known state when added to hass."""
        await super().async_added_to_hass()
        if (
            last_state := await self.async_get_last_state()
        ) and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._attr_current_option = last_state.state

        # Listen to memory writing events to update state if changed in ISY
        self._memory_change_handler = self._node.isy.nodes.platform_events.subscribe(
            self.async_on_memory_write,
            event_filter={
                TAG_ADDRESS: self._node.address,
                ATTR_ACTION: NodeChangeAction.DEVICE_MEMORY,
                ATTR_EVENT_INFO: BACKLIGHT_MEMORY_FILTER,
            },
            key=self.unique_id,
        )

    @callback
    def async_on_memory_write(self, event: NodeChangedEvent, key: str) -> None:
        """Handle a memory write event from the ISY Node."""
        option = BACKLIGHT_INDEX[event.event_info["value"]]
        if option == self._attr_current_option:
            return  # Change was from this entity, don't update twice
        self._attr_current_option = option
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        if not await self._node.send_cmd(
            CMD_BACKLIGHT, val=BACKLIGHT_INDEX.index(option), uom=ISY_UOM_INDEX
        ):
            raise HomeAssistantError(
                f"Could not set backlight to {option} for {self._node.address}"
            )
        self._attr_current_option = option
        self.async_write_ha_state()
