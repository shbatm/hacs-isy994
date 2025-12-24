Devcontainer: running tests for the ISY994 custom component

This devcontainer is configured to let maintainers run the integration's tests against Home Assistant's pytest fixtures, and develop alongside PyISYoX.

Quick steps after opening the repository in the Dev Container:

1. The container build will run the setup script automatically (via `postCreateCommand`).
   - The script creates a virtualenv at `/opt/venv` and installs a pre-release of `homeassistant` from PyPI (including testing extras when available).
   - If PyISYoX is available at `../pyisyox`, it will be installed in editable mode automatically.

2. Open a terminal in the container and activate the venv:

```bash
cd /workspaces/hacs-isy994
source /opt/venv/bin/activate
```

3. Run the tests for this integration:

```bash
pytest tests/
```

Co-Development with PyISYoX
----------------------------

This devcontainer automatically mounts the PyISYoX directory (if available) at `/workspaces/pyisyox` and installs it in editable mode during setup.

**Directory structure required:**
```
parent/
├── hacs-isy994/
└── pyisyox/
```

When both repositories are present:
- PyISYoX is installed with `pip install -e /workspaces/pyisyox`
- Changes to PyISYoX are immediately reflected in the integration
- You can edit both codebases simultaneously

If PyISYoX is not available, the setup script falls back to installing the version specified in `manifest.json`.

Notes and troubleshooting
--------------------------
- If the container build fails due to missing system dependencies while building wheels (cryptography, etc.), rebuild the container after adding the required package to `.devcontainer/Dockerfile` (for example `libssl-dev` and `cargo` are already included).
- To pin a specific Home Assistant version, edit `.devcontainer/scripts/setup_ha_test_env.sh` and replace the `pip install --pre "homeassistant[tests]"` line with a pinned version, for example:

```bash
python -m pip install --pre 'homeassistant==2025.1.0[tests]'
```

VS Code Tasks
--------------

The workspace includes VS Code tasks in `.vscode/tasks.json`:

- **Start Home Assistant (devcontainer)**: runs Home Assistant using the venv at `/opt/venv`
   - Runs Home Assistant with the workspace mounted as the config directory
   - Starts HA bound to port 9123 (inside the container), mapped to host port 9123
   - Uses the `.homeassistant` directory in the workspace as the config directory
   - The setup script creates a symlink `.homeassistant/custom_components` → `../custom_components`

- **Stop Home Assistant (kill)**: convenience task that stops any running Home Assistant process

- **Start Home Assistant (with project venv)**: activates the venv before launching Home Assistant

Usage (inside the devcontainer):

1. Open the Command Palette (Ctrl+Shift+P) and run "Tasks: Run Task" → one of the Start tasks.
2. The Home Assistant process will run in the Terminal panel in the foreground (shows HA logs).
3. To stop it, press Ctrl+C in the task terminal or run the "Stop Home Assistant (kill)" task.

Access Home Assistant:
- From the host machine: http://localhost:9123
- The devcontainer maps container port 8123 to host port 9123

The `.homeassistant/` directory is added to `.gitignore` so runtime state/config doesn't get committed.
