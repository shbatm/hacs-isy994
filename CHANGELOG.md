## CHANGELOG - HACS Version of ISY994 Component

### [1.0.11] - Jan 2020 Update

- Moved recording of extra attributes in the event stream from the Home Assistant integration into the PyISY module.
- Fixed erroneous errors when updating statuses for Thermostats.
- Added "group all on" attribute to scenes/groups to show if all of the devices in the group are on, or just some of them.
- Fixed "hint" assuming a device would turn on to full brightness - now instead of jumping to full brightness and back to the correct level if a local On Level is set, it will jump to the On Level.
- Fixed Brightness=255 from assuming device would turn on to full brightness, did not account for local On Levels. Now will actually send Brightness=255 if it is passed.

