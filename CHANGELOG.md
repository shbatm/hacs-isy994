# CHANGELOG - HACS Version of ISY994 Component

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
