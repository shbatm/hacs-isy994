"""Event entities for ISY Insteon load and keypad-button nodes.

Each entity represents a physical button on the device and emits one of the
``event_types`` below when its corresponding control event arrives from the
ISY. KeypadLinc sub-button entities are disabled by default to avoid
registering large numbers of unused entities for users who don't need them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyisyox.constants import (
    ATTR_ACTION,
    CMD_FADE_DOWN,
    CMD_FADE_STOP,
    CMD_FADE_UP,
    CMD_OFF,
    CMD_OFF_FAST,
    CMD_ON,
    CMD_ON_FAST,
    TAG_ADDRESS,
    NodeChangeAction,
)
from pyisyox.helpers.models import NodeChangedEvent, NodeProperty
from pyisyox.nodes import Node

from .entity import ISYNodeEntity

if TYPE_CHECKING:
    from .models import IsyConfigEntry

EVENT_BUTTON_UNIQUE_ID_SUFFIX = "_button"

CONTROL_TO_EVENT_TYPE: Final[dict[str, str]] = {
    CMD_ON: "on",
    CMD_OFF: "off",
    CMD_ON_FAST: "fast_on",
    CMD_OFF_FAST: "fast_off",
    CMD_FADE_UP: "fade_up",
    CMD_FADE_DOWN: "fade_down",
    CMD_FADE_STOP: "fade_stop",
}

BUTTON_DESCRIPTION: Final[EventEntityDescription] = EventEntityDescription(
    key="button",
    translation_key="button",
    device_class=EventDeviceClass.BUTTON,
    event_types=list(CONTROL_TO_EVENT_TYPE.values()),
)


def _sub_button_name(node: Node) -> str:
    """Return the sub-button label with the parent device prefix stripped.

    ISY users commonly label KeypadLinc sub-buttons as ``"<device> <suffix>"``
    (e.g. ``"Hallway Keypad B"``). With ``has_entity_name=True``, Home
    Assistant prepends the device name to the entity name when rendering the
    friendly name, so we strip the prefix here to avoid duplication like
    ``"Hallway Keypad Hallway Keypad B"``. Falls back to the raw node name
    when the prefix doesn't match. The label is user-supplied in the ISY
    admin console and is not translatable.
    """
    parent = node.parent_node
    name: str = node.name
    if parent is None:
        return name
    parent_name: str = parent.name
    if name.startswith(parent_name):
        return name[len(parent_name) :].lstrip(" -_:.") or name
    return name


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IsyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ISY event platform."""
    isy_data = entry.runtime_data
    device_info = isy_data.devices
    async_add_entities(
        ISYButtonEvent(node, device_info.get(node.primary_node))
        for node in isy_data.nodes[Platform.EVENT]
    )


class ISYButtonEvent(ISYNodeEntity, EventEntity):
    """Event entity that emits press/fast/fade events from an ISY node."""

    entity_description = BUTTON_DESCRIPTION
    _attr_has_entity_name = True

    def __init__(self, node: Node, device_info: DeviceInfo | None = None) -> None:
        """Initialize the ISY button event entity."""
        super().__init__(node, device_info=device_info)
        # Re-assert has_entity_name after super(): hacs's ISYNodeEntity
        # instance-writes False for non-device-root nodes (sub-buttons), which
        # would override the class-level True and break friendly names.
        self._attr_has_entity_name = True
        self._attr_unique_id = (
            f"{node.isy.uuid}_{node.address}{EVENT_BUTTON_UNIQUE_ID_SUFFIX}"
        )
        if node.parent_node is None:
            self._attr_name = None
        else:
            # Sub-button:
            self._attr_name = _sub_button_name(node)
            # Disabled by default — a typical KeypadLinc exposes 6-8 of
            # these and most users only automate a few.
            self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to all control events and node enabled/disabled changes.

        The base ISYNodeEntity subscribes to ``control_events`` filtered to a
        single control (``PROP_STATUS``) — for this entity we need every
        button/fade control, so we override with an unfiltered subscription.
        The bus-wide ``isy994_control`` event is still fired centrally by
        ``IsyControllerEvents.node_event_handler`` for every node.
        """
        self._change_handler = self._node.control_events.subscribe(
            self.async_on_control,
            key=self.unique_id,
        )
        self._availability_handler = self._node.isy.nodes.platform_events.subscribe(
            self._async_on_availability_change,
            event_filter={
                TAG_ADDRESS: self._node.address,
                ATTR_ACTION: NodeChangeAction.NODE_ENABLED,
            },
            key=self.unique_id,
        )

    @callback
    def _async_on_availability_change(self, event: NodeChangedEvent, key: str) -> None:
        """Refresh state when the node is enabled or disabled."""
        self._attr_available = self._node.enabled
        self.async_write_ha_state()

    @callback
    def async_on_control(self, event: NodeProperty, key: str) -> None:
        """Trigger the entity when a known control event arrives."""
        event_type = CONTROL_TO_EVENT_TYPE.get(event.control)
        if event_type is None:
            return
        self._trigger_event(event_type)
        self.async_write_ha_state()
