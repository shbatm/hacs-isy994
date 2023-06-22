"""Representation of ISY/IoX buttons."""
from __future__ import annotations

from pyisyox import ISY
from pyisyox.constants import (
    ATTR_ACTION,
    TAG_ADDRESS,
    TAG_ENABLED,
    NodeChangeAction,
    Protocol,
)
from pyisyox.helpers.events import EventListener
from pyisyox.helpers.models import NodeProperty
from pyisyox.networking import NetworkCommand
from pyisyox.nodes import Node

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NETWORK, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ISY/IoX button from config entry."""
    isy_data = hass.data[DOMAIN][config_entry.entry_id]
    isy: ISY = isy_data.root
    device_info = isy_data.devices
    entities: list[
        ISYNodeQueryButtonEntity
        | ISYNodeBeepButtonEntity
        | ISYNetworkResourceButtonEntity
    ] = []

    for node in isy_data.root_nodes[Platform.BUTTON]:
        entities.append(
            ISYNodeQueryButtonEntity(
                node=node,
                name="Query",
                unique_id=f"{isy_data.uid_base(node)}_query",
                entity_category=EntityCategory.DIAGNOSTIC,
                device_info=device_info[node.address],
            )
        )
        if node.protocol == Protocol.INSTEON:
            entities.append(
                ISYNodeBeepButtonEntity(
                    node=node,
                    name="Beep",
                    unique_id=f"{isy_data.uid_base(node)}_beep",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    device_info=device_info[node.address],
                )
            )

    for node in isy_data.net_resources:
        entities.append(
            ISYNetworkResourceButtonEntity(
                node=node,
                name=node.name,
                unique_id=isy_data.uid_base(node),
                device_info=device_info[CONF_NETWORK],
            )
        )

    # Add entity to query full system
    entities.append(
        ISYNodeQueryButtonEntity(
            node=isy,
            name="Query",
            unique_id=f"{isy.uuid}_query",
            device_info=DeviceInfo(identifiers={(DOMAIN, isy.uuid)}),
            entity_category=EntityCategory.DIAGNOSTIC,
        )
    )

    async_add_entities(entities)


class ISYNodeButtonEntity(ButtonEntity):
    """Representation of an ISY/IoX device button entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _node: Node | ISY | NetworkCommand

    def __init__(
        self,
        node: Node | ISY | NetworkCommand,
        name: str,
        unique_id: str,
        device_info: DeviceInfo,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize a query ISY device button entity."""
        self._node = node

        # Entity class attributes
        self._attr_name = name
        self._attr_entity_category = entity_category
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._node_enabled = getattr(node, TAG_ENABLED, True)
        self._availability_handler: EventListener | None = None

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._node_enabled

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        # No status for NetworkResources or ISY Query buttons
        if not isinstance(self._node, Node):
            return
        self._availability_handler = self._node.isy.nodes.platform_events.subscribe(
            self.async_on_update,
            event_filter={
                TAG_ADDRESS: self._node.address,
                ATTR_ACTION: NodeChangeAction.NODE_ENABLED,
            },
            key=self.unique_id,
        )

    @callback
    def async_on_update(self, event: NodeProperty, key: str) -> None:
        """Handle the update event from the ISY Node."""
        # Watch for node availability/enabled changes only
        self._node_enabled = getattr(self._node, TAG_ENABLED, True)
        self.async_write_ha_state()


class ISYNodeQueryButtonEntity(ISYNodeButtonEntity):
    """Representation of a device query button entity."""

    _node: Node | ISY

    async def async_press(self) -> None:
        """Press the button."""
        await self._node.query()


class ISYNodeBeepButtonEntity(ISYNodeButtonEntity):
    """Representation of a device beep button entity."""

    _node: Node

    async def async_press(self) -> None:
        """Press the button."""
        await self._node.beep()


class ISYNetworkResourceButtonEntity(ISYNodeButtonEntity):
    """Representation of an ISY/IoX Network Resource button entity."""

    _attr_has_entity_name = False
    _node: NetworkCommand

    async def async_press(self) -> None:
        """Press the button."""
        await self._node.run()
