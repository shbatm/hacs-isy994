#!/usr/bin/env bash
set -euo pipefail

# Create .homeassistant runtime directory and symlink custom_components for development
# Idempotent: will not overwrite an existing .homeassistant directory

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUNTIME_DIR="$REPO_ROOT/.homeassistant"
DEV_CONFIG="$REPO_ROOT/.devcontainer/configuration.yaml"

echo "[setup_homeassistant_runtime] repo_root=$REPO_ROOT"

if [ -d "$RUNTIME_DIR" ] && [ -f "$RUNTIME_DIR/configuration.yaml" ]; then
  echo "[setup_homeassistant_runtime] $RUNTIME_DIR already exists with configuration.yaml — leaving as-is"
  exit 0
fi

mkdir -p "$RUNTIME_DIR"

if [ -f "$DEV_CONFIG" ]; then
  if [ ! -f "$RUNTIME_DIR/configuration.yaml" ]; then
    cp "$DEV_CONFIG" "$RUNTIME_DIR/configuration.yaml"
    echo "[setup_homeassistant_runtime] copied default configuration to $RUNTIME_DIR/configuration.yaml"
  else
    echo "[setup_homeassistant_runtime] configuration.yaml already exists in $RUNTIME_DIR — skipping copy"
  fi
else
  echo "[setup_homeassistant_runtime] warning: $DEV_CONFIG not found — no default configuration copied"
fi

# Create symlink for custom_components if it doesn't already exist
if [ -L "$RUNTIME_DIR/custom_components" ] || [ -d "$RUNTIME_DIR/custom_components" ]; then
  echo "[setup_homeassistant_runtime] custom_components already present in $RUNTIME_DIR — skipping symlink"
else
  ln -s ../custom_components "$RUNTIME_DIR/custom_components"
  echo "[setup_homeassistant_runtime] created symlink $RUNTIME_DIR/custom_components -> ../custom_components"
fi

echo "[setup_homeassistant_runtime] done"
