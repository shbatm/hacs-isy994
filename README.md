[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
<a href="https://www.buymeacoffee.com/shbatm" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-blue.png" alt="Buy Me A Coffee" width="140px" height="30px" ></a>

> :warning: **This integration is for beta testing new features for the ISY994 integration**: Home Assistant Core has been updated to include all features that were added in this component's version 1.x.x. Once you have upgraded to Home Assistant >0.110.0, you may safely remove this integration if you do not wish to beta test the new software.

## Description

This Custom Component is to update the Home Assistant Core [ISY994 component](https://www.home-assistant.io/integrations/isy994/) with new functionality that is currently being tested before migrating to the main integration.

Version 3.x.x uses the beta version of PyISY, in which the communications with the ISY have been completely rewritten to use asynchronous IO methods; ideally making the ISY controls much more responsive when controlling from Home Assistant.

### Differences between this version and Home Assistant Core

See the [CHANGELOG](CHANGELOG.md) for the specific differences and improvements in this version over the Home Assistant Core Integration.

### Looking to Help Make This Integration Better?

The long-term goal is that these will be integrated into Home Assistant. Testing and feedback is encouraged to flush out any bugs now before a merge.

Please report any [issues or feature requests](https://github.com/shbatm/hacs-isy994/issues).

## Installation

This repo is meant to be installed with [HACS](https://custom-components.github.io/hacs/)

Refer to the built-in component's [integration page](https://www.home-assistant.io/integrations/isy994/) for more details on configuration.
