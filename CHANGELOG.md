## CHANGELOG - HACS Version of ISY994 Component

### [1.2.0] - Add a config flow and device registry entries.

- Implement config flow
- Device registry data is now provided
- Fix I/O in the event loop causing slow startup
- Update to PyISY-beta==2.0.0.dev136

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

