## CHANGELOG - HACS Version of ISY994 Component

### [1.5.0] - Merge with Home Assistant Core 0.110.0

- All code changes have been merged back into Core @ v0.110.0.

#### Breaking Changes:

Remove ISY Climate Module support: the ISY Climate Module was retired by UDI on 3/30/2020: UDI Announcement, support has been removed from the module, so any entities based on Climate module nodes will no longer import into Home Assistant. The enable_climate configuration option will need be removed from your YAML configuration file.

Nodes that are “grouped” together in the ISY Admin Console will now be correctly identified and sorted, this will cause additional entities to be added to Home Assistant. If you were using this “group” feature to ignore some sub-devices in Home Assistant, you will now need to use the ignore_string in the name instead.

Sorting of certain devices based on the ISY’s Node Def ID and Insteon Type properties have been corrected to match the ISY’s provided device categories, as well as user feedback of incorrect sorting for specific devices. As a result, some entities that were incorrectly categorized will now appear under a different platform (e.g. switch to binary_sensor, light to switch, etc.)

Both KeypadLinc Secondary Buttons and RemoteLinc2 Buttons have been moved from switch to sensor. This is because these buttons cannot actually be directly controlled via commands sent from the switch platform, doing so results in communication errors from the ISY because the commands are not valid. These devices are being moved to sensor instead of binary_sensor because they report a state in a range from 0 to 255; 0=Off, 255=On according to their last brightness/dimming level sent.

The ISY994 integration now includes a restore_light_state option. In 0.109.0, a change was made to restore a light’s brightness to the previous state when turned on with no brightness parameter. This was, in part, to fix an issue where the light to turn on to full brightness when no parameters were given, regardless of the physical device’s On Level brightness setting. Using the On Level is now supported and is the default behavior. To keep the current behavior and use Home Assistant’s last brightness, set the restore_light_state to True or enable the option in the new config flow options.

The following device node types have changed platforms to correct their categorization:

- “BinaryControl” (SWITCH->BINARY_SENSOR)
- “BinaryControl_ADV” (SWITCH->BINARY_SENSOR; IOLinc Sensor)
- “EZIO2x4_Input” (SWITCH->BINARY_SENSOR)
- “EZRAIN_Input” (SWITCH->BINARY_SENSOR)
- “OnOffControl” (SWITCH->BINARY_SENSOR)
- “OnOffControl_ADV” (New; Thermostat Control/Running Sensors)
- “EZIO2x4_Input_ADV” (SWITCH->SENSOR, Analog input on EZIO).
- “RemoteLinc2” (LIGHT->SWITCH),
- “RemoteLinc2_ADV” (LIGHT->SWITCH),
  - RemoteLincs only report button presses as events, are not controllable and do not accurately report dimmable states.
- New Insteon Types for BINARY_SENSORS: “7.0.”, “7.13.” (IOLinc/EZIO Sensors)
- New Insteon Type for LOCKS: “4.64.” added.
- New Insteon Types for SWITCHES: “0.16.”, “7.3.255.”, “9.10.”

### [1.4.3] - Bug Fixes and Core Catchup to 0.109.0

- Rename BinarySensorDevice to BinarySensorEntity (home-assistant/core#34462)
- Rename LockDevice to LockEntity (home-assistant/core#34594)
- Rename SwitchDevice to SwitchEntity (home-assistant/core#34673)
- Rename LockDevice to LockEntity (home-assistant/core#34594)
- Rename CoverDevice to CoverEntity (home-assistant/core#34595)
- Rename Light to LightEntity (home-assistant/core#34593)
- Rename ClimateDevice to ClimateEntity (home-assistant/core#34591)
- Fix restoring isy994 brightness with no previous state (home-assistant/core#34972)
- Rename "platform" (formerly "domain") to "component" to better align with Home Assistant terminology.

### [1.4.2]

### [1.4.1] - Added Reload and Cleanup Services, Bye-bye Beta!

- **MAJOR MILESTONE**: Good-bye beta! Now running on `pyisy==2.0.0`!
    + This is a major milestone towards enabling these changes to be migrated into the Home Assistant Core code, and have been over a year in the making!
- Added `isy994.reload` and `isy994.cleanup` services to reload the integration without restarting (to add new devices) and to cleanup old devices that have been removed or disabled on the ISY.

### [1.4.0] - Services, Variables Reavamped, Inheritance Fixes

#### BREAKING CHANGES!! - Variable Support Has Changed in this Version!

- To ensure future support and ability to merge the changes in this custom component into the Home Assistant core, some changes needed to be made to how variables were handled:
    + Variables are no longer configured in `configuration.yaml`.
    + A new `Variable Sensor String` config option has been added in the Integrations > Options page (or by using `variable_sensor_string: "HA."` in your `configuration.yaml`).
        * This behaves similarly to Sensor String and Ignore String for nodes: you need to rename the variables ***in your ISY*** to have the `Variable Sensor String` somewhere in the name.
        * If your Variable Sensor String is `"HA."` then every variable with `HA.` in the name will be imported as a sensor.
        * Additional configuration (changing device class, friendly name, unit of measurement, etc.) can be done using customizations in Home Assistant.
    + Variables as a `switch` or `binary_sensor` are no longer supported. This was a duplicate functionality that is already available [using Programs](https://www.home-assistant.io/integrations/isy994/#creating-custom-devices)

#### New:

- Add services to ISY994 Integration to access additional commands available in PyISY, such as fast on/off and fade up/down/stop as well as enable/disable nodes. The following services are now available:
     + `isy994.send_raw_node_command`: Send a "raw" ISY REST Device Command to a Node using its Home Assistant Entity ID.
     + `isy994.send_node_command`: Send a command to an ISY Device using its Home Assistant entity ID. Valid commands are: beep, brighten, dim, disable, enable, fade_down, fade_stop, fade_up, fast_off, fast_on, and query.
     + `isy994.set_on_level`: Send a ISY set_on_level command to a Node.
     + `isy994.set_ramp_rate`: Send a ISY set_ramp_rate command to a Node.
     + `isy994.system_query`: Request the ISY Query the connected devices.
     + `isy994.set_variable`: Set an ISY variable's current or initial value. Variables can be set by either type/address or by name.
     + `isy994.send_program_command`: Send a command to control an ISY program or folder. Valid commands are run, run_then, run_else, stop, enable, disable, enable_run_at_startup, and disable_run_at_startup.
     + `isy994.run_network_resource`: Run a network resource on the ISY.

#### Fixed:

- Fix #51 - Temperatures are not converted if ISY thermostat and HASS are different units
- Fix #54 - Z-Wave Sensor showing UOM as integer next to actual state.

### [1.3.7] - Bug Fixes and Core Catchup to 0.109.0

- Fix #50 for ISYv4 Firmware UOMs in Climate Module
- Add Insteon Dual Band SwitchLinc model 2477S to ISY994 (home-assistant/core#32813)
- Rename `.transitions` folder to `transitions` per Core changes to fix #52
- Add node_def_id for ISY994i wrapped X10 modules (home-assistant/core#31815)
- Enable pylint unnecessary-pass (home-assistant/core#33650)
- Remove unused manifest fields (home-assistant/core#33595)
- Add and use time related constants (home-assistant/core#32065)
- Add and use more unit constants (home-assistant/core#32122)
- Add and use percentage constant (home-assistant/core#32094)
- Add and use UNIT_VOLT constant (home-assistant/core#33994)
- Use LENGTH_KILOMETERS constant (home-assistant/core#33976)
- Use POWER_WATT constant (home-assistant/core#33984)
- Add and use UNIT_DEGREE constant (home-assistant/core#33978)
- Use MASS_KILOGRAMS constant (home-assistant/core#34052)
- Use LENGTH_METERS constant (home-assistant/core#34110)
- Add and use frequency constants (home-assistant/core#34113)
- Drop UNIT_ prefix for constants (home-assistant/core#34164)

### [1.3.6] - Correct State Attributes for Binary Sensor Programs

- Exclude "actions" program state attributes for binary sensor programs
- Update other Program-based entities to show device state attributes for both the status and actions program, in-case the status program is updated by something other than Home Assistant.
- Finalize new unique_ids in prep for HA Core PR.

### [1.3.5] - Improvements to multiple ISY Connections

- Should fix #43 and improve connections to multiple ISYs (multiple Config Entries).
- Provide initial state for tamper nodes that do not have a valid state after ISY Restart.

### [1.3.4] - Minor Bug Fixes, Bump PyISY-Beta to RC3

- Fix #41 - Appending Device Model when NodeDefId doesn't exist.
- Fix #42 - ExpatError not handled for XML Parser getting bad data.
- Better management of imported configurations with the stored config entry. Thanks @bdraco for pointing out a duplication issue.

### [1.3.3] - Various Bug Fixes

- Fix #40 - Unknown variable states
- Fix #39 - Fan Speed Attribute type error
- Fix #37 - Unable to add new variables when config is imported from YAML to Config Entry.
- Bump PyISY-Beta to RC2

### [1.3.2] - Bump PyISY-Beta to RC1

- This release replaces V1.3.1; no other changes other than a renumbering of PyISY-Beta dev174 to rc1

### [1.3.1] - [BREAKING] Remove Support for Climate Module

- **BREAKING CHANGE**: Update to PyISY-beta to remove support for the ISY Climate Module which has been retired by UDI as of 3/30/2020.
    + You will need to remove `enable_climate` from your configuration.

### [1.2.2] - Support ISY Portal Paths in Connections

- You can now connect to an ISY via the ISY Portal Cloud account. For the url, log-in to your [ISY Portal](https://my.isy.io/) account, choose the ISY you want to connect to, and under Tools > Information > ISY Information, copy the `URL to ISY` address. Use this in your configuration for this module.

### [1.2.1] - Fix Bad Fan Mode Command and Missing Tamper Devices

- Fixes #30 - Motion sensor devices are missing in latest update
- Fixes #33 - Error setting Fan Mode on Climate Devices.

### [1.2.0] - Add a config flow and device registry entries.

- Implement config flow
- Device registry data is now provided
- Fix I/O in the event loop causing slow startup
- Migrate unique_ids to be specific to the ISY Controller to avoid conflicts with multiple ISYs.
- Update to PyISY-beta==2.0.0.dev141

### [1.1.2] - Mop-up Changes from Home Assistant Core

- Pick up changes from home-assistant/home-assistant#30360
- Pick up changes from home-assistant/home-assistant#28864
- Bugfix for shbatm/hacs-isy994#22 - Malformed Formatted Values from ISY

### [1.1.1] - Bugfix for #12

### [1.1.0] - Changes to Conform to PyISY-beta changes

- Use more constants from underlying package instead of redefining.
- Update function names to match new changes in PyISY-beta
- PyISY-beta has been updated to track changes merged into the PyISY V2 branch.

### [1.0.15] - Bump PyISY-beta to 2.0.0.dev90 to fix #11

- PyISY-beta==2.0.0.dev89 fixes the unhandled errors thrown by not having any Variables defined.

### [1.0.13] - Rollup Source Changes, PyISY_Beta Function Name Changes

- Include changes from home-assistant/home-assistant#30500 (52164773) for Home Assistant spelling consistency
- Include changes from home-assistant/home-assistant#30532 (345cc244) for name corrections in manifests
- Accommodate changes in PyISY Beta function renaming
- Add ISY Address and new protocol property as entity attributes
- Fix issue where leak sensor "WET" nodes were being added as switches.

### [1.0.12] - Fix for #8

- Make sure brightness is returned as an integer

### [1.0.11] - Jan 2020 Update

- Moved recording of extra attributes in the event stream from the Home Assistant integration into the PyISY module.
- Fixed erroneous errors when updating statuses for Thermostats.
- Added "group all on" attribute to scenes/groups to show if all of the devices in the group are on, or just some of them.
- Fixed "hint" assuming a device would turn on to full brightness - now instead of jumping to full brightness and back to the correct level if a local On Level is set, it will jump to the On Level.
- Fixed Brightness=255 from assuming device would turn on to full brightness, did not account for local On Levels. Now will actually send Brightness=255 if it is passed.

### [pre-1.0.10] Differences from Home Assistant Core ISY994 Integration

- Move constants to a dedicated `const.py` file.
- Add support for Climate devices per `climate-1.0` changes.
- Expand ISY Z-Wave support by properly classifying devices using the `devtype.cat` attribute.
- Fixes issues with `device_state_attributes` throwing Type errors and getting overwritten on updates from the ISY--now maintains a updatable dict and adds attributes when provided from the ISY EventStream (ISY doesn't always provide all attributes on the initial query).
- Fixes ISY Heartbeats per #21996
- Update ISYBinarySensorHeartbeat to report state on startup if available.
- Revised comments to better clarify the behaviors of the heartbeat node in Home Assistant since it does not report the actual state of the ISY's sub-node (which could be on or off).
- Add logic for Motion Sensor subnodes, update framework for Z-Wave IDs.
- Allow ISY Variables to be used as sensors, binary_sensors, and switches.
- The `isy994_control` event has been updated to also expose `value`.  This is expected to be a non-breaking change in PyISY; (PyISY's `event` is now a `dict` instead of a `string`, but will represent itself the same as the command string it used to pass).  This change is vital to the `climate` integration, as some values are only made available from the event stream, not the node definition.