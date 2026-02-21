#!/usr/bin/env bash
# Launch vcad Rust sidecar for development
# Builds in release mode if binary not found, then exec's the sidecar.
#
# Usage: scripts/launch-vcad-sidecar.sh [sidecar-args...]

set -e

# Resolve symlinks (macOS-compatible, no readlink -f)
SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_PATH" ]; do
  SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
  SCRIPT_PATH="$(readlink "$SCRIPT_PATH")"
  [[ "$SCRIPT_PATH" != /* ]] && SCRIPT_PATH="$SCRIPT_DIR/$SCRIPT_PATH"
done
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
SIDECAR_DIR="$(cd "$SCRIPT_DIR/../vcad/sidecar" && pwd)"

# Build if needed
if [ ! -f "$SIDECAR_DIR/target/release/supex-vcad-sidecar" ]; then
    echo "Building vcad sidecar..." >&2
    cargo build --release --manifest-path "$SIDECAR_DIR/Cargo.toml"
fi

exec "$SIDECAR_DIR/target/release/supex-vcad-sidecar" "$@"
