### Purpose

This file gives concise, actionable guidance for AI coding agents working in the `hacs-isy994` Home Assistant custom integration and its closely-related `pyisyox` library.

**Home Assistant Compatibility:** This integration follows [Home Assistant Core development guidelines](https://github.com/home-assistant/core/blob/dev/.github/copilot-instructions.md). Maintain compatibility with Core patterns when making changes. See [UPDATE_PLAN.md](../UPDATE_PLAN.md) for modernization tasks.

**Scope:** primary work in this repository is in [custom_components/isy994](../custom_components/isy994/__init__.py). Co-development target: the `pyisyox` package in the sibling repo `pyisyox/`.

**High-level architecture (big picture)**
- The integration is a Home Assistant custom component located at [custom_components/isy994](../custom_components/isy994/__init__.py). It uses Home Assistant config entries and forwards platform setups via the `PLATFORMS` list.
- The ISY client is provided by the external library `pyisyox`. The integration instantiates `pyisyox.ISY` and calls `initialize(...)` to load nodes/programs/variables; the websocket event stream is started/stopped with `isy.websocket.start()` / `.stop()`.
- Data model: `IsyData` (see [custom_components/isy994/models.py](../custom_components/isy994/models.py)) stores categorized nodes, devices, programs, variables, and auxiliary properties. Helpers in [custom_components/isy994/helpers.py](../custom_components/isy994/helpers.py) perform the node->platform classification; the classification order is intentionally significant.
- Services and runtime behaviors are declared in [custom_components/isy994/services.py](../custom_components/isy994/services.py) and [services.yaml](../custom_components/isy994/services.yaml).

**Patterns and important conventions (project-specific)**
- Node classification order matters: helpers._categorize_nodes runs many checks (node_def → insteon type → zwave cat → uom → fallback). Preserve the order when refactoring.
- Use `IsyData` for shared state rather than global module variables; add devices into `isy_data.devices`, platform lists into `isy_data.nodes`, and aux properties into `isy_data.aux_properties`.
- Platform code (binary_sensor, sensor, switch, etc.) lives under `custom_components/isy994/` as standard HA platform modules. Follow existing entity naming and `DeviceInfo` creation pattern from `_generate_device_info` in `helpers.py`.
- Config entry lifecycle: initialization is performed in `async_setup_entry` and teardown in `async_unload_entry`; use `entry.add_update_listener` for options changes and `EVENT_HOMEASSISTANT_STOP` to stop websockets.
- When adding new Home Assistant services, define them in `services.yaml` and register in `async_setup_services` (see `services.py`).

**Testing & developer workflows (how to run/debug)**
- Tests use `pytest` + `pytest_homeassistant_custom_component`. Root tests folder: [tests/](../tests/). Global fixtures are in [tests/conftest.py](../tests/conftest.py).
- Run tests from repository root: `pytest -q` (or simply `pytest`). Mock network/ISY behavior by patching `pyisyox.ISY.initialize` or other `pyisyox` objects. Example pattern: patch `pyisyox.ISY` methods in tests to avoid network calls.
- Devcontainer: both this repo and `pyisyox` include DevContainer instructions in their READMEs. For co-development mount `pyisyox` locally and `pip install -e /workspaces/PyISY` (or `pyisyox`) inside the container.
- Formatting & linters: `black`, `isort`, `ruff`, and `pylint` are configured (see `pyproject.toml`). Use `pre-commit run --all-files` to check hooks.

**Co-development with `pyisyox`**
- `pyisyox` is the runtime dependency and should be developed in tandem. When making API or behavior changes in `pyisyox`:
  - Update tests in both `pyisyox` and `hacs-isy994` to reflect new behavior.
  - Install the local `pyisyox` into the integration dev environment via `pip install -e ../pyisyox` (devcontainer README covers this exact setup).
  - Keep a clear separation: networking and parsing lives in `pyisyox`; Home Assistant glue (entity lifecycle, registry, devices) stays in `hacs-isy994`.
- **Understanding PyISYoX connection flow**: See [pyisyox/docs/connection-flow.md](../../pyisyox/docs/connection-flow.md) for a detailed explanation of:
  - The complete sequence of REST API endpoint calls during `isy.initialize()`
  - How platforms load in parallel (nodes, programs, variables, etc.)
  - WebSocket vs TCP event stream setup and lifecycle
  - Connection limits, retry logic, and error handling
  - This is essential for debugging initialization issues or understanding performance characteristics.
- **Understanding Entity Creation Flow**: See [../docs/entity-creation-flow.md](../docs/entity-creation-flow.md) for comprehensive documentation on:
  - The 5-phase entity creation process from ISY connection to Home Assistant entities
  - Node categorization methods and filter system (node_def_id, Insteon type, Z-Wave category, UOM, states)
  - How ISY programs map to HA entities via folder structure (`HA.{platform}/Name/status` + `actions`)
  - Special case handling for complex devices (FanLinc light, thermostat subnodes, IOLinc relay)
  - How to extend `NODE_FILTERS` in `const.py` for new device types
  - Critical for understanding `helpers._categorize_nodes()` logic and why order matters

**Common edits and examples**
- To add a new platform entity type: add classification logic in `helpers._categorize_nodes`, add device info in `_generate_device_info`, then add platform module under `custom_components/isy994/<platform>.py` and list it in `PLATFORMS`.
- To add a new ISY-exposed action: implement API call in `pyisyox`, expose a Home Assistant service in `services.yaml`, and wire it in `services.py`.
- To mock ISY for tests: patch `pyisyox.ISY.initialize` to return quickly and set `isy.nodes`, `isy.programs`, `isy.variables` with minimal objects; use fixtures in [tests/conftest.py](../tests/conftest.py) as a template.

**Where to look first (key files)**
- Integration entrypoint: [custom_components/isy994/__init__.py](../custom_components/isy994/__init__.py)
- Node classification & device model: [custom_components/isy994/helpers.py](../custom_components/isy994/helpers.py) and [custom_components/isy994/models.py](../custom_components/isy994/models.py)
- Services: [custom_components/isy994/services.py](../custom_components/isy994/services.py) and [custom_components/isy994/services.yaml](../custom_components/isy994/services.yaml)
- Tests & fixtures: [tests/](../tests/) and [tests/conftest.py](../tests/conftest.py)
- Third-party client library: sibling repo [pyisyox/](../pyisyox) (see its README for examples)

**Agent behavior rules (do this first when editing code)**
1. Run the test suite in both repos after any API change to `pyisyox`.
2. Preserve the node classification order in `helpers.py` unless you intentionally change behavior and update tests.
3. Use `IsyData` for shared state changes; don't add ad-hoc globals.
4. Keep Home Assistant patterns (async config entry flow, entity/device registration) intact—use existing helper functions where possible.

If anything in this file is unclear or you want more examples (unit-test snippets, local dev steps, or common mock patterns), tell me which area to expand and I'll update this instruction file.
