# CHANGELOG - HACS Version of ISY994 Component

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
