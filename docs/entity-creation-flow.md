# Home Assistant ISY994 Entity Creation Flow

This document provides a comprehensive narrative of how the Home Assistant ISY994 integration creates and categorizes entities after PyISYoX establishes a connection to the ISY controller.

## Table of Contents

- [Overview](#overview)
- [Phase 1: Integration Setup](#phase-1-integration-setup)
- [Phase 2: Node Categorization](#phase-2-node-categorization)
- [Phase 3: Program Categorization](#phase-3-program-categorization)
- [Phase 4: Variable Categorization](#phase-4-variable-categorization)
- [Phase 5: Platform Entity Creation](#phase-5-platform-entity-creation)
- [Complete Entity Flow Diagram](#complete-entity-flow-diagram)
- [Categorization Filter System](#categorization-filter-system)

## Overview

The entity creation process happens in five sequential phases:

1. **Integration Setup** - Initialize ISY connection via PyISYoX
2. **Node Categorization** - Sort ISY nodes into Home Assistant platforms
3. **Program Categorization** - Organize ISY programs into platforms
4. **Variable Categorization** - Assign ISY variables to platforms
5. **Platform Entity Creation** - Create Home Assistant entities from categorized data

**Total Time**: Typically 2-5 seconds for medium-sized systems (50-200 devices)

**Important**: This document assumes PyISYoX has already connected and loaded platform data. For details on that process, see [pyisyox/docs/connection-flow.md](../../pyisyox/docs/connection-flow.md).

## Phase 1: Integration Setup

### Entry Point: `async_setup_entry()`

**Location**: `custom_components/isy994/__init__.py:66-182`

When Home Assistant loads the ISY994 config entry, the following sequence executes:

### Step 1.1: Initialize Data Model

```python
isy_data = IsyData()
entry.runtime_data = isy_data
```

**What is `IsyData`?** (`models.py:34-137`)

A central data structure that organizes all ISY entities by platform:

```python
@dataclass
class IsyData:
    root: ISY                                    # PyISYoX controller instance
    nodes: dict[Platform, list[Node]]            # Nodes by platform
    groups: list[Group]                          # ISY scenes/groups
    root_nodes: dict[Platform, list[Node]]       # Root nodes (for query/beep buttons)
    variables: dict[Platform, list[Variable]]    # Variables by platform
    programs: dict[Platform, list[tuple]]        # Programs by platform
    net_resources: list[NetworkCommand]          # Network resources
    devices: dict[str, DeviceInfo]               # Device registry info
    aux_properties: dict[Platform, list[tuple]]  # Auxiliary properties (on_level, etc.)
    controller_events: IsyControllerEvents       # Event handler
```

**Platform Lists Created** (`const.py:91-125`):

- **NODE_PLATFORMS**: binary_sensor, climate, cover, fan, light, lock, sensor, switch
- **NODE_AUX_PROP_PLATFORMS**: binary_sensor, number, select, sensor, switch
- **PROGRAM_PLATFORMS**: binary_sensor, cover, fan, lock, switch
- **VARIABLE_PLATFORMS**: number, sensor
- **ROOT_NODE_PLATFORMS**: button

Each platform list is initialized empty, ready to be populated during categorization.

### Step 1.2: Extract Configuration

```python
user = isy_config[CONF_USERNAME]
password = isy_config[CONF_PASSWORD]
host = urlparse(isy_config[CONF_HOST])

enable_variables = isy_options.get(CONF_ENABLE_VARIABLES, True)
enable_nodeservers = isy_options.get(CONF_ENABLE_NODESERVERS, True)
enable_programs = isy_options.get(CONF_ENABLE_PROGRAMS, True)
enable_networking = isy_options.get(CONF_ENABLE_NETWORKING, False)
```

**User Configuration Options**:
- Variables: Enabled by default
- Programs: Enabled by default
- Node Servers: Enabled by default
- Networking: **Disabled by default** (opt-in)

### Step 1.3: Create PyISYoX Connection

```python
connection_info = ISYConnectionInfo(
    isy_config[CONF_HOST],
    user,
    password,
    tls_version=tls_version if tls_version != DEFAULT_TLS_VERSION else None,
    websession=session,  # Shared aiohttp session from Home Assistant
)

isy = ISY(connection_info)
```

**Important**: Home Assistant provides its own `aiohttp.ClientSession` to share connection pooling across all integrations.

### Step 1.4: Initialize ISY Connection

```python
async with asyncio.timeout(60):
    await isy.initialize(
        nodes=True,          # Always load nodes
        clock=False,         # Clock not used by integration
        programs=enable_programs,
        variables=enable_variables,
        networking=enable_networking,
        node_servers=enable_nodeservers,
    )
```

**Timeout**: 60 seconds total for all ISY platform loading

**Error Handling**:
- `ISYInvalidAuthError` → `ConfigEntryAuthFailed` (prompts for new credentials)
- `ISYConnectionError` → `ConfigEntryNotReady` (retry on next poll)
- `ISYResponseParseError` → `ConfigEntryNotReady` (firmware upgrade may be needed)
- `TimeoutError` → `ConfigEntryNotReady` (ISY may be busy)

At this point, PyISYoX has loaded all data:
- `isy.nodes` - All nodes, groups, folders
- `isy.programs` - All programs
- `isy.variables` - All variables
- `isy.networking` - Network resources (if enabled)

**Next**: Categorize this raw data into Home Assistant platforms.

---

## Phase 2: Node Categorization

### Entry Point: `_categorize_nodes()`

**Location**: `custom_components/isy994/helpers.py:341-408`

**Called**: `__init__.py:141`

```python
_categorize_nodes(isy_data, isy.nodes, isy_options)
```

### Purpose

Transform ISY nodes from PyISYoX into organized lists by Home Assistant platform type (light, switch, sensor, etc.).

### How It Works

The categorization logic processes **every node in the ISY node tree** in a specific order to ensure consistent, accurate platform assignment.

### Step 2.1: Iterate Through Node Directory

```python
directory = nodes.get_directory()
for path, node in directory.items():
```

**What is `directory`?**

A dict of **all nodes** with their full ISY path as keys:
```python
{
    "My House/Living Room/Lamp": <Node at 1A 2B 3C 1>,
    "My House/Kitchen/Switch": <Node at 1A 2B 3C 2>,
    # ... etc
}
```

This includes:
- Folders (organizational only, skipped)
- Root nodes (physical devices)
- Child nodes (sub-devices like FanLinc light)
- Groups (ISY scenes)

### Step 2.2: Skip Ignored Nodes

```python
ignore_identifier = isy_options.get(CONF_IGNORE_STRING, DEFAULT_IGNORE_STRING)
if ignore_identifier in path or node.protocol == Protocol.NODE_FOLDER:
    continue
```

**Default ignore string**: `{IGNORE ME}`

Nodes with this string in their name or path are completely excluded from Home Assistant.

### Step 2.3: Process Root Nodes (Physical Devices)

```python
if isinstance(node, Node) and node.is_device_root:
    # This is a physical device / parent node
    isy_data.devices[node.address] = _generate_device_info(node)
    isy_data.root_nodes[Platform.BUTTON].append(node)
```

**Root Node Processing**:

1. **Create Device Registry Entry** (`helpers.py:304-338`):
   ```python
   DeviceInfo(
       identifiers={(DOMAIN, f"{isy.uuid}_{node.address}")},
       manufacturer=node.protocol.name.title(),  # "Insteon", "Z-Wave", etc.
       name=node.name,
       model=f"{node.address}: {node.node_def_id} ({node.type_})",
       via_device=(DOMAIN, isy.uuid),  # Link to ISY hub
       configuration_url=isy.conn.url,
       suggested_area=isy.nodes.get_folder(node.address),  # From ISY folder structure
   )
   ```

2. **Add Query/Beep Button**:
   - All root nodes get a "Query" button entity (forces ISY to update status)
   - Insteon root nodes also get a "Beep" button entity

3. **Add Communication Error Sensor**:
   ```python
   isy_data.aux_properties[Platform.SENSOR].append((node, PROP_COMMS_ERROR))
   ```
   - Every physical device gets a binary sensor showing if communication failed

4. **Add Auxiliary Properties** (for dimmable devices):
   ```python
   if getattr(node, "is_dimmable", False):
       aux_controls = {PROP_ON_LEVEL, PROP_RAMP_RATE}.intersection(node.aux_properties)
       for control in aux_controls:
           platform = NODE_AUX_FILTERS[control]  # ON_LEVEL → Number, RAMP_RATE → Select
           isy_data.aux_properties[platform].append((node, control))
   ```
   - **On Level** → Number entity (set default brightness)
   - **Ramp Rate** → Select entity (set fade time)

5. **Add Enable Switch** (if supported):
   ```python
   if hasattr(node, TAG_ENABLED):
       isy_data.aux_properties[Platform.SWITCH].append((node, TAG_ENABLED))
   ```

6. **Add Backlight Control** (if supported):
   ```python
   _add_backlight_if_supported(isy_data, node)
   ```
   - Keypad backlight brightness → Number or Select entity

### Step 2.4: Process Groups (ISY Scenes)

```python
if isinstance(node, Group):
    isy_data.groups.append(node)
    continue
```

**Important**: ISY scenes become **Switches** in Home Assistant, not Scene entities. This is because ISY scenes:
- Can be turned on AND off
- Report their current state
- Act more like switches than HA's stateless scenes

Groups are linked to their controller device if they have only one controller.

### Step 2.5: Process Auxiliary Properties (Non-Root Nodes)

```python
for control in node.aux_properties:
    if control in SKIP_AUX_PROPS:  # Skip STATUS, BUSY, COMMS_ERROR (already handled)
        continue
    platform = Platform.SENSOR
    if node.aux_properties[control].uom in BINARY_SENSOR_UOMS:  # UOM 2 or 78
        platform = Platform.BINARY_SENSOR
    isy_data.aux_properties[platform].append((node, control))
```

**Auxiliary Properties** are additional controls/sensors on nodes:
- Temperature sensors on thermostats
- Humidity sensors on climate devices
- Battery level sensors
- Motion sensor tamper switches
- Etc.

Most become sensors unless their UOM indicates binary (on/off) state.

### Step 2.6: User-Forced Sensor Override

```python
sensor_identifier = isy_options.get(CONF_SENSOR_STRING, DEFAULT_SENSOR_STRING)
if sensor_identifier in path or sensor_identifier in node.name:
    if _is_sensor_a_binary_sensor(isy_data, node):
        continue  # Already added as binary_sensor
    isy_data.nodes[Platform.SENSOR].append(node)
    continue
```

**Default sensor string**: `"sensor"`

If a node's name or path contains this string, it's **forced to be a sensor**, bypassing all other categorization logic.

Then `_is_sensor_a_binary_sensor()` runs mini-categorization to determine if it should be a binary_sensor instead.

### Step 2.7: Platform Detection (The Core Logic)

This is where the magic happens. The integration tries **multiple detection methods** in a specific order, from most reliable to least.

**Critical**: The order matters! Once a node matches a method, categorization stops.

```python
# Order of attempts (most reliable → least reliable):
if _check_for_node_def(isy_data, node):
    continue
if _check_for_insteon_type(isy_data, node):
    continue
if _check_for_zwave_cat(isy_data, node):
    continue
if enable_nodeservers and _check_for_node_server_def(isy_data, node):
    continue
if _check_for_uom_id(isy_data, node):
    continue
if _check_for_states_in_uom(isy_data, node):
    continue

# Fallback: treat as sensor
isy_data.nodes[Platform.SENSOR].append(node)
```

Let's examine each detection method in detail:

---

#### Method 1: Node Definition ID (ISY v5.0+)

**Function**: `_check_for_node_def()` (`helpers.py:68-88`)

**Reliability**: ⭐⭐⭐⭐⭐ **HIGHEST** (available on ISY v5.0+ firmware)

**How It Works**:

```python
if not hasattr(node, "node_def_id") or node.node_def_id is None:
    return False  # Pre-v5.0 firmware

node_def_id = node.node_def_id  # e.g. "KeypadDimmer", "FanLinc", "BinaryAlarm"

for platform in NODE_PLATFORMS:
    if node_def_id in NODE_FILTERS[platform][FILTER_NODE_DEF_ID]:
        isy_data.nodes[platform].append(node)
        return True
```

**Example Node Def IDs** (`const.py:209-218`):

```python
Platform.BINARY_SENSOR: [
    "BinaryAlarm",
    "BinaryAlarm_ADV",
    "BinaryControl",
    "EZIO2x4_Input",
    "OnOffControl",
]
Platform.SENSOR: [
    "IMETER_SOLO",
    "KeypadButton",
    "RemoteLinc2",
]
```

**Why Most Reliable?**

The node definition ID is explicitly assigned by the ISY based on the device's actual capabilities, not inferred from other properties.

---

#### Method 2: Insteon Device Type

**Function**: `_check_for_insteon_type()` (`helpers.py:101-162`)

**Reliability**: ⭐⭐⭐⭐ **HIGH** (Insteon devices only)

**Applies To**: Nodes where `node.protocol == Protocol.INSTEON`

**How It Works**:

```python
if node.protocol != Protocol.INSTEON:
    return False

device_type = node.type_  # e.g. "1.32.65.0" (KeypadLinc Dimmer)

for platform in NODE_PLATFORMS:
    if any(device_type.startswith(t) for t in NODE_FILTERS[platform][FILTER_INSTEON_TYPE]):
        isy_data.nodes[platform].append(node)
        return True
```

**Insteon Type Categories** (`const.py:161-176`):

```python
TYPE_CATEGORY_DIMMABLE = "1."       # All dimmable lights
TYPE_CATEGORY_SWITCHED = "2."       # All on/off switches
TYPE_CATEGORY_CLIMATE = "5."        # Thermostats
TYPE_CATEGORY_COVER = "14."         # Garage doors, shades
TYPE_CATEGORY_LOCK = "15."          # Door locks
TYPE_CATEGORY_SAFETY = "16."        # Motion, leak, door sensors
```

**Example Filter** (`const.py:219-224`):

```python
Platform.BINARY_SENSOR: {
    FILTER_INSTEON_TYPE: [
        "7.0.",   # I/O Linc (sensor mode)
        "7.13.",  # Leak sensor
        "16.",    # All safety devices (motion, door, etc.)
    ],
}
```

**Special Case Handling**:

Some Insteon devices have **child nodes** that should be different platforms:

```python
subnode_id = int(node.address.split(" ")[-1], 16)

# FanLinc light (subnode 1) → Light instead of Fan
if platform == Platform.FAN and subnode_id == SUBNODE_FANLINC_LIGHT:
    isy_data.nodes[Platform.LIGHT].append(node)
    return True

# Thermostat heat/cool subnodes (2, 3) → Binary Sensor
if platform == Platform.CLIMATE and subnode_id in (SUBNODE_CLIMATE_COOL, SUBNODE_CLIMATE_HEAT):
    isy_data.nodes[Platform.BINARY_SENSOR].append(node)
    return True

# IOLinc relay (subnode 2) → Switch instead of Binary Sensor
if platform == Platform.BINARY_SENSOR and subnode_id == SUBNODE_IOLINC_RELAY:
    isy_data.nodes[Platform.SWITCH].append(node)
    return True
```

**Why These Exceptions?**

- **FanLinc**: Physical device with separate fan and light modules
- **Thermostats**: Report "heating" and "cooling" as separate binary states
- **IOLinc**: Dual-purpose device (sensor input + relay output)

---

#### Method 3: Z-Wave Category

**Function**: `_check_for_zwave_cat()` (`helpers.py:165-190`)

**Reliability**: ⭐⭐⭐⭐ **HIGH** (Z-Wave devices only)

**Applies To**: Nodes where `node.protocol == Protocol.ZWAVE`

**How It Works**:

```python
if node.protocol != Protocol.ZWAVE:
    return False

if not hasattr(node, "zwave_props") or node.zwave_props is None:
    return False

device_type = node.zwave_props.category  # e.g. "109" (multilevel switch)

for platform in NODE_PLATFORMS:
    if any(device_type.startswith(t) for t in NODE_FILTERS[platform][FILTER_ZWAVE_CAT]):
        isy_data.nodes[platform].append(node)
        return True
```

**Example Z-Wave Categories** (`const.py:224`, `248`):

```python
Platform.BINARY_SENSOR: {
    FILTER_ZWAVE_CAT: [
        "104",  # Door/window sensor
        "112",  # Motion sensor
        "148"-"179",  # Range of sensor types
    ]
}
Platform.SENSOR: {
    FILTER_ZWAVE_CAT: [
        "118",  # Multilevel sensor
        "143",  # Energy meter
        "180"-"185",  # Range of sensor types
    ]
}
```

**Z-Wave Device Info Enhancement**:

When generating `DeviceInfo` for Z-Wave nodes, additional metadata is included:

```python
if node.protocol == Protocol.ZWAVE and node.zwave_props is not None:
    device_info[ATTR_MANUFACTURER] = f"Z-Wave MfrID:{node.zwave_props.mfr_id}"
    model += f"Type:{node.zwave_props.prod_type_id} Product:{node.zwave_props.product_id}"
```

---

#### Method 4: Node Server Definitions

**Function**: `_check_for_node_server_def()` (`helpers.py:91-98`)

**Reliability**: ⭐⭐⭐ **MEDIUM** (custom node servers)

**Status**: **NOT YET IMPLEMENTED** (placeholder for future)

```python
def _check_for_node_server_def(isy_data: IsyData, node: Node) -> bool:
    """Check if the node is a Node Server node with assigned platforms."""
    # FUTURE: Move sorting here to check for binary_sensor, sensor, switch
    return False
```

**Why Important?**

Polyglot Node Servers define custom device types that don't follow Insteon/Z-Wave patterns. Future implementation will check node server definitions to determine platform.

Currently, these fall through to UOM-based detection or the sensor fallback.

---

#### Method 5: Unit of Measure (UOM) ID

**Function**: `_check_for_uom_id()` (`helpers.py:193-225`)

**Reliability**: ⭐⭐⭐ **MEDIUM**

**How It Works**:

```python
if not hasattr(node, "uom") or node.uom in (None, ""):
    return False

node_uom = node.uom
if isinstance(node.uom, list):  # ISYv4 compatibility
    node_uom = node.uom[0]

for platform in NODE_PLATFORMS:
    if node_uom in NODE_FILTERS[platform][FILTER_UOM]:
        isy_data.nodes[platform].append(node)
        return True
```

**What is UOM?**

**Unit of Measure** - ISY's way of indicating what a node's status value represents.

**Common UOMs**:
- `"2"` - On/Off (binary)
- `"51"` - Percentage (0-100%)
- `"100"` - 8-bit range (0-255, used for lights)
- `"4"` - Temperature (Fahrenheit)
- `"1"` - Temperature (Celsius)
- `"12"` - Kilowatt hours
- `"73"` - Watts

**Example UOM Filters** (`const.py:207`, `229-237`):

```python
Platform.BINARY_SENSOR: {
    FILTER_UOM: ["2"],  # On/Off only
}

Platform.SENSOR: {
    FILTER_UOM: [
        "1",              # Temperature Celsius
        "3"-"10",         # Various measurements
        "12"-"50",        # Energy, power, etc.
        "52"-"65",        # More measurements
        "69"-"77", "79",  # Even more
        "82"-"96",        # And more
    ],
}
```

**Why Less Reliable?**

UOM indicates the *type* of value, but doesn't always indicate the *purpose* of the device. For example, UOM "51" (percentage) could be:
- Light brightness
- Cover position
- Fan speed
- Generic sensor reading

This method only works when UOM strongly implies a specific platform.

---

#### Method 6: States in UOM (ISYv4)

**Function**: `_check_for_states_in_uom()` (`helpers.py:228-262`)

**Reliability**: ⭐⭐ **LOW** (ISYv4 firmware only)

**Applies To**: ISYv4 firmware where `uom` is a **list of state names**

**How It Works**:

```python
if not isinstance(node.uom, list):
    return False  # Not ISYv4 format

node_uom = set(map(str.lower, node.uom))  # e.g. {"on", "off"}

for platform in NODE_PLATFORMS:
    if node_uom == set(NODE_FILTERS[platform][FILTER_STATES]):
        isy_data.nodes[platform].append(node)
        return True
```

**Example**:

ISYv4 might report `uom = ["On", "Off"]` instead of UOM ID `"2"`.

The integration checks if the set of states exactly matches a platform's expected states.

**Why Least Reliable?**

- Only works on older ISYv4 firmware
- Requires exact state name matching
- Rare edge case in modern deployments

---

### Step 2.8: Fallback as Sensor

If **none** of the detection methods match:

```python
# Fallback as sensor, e.g. for un-sortable items like NodeServer nodes.
isy_data.nodes[Platform.SENSOR].append(node)
```

**Why Sensor?**

Sensors are the most generic platform - they can display any value with any unit of measurement. When the integration can't determine what a node is, treating it as a sensor ensures:
- It still appears in Home Assistant
- Users can see its value
- No functionality is lost (just maybe not the ideal entity type)

---

## Phase 3: Program Categorization

### Entry Point: `_categorize_programs()`

**Location**: `custom_components/isy994/helpers.py:410-449`

**Called**: `__init__.py:143-144`

```python
if enable_programs and isy.programs.loaded:
    _categorize_programs(isy_data, isy.programs)
```

### How ISY Programs Become Home Assistant Entities

ISY programs can be exposed as Home Assistant entities by organizing them into a specific folder structure.

### Required Folder Structure

```
ISY Programs
└── HA.{platform}/
    ├── My Device/
    │   ├── status
    │   └── actions
    └── Another Device/
        ├── status
        └── actions
```

**Folder Naming**: `HA.{platform}` where platform is one of:
- `HA.binary_sensor/`
- `HA.cover/`
- `HA.fan/`
- `HA.lock/`
- `HA.switch/`

### Program Pairing

Each entity requires **two programs**:

1. **Status Program**: Condition that determines entity state
   - Name must end with `/status`
   - `If` clause evaluates to true/false
   - `Then`/`Else` clauses are ignored

2. **Actions Program**: Commands to control the entity
   - Name must end with `/actions`
   - `Then` clause = turn on
   - `Else` clause = turn off
   - Condition is ignored

**Exception**: Binary sensors only need a status program (read-only).

### Step 3.1: Find Programs in Platform Folders

```python
directory = programs.get_directory()
for platform in PROGRAM_PLATFORMS:  # binary_sensor, cover, fan, lock, switch
    folder_name = f"{DEFAULT_PROGRAM_STRING}{platform}/"  # "HA.switch/"

    entities = {
        path.partition(folder_name)[2]: entity
        for path, entity in directory.items()
        if folder_name in path
    }
```

**Example `entities` dict**:

```python
{
    "Garage Door/status": <Program at 0x1234>,
    "Garage Door/actions": <Program at 0x5678>,
    "Front Light/status": <Program at 0xabcd>,
    "Front Light/actions": <Program at 0xef01>,
}
```

### Step 3.2: Separate Status and Actions Programs

```python
status_programs = {
    path.rstrip(f"/{KEY_STATUS}"): status
    for path, status in entities.items()
    if path.endswith(KEY_STATUS)
}
# Result: {"Garage Door": <Program>, "Front Light": <Program>}

action_programs = {
    path.rstrip(f"/{KEY_ACTIONS}"): action
    for path, action in entities.items()
    if path.endswith(KEY_ACTIONS)
}
# Result: {"Garage Door": <Program>, "Front Light": <Program>}
```

### Step 3.3: Pair and Validate

```python
for name, program in status_programs.items():
    if platform != Platform.BINARY_SENSOR and name not in action_programs:
        _LOGGER.warning(
            "Program %s entity '%s' not loaded, invalid/missing actions program",
            platform, name
        )
    entity = (name, program, action_programs.get(name))
    isy_data.programs[platform].append(entity)
```

**Stored as Tuple**: `(name, status_program, actions_program | None)`

**Validation**:
- Binary sensors: Actions program optional
- All others: Actions program required (warning logged if missing)

### Example: ISY Program Switch

**ISY Setup**:
```
Programs
└── HA.switch/
    └── Landscape Lighting/
        ├── status
        │   If: $landscapeLightVar is 1
        │   Then: (nothing)
        │   Else: (nothing)
        └── actions
            If: (always true)
            Then: Set $landscapeLightVar = 1
            Else: Set $landscapeLightVar = 0
```

**Result**: A switch entity named "Landscape Lighting" in Home Assistant that:
- Shows "on" when `status` program condition is true
- Runs `actions` Then clause when turned on
- Runs `actions` Else clause when turned off

---

## Phase 4: Variable Categorization

### Entry Point: `_categorize_variables()`

**Location**: `custom_components/isy994/helpers.py:452-462`

**Called**: `__init__.py:146-150`

```python
if enable_variables and isy.variables.entities:
    _categorize_variables(isy_data, isy.variables)
    isy_data.devices[CONF_VARIABLES] = _create_service_device_info(
        isy, name=CONF_VARIABLES.title(), unique_id=CONF_VARIABLES
    )
```

### How It Works

**Simple**: All ISY variables become Number entities.

```python
numbers = isy_data.variables[Platform.NUMBER]
for variable in variables.values():
    numbers.append(variable)
```

**Why Number?**

ISY variables store integer values that can be:
- Read by Home Assistant
- Written to from Home Assistant
- Used in automations as conditions/triggers

The Number platform is perfect for this use case.

### Variable Types

ISY has two variable types (managed by PyISYoX):
1. **Integer Variables** (Type 1): General-purpose storage
2. **State Variables** (Type 2): Used by ISY programs

Both are treated identically in Home Assistant.

### Device Registry Entry

All variables are grouped under a single **virtual device**:

```python
_create_service_device_info(
    isy,
    name="Variables",
    unique_id="variables"
)
```

This creates a "Variables" device in the device registry containing all variable entities.

---

## Phase 5: Platform Entity Creation

### Entry Point: `async_forward_entry_setups()`

**Location**: `__init__.py:163`

```python
await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
```

**What Happens**: Home Assistant calls `async_setup_entry()` for each platform in parallel.

### Platform Setup Flow

Each platform file (e.g., `light.py`, `switch.py`) follows the same pattern:

#### Example: Light Platform

**File**: `custom_components/isy994/light.py:23-40`

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: IsyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ISY light platform."""
    isy_data = entry.runtime_data
    devices = isy_data.devices
    isy_options = entry.options
    restore_light_state = isy_options.get(CONF_RESTORE_LIGHT_STATE, False)

    entities = []
    for node in isy_data.nodes[Platform.LIGHT]:
        entities.append(
            ISYLightEntity(node, restore_light_state, devices.get(node.primary_node))
        )

    async_add_entities(entities)
```

**Process**:
1. Get categorized nodes from `isy_data.nodes[Platform.LIGHT]`
2. For each node, create platform-specific entity class
3. Pass device_info from device registry (links entity to device)
4. Add all entities at once via `async_add_entities()`

#### Example: Switch Platform (More Complex)

**File**: `custom_components/isy994/switch.py:36-84`

Switch platform creates **multiple entity types**:

```python
entities = []

# 1. Node-based switches
for node in isy_data.nodes[Platform.SWITCH]:
    entities.append(
        ISYSwitchEntity(node=node, device_info=device_info.get(node.primary_node))
    )

# 2. Group-based switches (ISY scenes)
for group in isy_data.groups:
    device = None
    if len(group.controllers) == 1:
        # Link to single controller device
        controller = isy_data.root.nodes.entities[group.controllers[0]]
        device = device_info.get(controller.primary_node)
    entities.append(ISYGroupSwitchEntity(node=group, device_info=device))

# 3. Program-based switches
for name, status, actions in isy_data.programs[Platform.SWITCH]:
    entities.append(ISYSwitchProgramEntity(name, status, actions))

# 4. Auxiliary property switches (enable/disable)
for node, control in isy_data.aux_properties[Platform.SWITCH]:
    description = ISYSwitchEntityDescription(
        key=control,
        device_class=SwitchDeviceClass.SWITCH,
        name=control.title(),
        entity_category=EntityCategory.CONFIG,
    )
    entities.append(
        ISYEnableSwitchEntity(
            node=node,
            control=control,
            unique_id=f"{isy_data.uid_base(node)}_{control}",
            description=description,
            device_info=device_info.get(node.primary_node),
        )
    )

async_add_entities(entities)
```

### Entity Base Classes

All platform entities inherit from base classes that provide common functionality:

**Entity Hierarchy**:
```
ISYEntity (base class)
├── ISYNodeEntity (for node-based entities)
├── ISYGroupEntity (for scene-based entities)
├── ISYProgramEntity (for program-based entities)
└── ISYAuxPropertyEntity (for auxiliary controls)
```

**What Base Classes Provide** (`entity.py`):

1. **Automatic Updates**:
   ```python
   async def async_added_to_hass(self) -> None:
       self._node.status_events.subscribe(self.async_on_update, key=self.unique_id)
   ```
   Entities subscribe to PyISYoX events and update automatically.

2. **Unique IDs**:
   ```python
   @property
   def unique_id(self) -> str:
       return f"{self._isy_data.uuid}_{self._node.address}"
   ```

3. **Device Linking**:
   ```python
   @property
   def device_info(self) -> DeviceInfo | None:
       return self._device_info
   ```

4. **Should Poll = False**:
   ```python
   _attr_should_poll = False
   ```
   All entities are event-driven via WebSocket, no polling needed.

---

## Complete Entity Flow Diagram

```
PyISYoX Connection Established
         │
         v
┌────────────────────────────────────────┐
│  Phase 1: Integration Setup            │
│  - Create IsyData structure            │
│  - Initialize empty platform lists     │
│  - Load config options                 │
└────────────────┬───────────────────────┘
                 │
                 v
┌────────────────────────────────────────┐
│  Phase 2: Node Categorization          │
│  - Iterate all nodes                   │
│  - Skip ignored nodes                  │
│  - Process root nodes:                 │
│    • Create device registry entry      │
│    • Add query/beep buttons            │
│    • Add comm error sensor             │
│    • Add aux properties                │
│  - Process groups                      │
│  - Detect platform via:                │
│    1. Node Def ID (v5.0+)             │
│    2. Insteon Type                     │
│    3. Z-Wave Category                  │
│    4. Node Server Def (future)         │
│    5. UOM ID                           │
│    6. States in UOM (v4)               │
│    7. Fallback to sensor               │
└────────────────┬───────────────────────┘
                 │
                 v
┌────────────────────────────────────────┐
│  Phase 3: Program Categorization       │
│  - Find HA.{platform} folders          │
│  - Pair status/actions programs        │
│  - Validate and store tuples           │
└────────────────┬───────────────────────┘
                 │
                 v
┌────────────────────────────────────────┐
│  Phase 4: Variable Categorization      │
│  - All variables → Number platform     │
│  - Create virtual Variables device     │
└────────────────┬───────────────────────┘
                 │
                 v
┌────────────────────────────────────────┐
│  Phase 5: Platform Entity Creation     │
│  - For each platform in parallel:      │
│    • Call async_setup_entry()          │
│    • Create entity instances           │
│    • Link to device registry           │
│    • Subscribe to PyISYoX events       │
│    • Add entities to Home Assistant    │
└────────────────┬───────────────────────┘
                 │
                 v
         ┌───────────────┐
         │  WebSocket    │
         │  Event Stream │
         │    Started    │
         └───────────────┘
                 │
                 v
         ┌───────────────┐
         │   Entities    │
         │    Active     │
         └───────────────┘
```

---

## Categorization Filter System

### Filter Types

The integration uses **five filter types** to categorize nodes, in this priority order:

| Priority | Filter Type | Source | Applies To | Reliability |
|----------|------------|--------|------------|-------------|
| 1 | `FILTER_NODE_DEF_ID` | `node.node_def_id` | ISY v5.0+ | Highest |
| 2 | `FILTER_INSTEON_TYPE` | `node.type_` | Insteon only | High |
| 3 | `FILTER_ZWAVE_CAT` | `node.zwave_props.category` | Z-Wave only | High |
| 4 | `FILTER_UOM` | `node.uom` | All nodes | Medium |
| 5 | `FILTER_STATES` | `node.uom` (list) | ISYv4 only | Low |

### Filter Definition Structure

**Location**: `custom_components/isy994/const.py:205-325`

```python
NODE_FILTERS: dict[Platform, dict[str, list[str]]] = {
    Platform.LIGHT: {
        FILTER_UOM: ["51", "100"],  # Percentage, 8-bit range
        FILTER_STATES: [],
        FILTER_NODE_DEF_ID: ["DimmerLampSwitch", "DimmerSwitchOnly", ...],
        FILTER_INSTEON_TYPE: ["1."],  # All category 1 (dimmable)
        FILTER_ZWAVE_CAT: ["109", "119"],
    },
    # ... other platforms
}
```

### How Filters Are Applied

**Check Flow**:

```python
# 1. Try node_def_id first (if available)
if node.node_def_id in NODE_FILTERS[platform][FILTER_NODE_DEF_ID]:
    add_to_platform(platform)
    return

# 2. Try protocol-specific type (Insteon or Z-Wave)
if node.protocol == INSTEON:
    if node.type_.startswith(any NODE_FILTERS[platform][FILTER_INSTEON_TYPE]):
        add_to_platform(platform)
        return
elif node.protocol == ZWAVE:
    if node.zwave_props.category in NODE_FILTERS[platform][FILTER_ZWAVE_CAT]:
        add_to_platform(platform)
        return

# 3. Try UOM (universal fallback)
if node.uom in NODE_FILTERS[platform][FILTER_UOM]:
    add_to_platform(platform)
    return

# 4. Try states (ISYv4 only)
if set(node.uom) == set(NODE_FILTERS[platform][FILTER_STATES]):
    add_to_platform(platform)
    return
```

### Auxiliary Property Filters

**Location**: `custom_components/isy994/const.py:326-329`

```python
NODE_AUX_FILTERS: dict[str, Platform] = {
    PROP_ON_LEVEL: Platform.NUMBER,      # Default brightness
    PROP_RAMP_RATE: Platform.SELECT,     # Fade time selector
}
```

**Simple Mapping**: Property type → Platform

---

## Summary

The entity creation process transforms raw ISY data into organized Home Assistant entities through a carefully orchestrated series of steps:

1. **Setup** - Initialize data structures and connect to ISY
2. **Node Categorization** - Use intelligent detection methods to sort nodes by platform
3. **Program Categorization** - Pair status/actions programs into controllable entities
4. **Variable Categorization** - Convert all variables to Number entities
5. **Entity Creation** - Instantiate platform-specific entity classes with event subscriptions

**Key Design Principles**:

- **Order Matters**: Categorization methods run from most → least reliable
- **Device Grouping**: Related entities link to parent devices
- **Event-Driven**: No polling, all updates via WebSocket
- **Extensible**: Easy to add new platforms or node types
- **Fallback Safety**: Unknown nodes become sensors rather than being hidden

**Performance Characteristics**:

- **Small System** (1-20 devices): < 1 second
- **Medium System** (50-100 devices): 2-3 seconds
- **Large System** (200+ devices): 3-5 seconds

**For Developers**:

When adding support for new device types:
1. Add filter values to `NODE_FILTERS` in `const.py`
2. Test with real hardware to verify correct categorization
3. Add special case handling in `helpers.py` if needed
4. Update this documentation with examples

---

## Related Documentation

- **PyISYoX Connection Flow**: [../../pyisyox/docs/connection-flow.md](../../pyisyox/docs/connection-flow.md)
- **Home Assistant ISY994 Integration**: [README.md](../README.md)
- **ISY REST API Reference**: https://www.universal-devices.com/developers/
