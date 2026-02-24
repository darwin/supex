#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="supex-test"

# Build the image
echo "Building Docker image..."
docker build -f "$PROJECT_ROOT/devtools/ci/Dockerfile" -t "$IMAGE_NAME" "$PROJECT_ROOT"

# Run tests — pass all arguments through to launch-test.sh
echo "Running tests..."
docker run --rm "$IMAGE_NAME" "$@"
