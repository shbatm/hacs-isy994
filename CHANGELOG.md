## CHANGELOG - HACS Version of ISY994 Component

### [1.1.0-beta1] - Add support for multiple controllers

### [1.1.0] - Changes to Conform to PyISY-beta changes

- Use more constants from underlying package instead of redefining.
- Update function names to match new changes in PyISY-beta
- PyISY-beta has been updated to track changes merged into the PyISY V2 branch.

### [1.0.15] - Bump PyISY-beta to 2.0.0.dev90 to fix #11

- PyISY-beta==2.0.0.dev89 fixes the unhandled errors thrown by not having any Variables defined.

### [1.0.13] - Rollup Source Changes, PyISY_Beta Function Name Changes

- This update add support for multiple ISY994 controllers. Simply update your config to include a list element for each controller:
```yaml
isy994:
  - host: http://my_first_isy_ip:80
    username: !secret isy1_username
    password: !secret isy1_password
    ignore_string: "[i]"
    sensor_string: "[s]"
  - host: http://my_second_isy_ip:80
    username: !secret isy2_username
    password: !secret isy2_password
    ignore_string: "[i]"
    sensor_string: "[s]"
```

#### BREAKING CHANGE:

This update prepends the UUID from the ISY controller onto each entity's unique_id. This will create duplicate entities the first time it runs. It's strongly suggested you remove any ISY994 entities from the Entity Register before restarting Home Assistant (or remove them manually from the `config/.storage/core.entity_registry` and `config/.storage/core.restore_states` while Home Assistant is not running).

### [1.0.14] - Rollup Source Changes, PyISY_Beta Function Name Changes

- Include changes from home-assistant/home-assistant#30500 (52164773) for Home Assistant spelling consistency
- Include changes from home-assistant/home-assistant#30532 (345cc244) for name corrections in manifests
- Accomodate changes in PyISY Beta function renaming
- Add ISY Address and new protocol property as entity attributes
- Fix issue where leak sensor "WET" nodes were being added as switches.

### [1.0.13] - DO NOT USE. Fails on bad PyISY-Beta install.

### [1.0.12] - Fix for #8

- Make sure brightness is returned as an integer

### [1.0.11] - Jan 2020 Update

- Moved recording of extra attributes in the event stream from the Home Assistant integration into the PyISY module.
- Fixed erroneous errors when updating statuses for Thermostats.
- Added "group all on" attribute to scenes/groups to show if all of the devices in the group are on, or just some of them.
- Fixed "hint" assuming a device would turn on to full brightness - now instead of jumping to full brightness and back to the correct level if a local On Level is set, it will jump to the On Level.
- Fixed Brightness=255 from assuming device would turn on to full brightness, did not account for local On Levels. Now will actually send Brightness=255 if it is passed.

