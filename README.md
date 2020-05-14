[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

> :warning: **This integration is marked for retirement**: Once you have upgraded to Home Assistant >0.110.0, you may safely remove this integration. All changes are present in the Home Assistant Core code.

## Description:
This Custom Component is to update the ISY994 component with various bug fixes, better Z-Wave integration, device state attribute support, ISY Variables support, and add Climate support for Insteon and Z-Wave Thermostats that are exposed by the ISY994 Controller hub component.  This will eventually be integrated into Home Assistant after PyISY updates are completed.

As of version 1.4.0, there are now services exposed for more control over your ISY devices! The following services are available:
 - `isy994.send_raw_node_command`: Send a "raw" ISY REST Device Command to a Node using its Home Assistant Entity ID.
 - `isy994.send_node_command`: Send a command to an ISY Device using its Home Assistant entity ID. Valid commands are: beep, brighten, dim, disable, enable, fade_down, fade_stop, fade_up, fast_off, fast_on, and query.
 - `isy994.set_on_level`: Send a ISY set_on_level command to a Node.
 - `isy994.set_ramp_rate`: Send a ISY set_ramp_rate command to a Node.
 - `isy994.system_query`: Request the ISY Query the connected devices.
 - `isy994.set_variable`: Set an ISY variable's current or initial value. Variables can be set by either type/address or by name.
 - `isy994.send_program_command`: Send a command to control an ISY program or folder. Valid commands are run, run_then, run_else, stop, enable, disable, enable_run_at_startup, and disable_run_at_startup.
 - `isy994.run_network_resource`: Run a network resource on the ISY.
 - `isy994.reload`: Reload the ISY994 connection(s) without restarting Home Assistant. Use to pick up new devices that have been added or changed on the ISY.
 - `isy994.cleanup_entities`: Cleanup old entities and devices no longer used by the ISY994 integrations. Useful if you've removed devices from the ISY or changed the options in the configuration to exclude additional items.

### Now Configurable from the Integrations Page!

![](https://raw.githubusercontent.com/shbatm/hacs-isy994/master/.images/integrations.png)

Notes: 

1. Multiple ISYs are supported if added from the Integrations page, just add one entry for each ISY. Make sure you do not have more than one in the `configuration.yaml` page, this will not work.

Thank you to [@bdraco](https://github.com/bdraco) for the help.

### Differences between this version and Home Assistant Core

See the [CHANGELOG](CHANGELOG.md) for the differences and improvements in this version over the Home Assistant Core Integration.  

### Looking to Help Make This Integration Better?

The long-term goal is that these will be integrated into Home Assistant. Testing and feedback is ecouraged to flush out any bugs now before a merge.

Please report any [issues or feature requests](https://github.com/shbatm/hacs-isy994/issues).
If you want to contribute, please review the [Project Plan](https://github.com/shbatm/hacs-isy994/projects/1).

## Installation

This repo is meant to be installed with [HACS](https://custom-components.github.io/hacs/)

## Example entry for `configuration.yaml` (if applicable):
```yaml
isy994:
  host: !secret isy_url
  username: !secret isy_username
  password: !secret isy_password
  sensor_string: "sensor"
  ignore_string: "{IGNORE ME}"
  variable_sensor_string: "HA."
```

Refer to the built-in component's [integration page](https://www.home-assistant.io/integrations/isy994/) for more details.