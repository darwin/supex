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

    # Extract values for logging
    local x y width height is_maximized
    x=$(echo "$position_json" | jq -r '.x')
    y=$(echo "$position_json" | jq -r '.y')
    width=$(echo "$position_json" | jq -r '.width')
    height=$(echo "$position_json" | jq -r '.height')
    is_maximized=$(echo "$position_json" | jq -r '.isMaximized')

    log_info "Position: x=$x, y=$y, width=$width, height=$height, maximized=$is_maximized"

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

    log_info "Position: x=$x, y=$y, width=$width, height=$height, maximized=$is_maximized"

    # Wait for SketchUp to be ready
    log_info "Waiting for SketchUp window..."
    if ! wait_for_process "SketchUp" 15; then
        log_warn "SketchUp not detected, cannot restore position"
        return 1
    fi

    # Wait for window to be available (retry up to 10 times)
    local max_retries=10
    local retry=0
    local result=""
    while [[ $retry -lt $max_retries ]]; do
        sleep 1
        result=$(osascript "$SCRIPT_DIR/set-window-position.applescript" "$x" "$y" "$width" "$height" "$maximized_flag" 2>&1)
        if [[ "$result" != *"Error"* ]]; then
            log_success "Window position restored successfully"
            return 0
        fi
        retry=$((retry + 1))
        log_info "Waiting for window... (attempt $retry/$max_retries)"
    done

    log_warn "Could not restore window position: $result"
    return 1
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
