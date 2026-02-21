#!/usr/bin/env bash
# Launch vcad viewer in Tauri dev mode
#
# Usage: launch-vcad-viewer.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VIEWER_DIR="$PROJECT_ROOT/vcad/viewer"

source "$SCRIPT_DIR/helpers/common.sh"

main() {
    log_info "Starting vcad viewer (Tauri dev mode)"
    log_info "======================================================="

    if [[ ! -d "$VIEWER_DIR" ]]; then
        log_error "Viewer directory not found: $VIEWER_DIR"
        exit 1
    fi

    if [[ ! -d "$VIEWER_DIR/node_modules" ]]; then
        log_info "Installing npm dependencies..."
        (cd "$VIEWER_DIR" && npm install)
    fi

    log_info "Launching Tauri dev server..."
    log_info "Use Ctrl+C to stop"

    cd "$VIEWER_DIR" && npm run tauri dev
}

main "$@"
