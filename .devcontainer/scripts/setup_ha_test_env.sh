#!/usr/bin/env bash
set -euo pipefail

# Minimal devcontainer setup script — assumes the image provides a working, writable venv at /opt/venv
VENV="/opt/venv"
WORKSPACE_DIR="/workspaces/hacs-isy994"
PYISYOX_DIR="/workspaces/pyisyox"
WHEEL_DIR="${WORKSPACE_DIR}/.wheels"
PIP_CACHE_DIR="${WORKSPACE_DIR}/.cache/pip"

if [ ! -x "${VENV}/bin/python" ]; then
    echo "Error: expected venv at ${VENV} but python not found. Ensure the image provides /opt/venv"
    exit 1
fi

echo "Using venv: ${VENV}"
echo "Using wheel cache: ${WHEEL_DIR}"
mkdir -p "${WHEEL_DIR}" "${PIP_CACHE_DIR}"

VENV_PYTHON="${VENV}/bin/python"

echo "Updating pip, setuptools, and wheel..."
${VENV_PYTHON} -m pip install -U pip "setuptools>=70.0" wheel

echo "Building/pulling wheelhouse for Home Assistant (may take a while first run)..."
set +e
${VENV_PYTHON} -m pip wheel --wheel-dir "${WHEEL_DIR}" --pre "homeassistant[tests]" || true
set -e

if [ -n "$(ls -A "${WHEEL_DIR}" 2>/dev/null)" ]; then
    echo "Installing Home Assistant from wheelhouse..."
    ${VENV_PYTHON} -m pip install --no-index --find-links "${WHEEL_DIR}" --pre "homeassistant[tests]"
else
    echo "Installing Home Assistant from PyPI (this may compile wheels)..."
    ${VENV_PYTHON} -m pip install --pre --prefer-binary "homeassistant[tests]"
fi

# Install PyISYoX from local workspace if available
if [ -d "${PYISYOX_DIR}" ] && [ -f "${PYISYOX_DIR}/pyproject.toml" ]; then
    echo "Installing PyISYoX from local workspace in editable mode..."
    ${VENV_PYTHON} -m pip install -e "${PYISYOX_DIR}"
else
    echo "PyISYoX directory not found at ${PYISYOX_DIR}, will use version from requirements"
fi

echo "Installing integration requirements from manifest..."
if command -v jq >/dev/null 2>&1; then
    for req in $(jq -c -r '.requirements | .[]' "${WORKSPACE_DIR}/custom_components/isy994/manifest.json"); do
        # Skip pyisyox if we already installed it from local workspace
        if [ -d "${PYISYOX_DIR}" ] && [[ "$req" == pyisyox* ]]; then
            echo "Skipping $req (already installed from local workspace)"
            continue
        fi
        ${VENV_PYTHON} -m pip install "$req"
    done
fi

echo "Ensuring pytest and Home Assistant test dependencies..."
${VENV_PYTHON} -m pip install -U pytest pytest-asyncio pytest-homeassistant-custom-component

echo "Setup complete."
echo "To activate the venv in terminal, run: source ${VENV}/bin/activate"
echo "Or configure Python path in VS Code to: ${VENV}/bin/python"
