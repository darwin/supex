#!/usr/bin/env bash
# Window position management for SketchUp
# Handles saving and restoring window positions

set -euo pipefail

# Script directory and source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Ensure jq is available
require_jq

# Paths
POSITION_FILE="$HOME/.supex/window-position.json"
POSITION_DIR="$(dirname "$POSITION_FILE")"

# Ensure directory exists
mkdir -p "$POSITION_DIR"

# Save current window position
save_position() {
    log_info "Saving SketchUp window position..."

    # Get current position using AppleScript
    local position_json
    if ! position_json=$(osascript "$SCRIPT_DIR/get-window-position.applescript" 2>/dev/null); then
        log_error "Failed to run get-window-position.applescript"
        return 1
    fi

    # Validate JSON
    if ! echo "$position_json" | jq empty 2>/dev/null; then
        log_error "Invalid JSON from AppleScript: $position_json"
        return 1
    fi

    # Check for error in response
    if echo "$position_json" | jq -e '.error' &>/dev/null; then
        local error_msg
        error_msg=$(echo "$position_json" | jq -r '.error')
        log_warn "Could not get window position: $error_msg"
        return 1
    fi

    # Add timestamp and save
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "$position_json" | jq --arg ts "$timestamp" '. + {timestamp: $ts}' > "$POSITION_FILE"

    log_success "Window position saved to $POSITION_FILE"
    return 0
}

# Restore saved window position
restore_position() {
    log_info "Restoring SketchUp window position..."

    # Check if position file exists
    if [[ ! -f "$POSITION_FILE" ]]; then
        log_warn "No saved position found at $POSITION_FILE"
        return 1
    fi

    # Validate JSON file
    if ! jq empty "$POSITION_FILE" 2>/dev/null; then
        log_error "Invalid JSON in $POSITION_FILE"
        return 1
    fi

    # Extract values using jq
    local x y width height is_maximized
    x=$(jq -r '.x // empty' "$POSITION_FILE")
    y=$(jq -r '.y // empty' "$POSITION_FILE")
    width=$(jq -r '.width // empty' "$POSITION_FILE")
    height=$(jq -r '.height // empty' "$POSITION_FILE")
    is_maximized=$(jq -r '.isMaximized // false' "$POSITION_FILE")

    # Validate required values
    if [[ -z "$x" || -z "$y" || -z "$width" || -z "$height" ]]; then
        log_error "Invalid position data in $POSITION_FILE (missing x, y, width, or height)"
        return 1
    fi

    # Convert boolean to 0/1 for AppleScript
    local maximized_flag="0"
    if [[ "$is_maximized" == "true" ]]; then
        maximized_flag="1"
    fi

    # Wait for SketchUp to be ready
    log_info "Waiting for SketchUp window..."
    if ! wait_for_process "SketchUp" 15; then
        log_warn "SketchUp not detected, cannot restore position"
        return 1
    fi

    # Additional delay to ensure window is fully initialized
    sleep 1

    # Apply the saved position
    local result
    if result=$(osascript "$SCRIPT_DIR/set-window-position.applescript" "$x" "$y" "$width" "$height" "$maximized_flag" 2>&1); then
        if [[ "$result" == *"Error"* ]]; then
            log_warn "Could not restore window position: $result"
            return 1
        fi
        log_success "Window position restored successfully"
        return 0
    else
        log_warn "Failed to run set-window-position.applescript: $result"
        return 1
    fi
}

# Get current position (for debugging)
get_position() {
    local position_json
    position_json=$(osascript "$SCRIPT_DIR/get-window-position.applescript" 2>/dev/null)
    echo "$position_json"
}

# Main command handling
case "${1:-}" in
    save)
        save_position
        ;;
    restore)
        restore_position
        ;;
    get)
        get_position
        ;;
    *)
        echo "Usage: $0 {save|restore|get}"
        echo "  save    - Save current SketchUp window position"
        echo "  restore - Restore saved window position"
        echo "  get     - Get current window position (JSON)"
        exit 1
        ;;
esac
