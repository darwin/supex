#!/usr/bin/env bash
# Launch the su-mock headless SketchUp API mock server.
# Usage: scripts/launch-su-mock.sh [--port PORT]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PORT="${SUPEX_MOCK_PORT:-9876}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--port PORT]" >&2
      exit 1
      ;;
  esac
done

exec ruby "$PROJECT_DIR/mock/src/su_mock.rb" --port "$PORT"
