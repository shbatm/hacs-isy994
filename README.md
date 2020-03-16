## Description:
This Custom Component is to update the ISY994 component with various bug fixes, better Z-Wave integration, device state attribute support, ISY Variables support, and add Climate support for Insteon and Z-Wave Thermostats that are exposed by the ISY994 Controller hub component.  This will eventually be integrated into Home Assistant after PyISY updates are completed.

### Now Configurable from the Integrations Page!

![](.images/integrations.png)

Thank you to [@bdraco](https://github.com/bdraco) for the help.

### Differences between this version and Home Assistant Core

See the [CHANGELOG](CHANGELOG.md) for the differences and improvements in this version over the Home Assistant Core Integration.  

### Looking to Help Make This Integration Better?

The long-term goal is that these will be integrated into Home Assistant. Testing and feedback is ecouraged to flush out any bugs now before a merge.

Please report any [issues or feature requests](https://github.com/shbatm/hacs-isy994/issues.
If you want to contribute, please review the [Project Plan](https://github.com/shbatm/hacs-isy994/projects/1).

## Installation

This repo is meant to be installed with [HACS](https://custom-components.github.io/hacs/)

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