## CHANGELOG - HACS Version of ISY994 Component

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