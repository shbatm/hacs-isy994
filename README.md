[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

<a href="https://www.buymeacoffee.com/shbatm" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-blue.png" alt="Buy Me A Coffee" width="140px" height="30px" ></a>

> :warning: **This integration is for beta testing new features for the ISY994 integration**

## Description

This Custom Component is to update the Home Assistant Core [ISY994 component](https://www.home-assistant.io/integrations/isy994/) with new functionality that is currently being tested before migrating to the main integration.

Version 4.x.x uses the beta version of PyISY, in which the communications with the ISY have been completely rewritten (again); ideally making the ISY controls much more responsive when controlling from Home Assistant.

### Differences between this version and Home Assistant Core

See the [CHANGELOG](CHANGELOG.md) for the specific differences and improvements in this version over the Home Assistant Core Integration.

### Looking to Help Make This Integration Better?

The long-term goal is that these will be integrated into Home Assistant. Testing and feedback is encouraged to flush out any bugs now before a merge.

Please report any [issues or feature requests](https://github.com/shbatm/hacs-isy994/issues).

#### Local Development

A [VSCode DevContainer](https://code.visualstudio.com/docs/remote/containers#_getting-started) is also available to provide a consistent development environment.

Assuming you have the pre-requisites installed from the link above (VSCode, Docker, & Remote-Containers Extension), to get started:

1. Fork the repository.
2. Clone the repository to your computer.
3. Open the repository using Visual Studio code.
4. PyISY Co-Development:
    - If you are simulatenously making changes to PyISY, this container will mount your local PyISY folder inside this devcontainer. Assuming you have `./hacs-isy994` and `./PyISY` at the same root folder on your computer, they will be mounted at `/workspaces/hacs-isy994` and `/workspaces/PyISY` in the container. Install your local `pyisy` instance with `pip3 install -e /workspaces/PyISY`.
    - If you are not making changes to PyISY or do not have the structure above, remove the `"mounts"` section from `.devcontainer/devcontainer.json`.
4. When you open this repository with Visual Studio code you are asked to "Reopen in Container", this will start the build of the container.
   - If you don't see this notification, open the command palette and select Remote-Containers: Reopen Folder in Container.

## Installation

This repo is meant to be installed with [HACS](https://custom-components.github.io/hacs/)

Refer to the built-in component's [integration page](https://www.home-assistant.io/integrations/isy994/) for more details on configuration.
