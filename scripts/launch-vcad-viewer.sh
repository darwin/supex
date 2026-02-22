#!/usr/bin/env bash
# Launch vcad viewer
#
# Usage: launch-vcad-viewer.sh [--dev]
#
#   (default)  Full Tauri dev mode (native window + Vite)
#   --dev      Browser debug mode — Vite dev server only (localhost:1420)
#              Opens in Chrome for DevTools / Claude Chrome extension debugging

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VIEWER_DIR="$PROJECT_ROOT/vcad/viewer"

source "$SCRIPT_DIR/helpers/common.sh"

main() {
    local browser_mode=false
    for arg in "$@"; do
        case "$arg" in
            --dev) browser_mode=true ;;
            *) log_error "Unknown argument: $arg"; exit 1 ;;
        esac
    done

    if [[ ! -d "$VIEWER_DIR" ]]; then
        log_error "Viewer directory not found: $VIEWER_DIR"
        exit 1
    fi

    if [[ ! -d "$VIEWER_DIR/node_modules" ]]; then
        log_info "Installing npm dependencies..."
        (cd "$VIEWER_DIR" && npm install)
    fi

    if $browser_mode; then
        log_info "Starting vcad viewer (browser debug mode)"
        log_info "======================================================="
        log_info "Vite dev server: http://localhost:1420"
        log_info ""
        log_info "Open Chrome and navigate to http://localhost:1420"
        log_info "  - Chrome DevTools: Cmd+Option+I (F12)"
        log_info "  - Claude Chrome extension works on this page"
        log_info "======================================================="
        log_info "Use Ctrl+C to stop"
        cd "$VIEWER_DIR" && npm run dev
    else
        log_info "Starting vcad viewer (Tauri dev mode)"
        log_info "======================================================="
        log_info "Use Ctrl+C to stop"
        cd "$VIEWER_DIR" && npm run tauri dev
    fi
}

main "$@"
