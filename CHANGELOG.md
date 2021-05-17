# CHANGELOG - HACS Version of ISY994 Component

## [3.0.0] - Migrate to released PyISY V3 (non-beta)

- Migrate back to the upstream PyISY project for testing of PyISY V3 (not PyISY-beta package).
- Remove use of `HomeAssistantType` which was removed in home-assistant/core#49593 (#87)
- Core Catchup to 2021.5.4:
    - None optional hass typing in FlowHandler (home-assistant/core#46462)
    - Implement percentage step sizes for fans (home-assistant/core#46512)
    - Add suggested area support to isy994 (home-assistant/core#46927)
    - Update pylint (home-assistant/core#47205)
    - Fix typing on fan percentage (home-assistant/core#47259)
    - Uniformize platform setup (home-assistant/core#47101)
    - Update integrations f-i to override extra_state_attributes() (home-assistant/core#47757)
    - Update integrations j-o to override extra_state_attributes() (home-assistant/core#47758)
    - Update typing 09 (home-assistant/core#48059)
    - Have pylint warn when user visible log messages do not start with capital letter or end with a period (home-assistant/core#48064)
    - Migrate integrations i-m to extend SensorEntity (home-assistant/core#48213)
    - Rewrite of not a == b occurrences (home-assistant/core#48132)
    - Merge of nested IF-IF cases - H-J (home-assistant/core#48368)
    - Update pylint to 2.7.3 (home-assistant/core#48488)
    - Don't import stdlib typing types from helpers.typing (home-assistant/core#49104)
    - Add support for IoT class in manifest (home-assistant/core#46935)
    - Integrations h* - i*: Rename HomeAssistantType to HomeAssistant. (home-assistant/core#49587)
    - Integrations i* - m*: Rename HomeAssistantType to HomeAssistant. (home-assistant/core#49586)
    - Reduce config entry setup/unload boilerplate G-J (home-assistant/core#49737)
    - Enable mccabe complexity checks in flake8 (home-assistant/core#49616)
    - Add dhcp discovery support to isy994 (home-assistant/core#50488)
    - Ensure isy994 is only discovered once (home-assistant/core#50577)

## [3.0.0.dev19] - Add Suggested Area Support

- Uses the folders on the ISY to suggest the areas for Home Assistant to use for each device.

## [3.0.0.dev18] - Add support for renaming ISY Nodes from Home Assistant services

- Add a `isy994.rename_node` service to update an entities name within the ISY. Note this does not automatically update the name of the entity in Home Assistant. If you call `isy994.reload`, the name will be updated in Home Assistant ONLY IF you have not customized the name previously.

## [3.0.0.dev17] - Add Z-Wave Parameter Support

- Add the following services to allow setting and getting Z-Wave Device parameters via the ISY.
    - `isy994.get_zwave_parameter` - Call the service with the entity ID and parameter number to retrieve. The parameter will be returned as an entity state attribute.
    - `isy994.set_zwave_parameter` - Call the service with the entity ID, parameter number, value, and size in bytes and the ISY will set the parameter.

## [3.0.0dev16] - Bump PyISY, Minor stability updates

- Bump PyISY-beta to 3.0.0dev16.
    - Fixes `group_all_on` reporting incorrectly
    - Removes `hint` and presumptive status updates.
- Fix incorrect service function names for `set_on_level` and `set_ramp_rate`.
- Retry config setup on connection failure (#79)

## [3.0.0dev15-2] - Core Catchup to 2021.2.0

- Update for new fan model (backwards-compatibility) (#78)
- Update isy994 to use new fan entity model (home-assistant/core#45536)
- Separate fan speeds into percentages and presets modes (home-assistant/core#45407)
- Use strings instead of f-strings for constants (home-assistant/core#40619)
- Add Devcontainer for integration development.

## [3.0.0dev15-1] - Bugfix for error while turning on a fan

- Fixes `fan.turn_on` service error due to trying to call the old sync function instead of async.

## [3.0.0dev15] - Variable Precision, V2.1.0 Changes, Core Catch-up to 0.117.4

The following changes from the Core ISY994 Integration have been included:

- Fix dimming for ISY Z-Wave devices using percent instead of 8-bit (home-assistant/core#42915)
- Remove unnecessary instances of dict.keys() (home-assistant/core#42518)
- Improve ISY994 NodeServer sorting and format sensor display values (home-assistant/core#42050)
- Upgrade PyISY to v2.1.0, add support for variable precision (home-assistant/core#42043)
- Use references in isy994 strings.json (home-assistant/core#40990)
- Add and use light lux constant in entire code base (home-assistant/core#40171)
- Add and use length millimeters constant (home-assistant/core#40116)
- Add and use currency cent constant (home-assistant/core#40261)
- Use pressure constants in code base (home-assistant/core#40262)
- Add and use currency constants (home-assistant/core#40113)
- Use AREA_SQUARE_METERS constant in all integrations (home-assistant/core#40107)
- Add and use volume cubic constants (home-assistant/core#40106)

## [3.0.0dev13] - Minor Bugfixes

- Bump to PyISY-Beta 3.0.0dev13

## [3.0.0dev12] - Update to use asynchronous version of PyISY

This update is for testing a new beta branch of PyISY, what will become PyISY Version 3.0.0, in which the communications with the ISY have been completely rewritten to use asynchronous IO methods; ideally making the ISY controls much more responsive when controlling from Home Assistant.

### Parity Changes from HomeAssistant from 0.110.0 through 0.115.0b7

- Fix isy994 send_node_command (#39806)
- Drop UNIT_ prefix for percentage constant (#39383)
- Exception chaining and wrapping improvements (#39320)
- Log lines do not end with a full stop (#37527)
- Use LENGTH_FEET constant (#34053)
- Add Z-Wave Notification Sensor support to ISY994 (#36548)
- Fix error on empty UOM for ISY994 Climate Device (#36454)

## [1.5.0] - Merge with Home Assistant Core 0.110.0

- All code changes have been merged back into Core @ v0.110.0.
