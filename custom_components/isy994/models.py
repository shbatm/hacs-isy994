"""The ISY/IoX integration data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.entity import DeviceInfo
from pyisyox import ISY
from pyisyox.constants import Protocol
from pyisyox.helpers.models import EntityStatus, NodeProperty
from pyisyox.networking import NetworkCommand
from pyisyox.nodes import Group, Node
from pyisyox.programs import Program
from pyisyox.variables import Variable

from .const import (
    CONF_NETWORK,
    NODE_AUX_PROP_PLATFORMS,
    NODE_PARALLEL_PLATFORMS,
    NODE_PLATFORMS,
    PROGRAM_PLATFORMS,
    ROOT_NODE_PLATFORMS,
    VARIABLE_PLATFORMS,
)
from .event import EVENT_BUTTON_UNIQUE_ID_SUFFIX

if TYPE_CHECKING:
    from .controller_events import IsyControllerEvents


@dataclass
class IsyData:
    """Data for the ISY/IoX integration."""

    root: ISY
    nodes: dict[Platform, list[Node]]
    groups: list[Group]
    root_nodes: dict[Platform, list[Node]]
    variables: dict[Platform, list[Variable]]
    programs: dict[Platform, list[tuple[str, Program, Program | None]]]
    net_resources: list[NetworkCommand]
    devices: dict[str, DeviceInfo]
    aux_properties: dict[Platform, list[tuple[Node, str]]]
    controller_events: IsyControllerEvents

    def __init__(self) -> None:
        """Initialize an empty ISY data class."""
        self.nodes = {p: [] for p in (*NODE_PLATFORMS, *NODE_PARALLEL_PLATFORMS)}
        self.groups = []
        self.root_nodes = {p: [] for p in ROOT_NODE_PLATFORMS}
        self.aux_properties = {p: [] for p in NODE_AUX_PROP_PLATFORMS}
        self.programs = {p: [] for p in PROGRAM_PLATFORMS}
        self.variables = {p: [] for p in VARIABLE_PLATFORMS}
        self.net_resources = []
        self.devices = {}

    @property
    def uuid(self) -> str:
        """Return the ISY UUID identification."""
        return self.root.uuid

    def uid_base(
        self,
        node: (
            Node
            | Group
            | Variable
            | Program
            | NetworkCommand
            | NodeProperty
            | EntityStatus
        ),
    ) -> str:
        """Return the unique id base string for a given node."""
        if isinstance(node, NetworkCommand):
            return f"{self.uuid}_{CONF_NETWORK}_{node.address}"
        return f"{self.uuid}_{node.address}"

    @property
    def unique_ids(self) -> set[tuple[Platform, str]]:
        """Return all the unique ids for a config entry id."""
        current_unique_ids: set[tuple[Platform, str]] = {
            (Platform.BUTTON, f"{self.uuid}_query")
        }

        # Structure and prefixes here must match what's added in __init__ and helpers
        for platform in NODE_PLATFORMS:
            for node in self.nodes[platform]:
                current_unique_ids.add((platform, self.uid_base(node)))

        for group in self.groups:
            current_unique_ids.add((Platform.SWITCH, self.uid_base(group)))

        for platform in NODE_AUX_PROP_PLATFORMS:
            for node, control in self.aux_properties[platform]:
                current_unique_ids.add((platform, f"{self.uid_base(node)}_{control}"))

        for platform in PROGRAM_PLATFORMS:
            for _, program, _ in self.programs[platform]:
                current_unique_ids.add((platform, self.uid_base(program)))

        for platform in VARIABLE_PLATFORMS:
            for variable in self.variables[platform]:
                current_unique_ids.add((platform, self.uid_base(variable)))
                if platform == Platform.NUMBER:
                    current_unique_ids.add(
                        (platform, f"{self.uid_base(variable)}_init")
                    )

        for platform in ROOT_NODE_PLATFORMS:
            for node in self.root_nodes[platform]:
                current_unique_ids.add((platform, f"{self.uid_base(node)}_query"))
                if platform == Platform.BUTTON and node.protocol == Protocol.INSTEON:
                    current_unique_ids.add((platform, f"{self.uid_base(node)}_beep"))

        for resource in self.net_resources:
            current_unique_ids.add((Platform.BUTTON, self.uid_base(resource)))

        # EVENT-specific unique-id format. If more NODE_PARALLEL_PLATFORMS
        # are added with their own suffixes, generalize this loop to dispatch
        # by platform.
        for node in self.nodes[Platform.EVENT]:
            current_unique_ids.add(
                (
                    Platform.EVENT,
                    f"{self.uid_base(node)}{EVENT_BUTTON_UNIQUE_ID_SUFFIX}",
                )
            )

        return current_unique_ids

    @property
    def node_event_unique_ids(self) -> dict[str, Platform]:
        """Return all the unique ids to use for node events."""
        current_unique_ids: dict[str, Platform] = {}

        # Structure and prefixes here must match what's added in __init__ and helpers
        for platform in NODE_PLATFORMS:
            for node in self.nodes[platform]:
                current_unique_ids[self.uid_base(node)] = platform

        for node in self.nodes[Platform.EVENT]:
            current_unique_ids[
                f"{self.uid_base(node)}{EVENT_BUTTON_UNIQUE_ID_SUFFIX}"
            ] = Platform.EVENT

        for group in self.groups:
            current_unique_ids[self.uid_base(group)] = Platform.SWITCH

        return current_unique_ids


IsyConfigEntry = ConfigEntry[IsyData]
