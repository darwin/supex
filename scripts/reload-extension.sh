#!/bin/bash
# Reload SketchUp extension from command line
# Usage: ./scripts/reload-extension.sh
#
# This is a simple wrapper around the Python reload script for convenience.

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/../src/driver/scripts/reload_extension.py"

# Call the Python script with any arguments passed to this script
exec "$PYTHON_SCRIPT" "$@"
