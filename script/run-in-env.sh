#!/usr/bin/env bash
set -euo pipefail

# Wrapper to run tools inside a project virtualenv if available.
# Usage: script/run-in-env.sh <command> [args...]

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
  exec "$@"
fi

if [ -x "/opt/venv/bin/$1" ]; then
  exec "/opt/venv/bin/$1" "${@:2}"
fi

exec "$@"
