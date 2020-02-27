## Description:
This Custom Component is to update the ISY994 component with various bug fixes, better Z-Wave integration, device state attribute support, ISY Variables support, and add Climate support for Insteon and Z-Wave Thermostats that are exposed by the ISY994 Controller hub component.  This will eventually be integrated into Home Assistant after PyISY updates are completed.

Change Log:

- Move constants to a dedicated `const.py` file.
- Add support for Climate devices per `climate-1.0` changes.
- Expand ISY Z-Wave support by properly classifying devices using the `devtype.cat` attribute.
- Fixes issues with `device_state_attributes` throwing Type errors and getting overwritten on updates from the ISY--now maintains a updatable dict and adds attributes when provided from the ISY EventStream (ISY doesn't always provide all attributes on the initial query).
- Fixes ISY Heartbeats per #21996
- Update ISYBinarySensorHeartbeat to report state on startup if available.
- Revised comments to better clarify the behaviors of the heartbeat node in Home Assistant since it does not report the actual state of the ISY's sub-node (which could be on or off).
- Add logic for Motion Sensor subnodes, update framework for Z-Wave IDs
- Allow ISY Variables to be used as sensors, binary_sensors, and switches.
- The `isy994_control` event has been updated to also expose `value`.  This is expected to be a non-breaking change in PyISY; (PyISY's `event` is now a `dict` instead of a `string`, but will represent itself the same as the command string it used to pass).  This change is vital to the `climate` integration, as some values are only made available from the event stream, not the node definition.
- Updated Device Domain assignments and improved Z-Wave status functions.
- Added "Group All On" attribute to scenes (groups) to determine if all devices are on in a scene or if only some are.
- Fixed issues with "On Levels" not being used by Home Assistant (jumping to 100% then back to On Level when controlling in Lovelace, 100% brightness only goes to On Level)


## Example entry for `configuration.yaml` (if applicable):
```yaml
isy994:
  host: !secret isy_url
  username: !secret isy_username
  password: !secret isy_password
  isy_variables:
    sensors:
      - id: 23
        type: 2
        unit_of_measurement: '%'
        device_class: 'battery'
    binary_sensors:
      - id: 14
        type: 2
    switches:
      - id: 5
        type: 2
```