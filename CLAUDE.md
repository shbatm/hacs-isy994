# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a **HACS Custom Component** for Home Assistant that integrates with Universal Devices ISY994/IoX controllers. It serves as a beta testing ground for new features before they're merged into the Home Assistant Core ISY994 integration. The integration uses PyISYoX (v4.x) to communicate with ISY controllers.

## Home Assistant Compatibility

This integration follows [Home Assistant Core development guidelines](https://github.com/home-assistant/core/blob/dev/.github/copilot-instructions.md). Key patterns implemented:

**Followed Patterns:**
- Config entry lifecycle (`async_setup_entry`, `async_unload_entry`)
- Entity unique IDs for all entities
- Async I/O throughout (no blocking calls)
- Config flow with UI-based setup
- Device registry integration
- Proper entity availability handling

**Intentional Differences:**
- **Event-driven updates**: Uses PyISYoX WebSocket events instead of `DataUpdateCoordinator` (ISY provides real-time push updates)
- **Runtime data storage**: Currently uses `hass.data[DOMAIN][entry_id]` pattern; migration to `ConfigEntry.runtime_data` is recommended for future updates to align with modern HA Core patterns
- **Quality Scale**: As a HACS component, not subject to Core Quality Scale tiers

**When modifying this integration:**
- Follow HA Core async programming patterns
- Use proper type hints on new code
- Maintain entity unique ID conventions
- Test config flow changes thoroughly

**Modernization Plan:**
See [UPDATE_PLAN.md](./UPDATE_PLAN.md) for a comprehensive list of updates needed to bring this component to current HA standards (created December 2024).

## Development Setup

### Local Development (without DevContainer)
```bash
# Install dependencies and setup pre-commit hooks
./scripts/setup

# Start Home Assistant with debug mode
./scripts/develop
```

### DevContainer Development (Recommended)
The DevContainer provides a complete Home Assistant test environment:

```bash
# After opening in DevContainer, activate the venv
source /opt/venv/bin/activate

# Run tests
pytest tests/

# Run Home Assistant (via VS Code task or manually)
hass -c /workspaces/hacs-isy994/.homeassistant
```

### DevContainer Support
This repository includes a modern VSCode DevContainer for consistent development and testing with Home Assistant.

**Features:**
- Automatically installs Home Assistant (pre-release) with test fixtures
- Mounts PyISYoX from `../pyisyox` and installs it in editable mode
- Creates `.homeassistant` runtime directory with symlinked `custom_components`
- Includes VS Code tasks for running Home Assistant and pytest
- Maps port 9123 (host) → 8123 (container) for Home Assistant access

**Quick Start:**
1. Open repository in VS Code
2. "Reopen in Container" when prompted
3. Wait for automatic setup to complete
4. Activate venv: `source /opt/venv/bin/activate`
5. Run tests: `pytest tests/`
6. Start HA: Use VS Code task "Start Home Assistant (devcontainer)"

**Co-developing with PyISYoX:**
If `../pyisyox` exists, it's automatically installed in editable mode during container creation. Changes to PyISYoX are immediately reflected without reinstalling.

See `.devcontainer/README.md` for detailed usage instructions.

## Code Quality & Testing

### Linting & Formatting
```bash
# Run pre-commit hooks manually
pre-commit run --all-files

# Format code with black
black custom_components/isy994

# Run ruff linter
ruff check custom_components/isy994 --fix
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_specific.py
```

**Note**: Test infrastructure exists but test coverage is minimal (only conftest.py present).

## Architecture

### Component Structure

**Entry Point (`__init__.py`)**:
- `async_setup_entry()`: Main setup function that initializes ISY connection and loads platforms
- Creates `IsyData` object to hold all integration state
- Categorizes nodes, programs, variables, and network resources via helper functions
- Starts WebSocket event stream for real-time updates
- Registers integration-wide services

**Data Model (`models.py`)**:
- `IsyData`: Central data class holding all ISY entities organized by platform
  - `root`: ISY controller instance
  - `nodes`: Dict of Node objects by platform
  - `groups`: ISY scenes/groups
  - `programs`: ISY programs
  - `variables`: ISY variables
  - `net_resources`: Network resources
  - `aux_properties`: Auxiliary node properties (on_level, ramp_rate)
  - Provides `unique_ids` property for entity registry cleanup

**Node Categorization (`helpers.py`)**:
- `_categorize_nodes()`: Main function that sorts ISY nodes into Home Assistant platforms
- Uses multiple filter strategies in order:
  1. `node_def_id` (most reliable, ISY v5.0+)
  2. Node server definitions (custom node servers)
  3. Insteon device type
  4. Z-Wave category
  5. UOM (Unit of Measure) and states fallback
- Handles special subnodes (FanLinc light, climate heat/cool, etc.)
- Identifies auxiliary properties for number/select entities

**Entity Base Classes (`entity.py`)**:
- `ISYEntity`: Base class for all ISY entities
  - Handles event subscription via `_node.status_events.subscribe()`
  - Provides device info and unique ID generation
  - Sets `should_poll = False` (event-driven updates)
- `ISYNodeEntity`, `ISYGroupEntity`, `ISYProgramEntity`, etc.: Specialized base classes

**Platform Modules**:
Each platform (sensor.py, light.py, switch.py, etc.) follows a similar pattern:
- `async_setup_entry()`: Creates entities from categorized nodes
- Platform-specific entity classes extending base ISYEntity
- Device-specific mappings (e.g., ISY UOM to HA device classes)

### Key Concepts

**Platforms Used**:
- Node-based: binary_sensor, climate, cover, fan, light, lock, sensor, switch
- Auxiliary properties: number (on_level), select (ramp_rate)
- Program-based: binary_sensor, cover, fan, lock, switch
- Variables: number, sensor
- Network resources: button
- Root node: button (query, beep)

**ISY Device Types**:
- **Insteon**: Identified by type category (e.g., "1." = dimmable, "2." = switched)
- **Z-Wave**: Identified by category number (e.g., "109" = dimmer)
- **Node Servers**: Custom device types with their own definitions

**Special Handling**:
- ISY Scenes are treated as switches (not HA scenes) because they can turn off and report state
- Some devices have "subnodes" (e.g., FanLinc has separate fan and light nodes)
- Auxiliary properties create separate entities (e.g., on_level becomes a number entity)
- Network resources are disabled by default (opt-in via options)

**Unit Conversions**:
The integration maps ISY Units of Measure (UOM) to Home Assistant units:
- UOM definitions in `const.py`: `UOM_FRIENDLY_NAME`, `UOM_TO_STATES`
- Conversion logic in `helpers.py`: `convert_isy_value_to_hass()`
- Special handling for temperature (Celsius/Fahrenheit), barriers (0-100%), HVAC modes

**Event Handling**:
- PyISYoX provides event-driven updates via WebSocket
- Entities subscribe to `status_events` in `async_added_to_hass()`
- Controller-level events handled by `IsyControllerEvents` class (events.py)
- Node events fire HA events for automation triggers

### Configuration Options

Configured via config_flow.py with options to disable unused features:
- `enable_programs`: Load ISY programs (default: True)
- `enable_variables`: Load ISY variables (default: True)
- `enable_nodeservers`: Load node server details (default: True)
- `enable_networking`: Load network resources (default: False)
- `ignore_string`: String in node names to ignore (default: "{IGNORE ME}")
- `sensor_string`: Force nodes to sensors (default: "sensor")
- `restore_light_state`: Restore light state on restart (default: False)

## Important Constants

**Filtering (`const.py`)**:
- `NODE_FILTERS`: Platform-specific filters by UOM, states, node_def_id, insteon_type, zwave_cat
- `NODE_AUX_FILTERS`: Maps aux properties (PROP_ON_LEVEL, PROP_RAMP_RATE) to platforms
- `SUPPORTED_BIN_SENS_CLASSES`: Binary sensor device classes to categorize

**Platform Lists**:
- `NODE_PLATFORMS`: Platforms from ISY nodes
- `PROGRAM_PLATFORMS`: Platforms from ISY programs
- `VARIABLE_PLATFORMS`: Platforms from ISY variables
- `PLATFORMS`: All platforms used by integration

## Code Style

The project follows Home Assistant's code style:
- **Black** for formatting (targets Python 3.9-3.10)
- **Ruff** for linting with Home Assistant-specific rules
- **isort** for import sorting (profile: black, known_first_party: homeassistant)
- **Pylint** with Home Assistant configuration (jobs=2)

Key style points from pyproject.toml:
- Line length: Black default (88 chars)
- Target Python version: 3.10+
- Docstring style: Google (D213 multi-line on second line)
- Many complexity checks disabled for readability (too-many-branches, etc.)

## Pre-commit Hooks

The repository uses pre-commit with:
- ruff (auto-fix enabled)
- black (quiet mode)
- isort
- codespell (ignores Home Assistant-specific terms)
- yamllint
- prettier
- check-json
- no-commit-to-branch (blocks commits to `dev` and `main`)

**Important**: Direct commits to `dev` and `main` branches are blocked by pre-commit hooks.

## PyISYoX Dependency

This integration is tightly coupled with PyISYoX:
- Uses beta/development versions for testing new features
- PyISYoX handles all ISY communication, XML parsing, and WebSocket events
- If making changes that require PyISY updates, co-develop using the DevContainer mount structure

**PyISYoX Documentation**: See `../pyisyox/CLAUDE.md` for comprehensive PyISYoX architecture and development guide.

Key PyISYoX concepts:
- `ISY`: Main controller object that manages the entire connection
- `Node`: Individual device/node on ISY (Insteon, Z-Wave, etc.)
- `Group`: ISY scene (collection of nodes)
- `Program`: ISY program with status/actions
- `Variable`: ISY variable (integer or state)
- `NetworkCommand`: Network resource command
- Event system: All entities emit events via `EventEmitter` for real-time updates

**Understanding PyISYoX Connection Flow**: For a detailed explanation of how PyISYoX establishes connections, loads platforms, and sets up event streams, see [../pyisyox/docs/connection-flow.md](../pyisyox/docs/connection-flow.md). This document covers:
- The complete sequence of REST API endpoint calls during initialization
- How platforms load in parallel (nodes, programs, variables, etc.)
- WebSocket vs TCP event stream setup and lifecycle
- Connection limits, retry logic, and error handling
- Essential for debugging initialization issues or understanding performance

**Understanding Entity Creation Flow**: For a comprehensive explanation of how this integration categorizes ISY nodes and creates Home Assistant entities, see [docs/entity-creation-flow.md](docs/entity-creation-flow.md). This document covers:
- The 5-phase entity creation process (setup, node categorization, program categorization, variable categorization, platform entity creation)
- Node categorization detection methods (node_def_id, Insteon type, Z-Wave category, UOM, etc.) in priority order
- How ISY programs become Home Assistant entities using folder structure
- Special case handling for multi-node devices (FanLinc, thermostats, IOLinc)
- Filter system architecture and how to extend it for new device types
- Essential for understanding how ISY devices map to HA platforms

### Co-Development with PyISYoX

When working on features that span both repositories:
1. Both repos should be in the same parent directory:
   ```
   parent/
   ├── hacs-isy994/
   └── pyisyox/
   ```
2. Use the DevContainer which automatically mounts both:
   - `/workspaces/hacs-isy994` (this repo)
   - `/workspaces/pyisyox` (PyISYoX)
3. PyISYoX is automatically installed in editable mode during container creation
4. Changes to PyISYoX are immediately reflected in the integration
5. Test both together before committing

**Manually installing PyISYoX in editable mode (if needed):**
```bash
source /opt/venv/bin/activate
pip install -e /workspaces/pyisyox
```
