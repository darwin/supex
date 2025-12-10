#!/usr/bin/env bash
# Window position management for SketchUp
# Handles saving and restoring window positions for ALL windows
# Uses v2 JSON format with multiple windows keyed by title

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

# Detect config version
get_config_version() {
    if [[ ! -f "$POSITION_FILE" ]]; then
        echo "none"
        return
    fi

    if jq -e '.version' "$POSITION_FILE" &>/dev/null; then
        jq -r '.version' "$POSITION_FILE"
    else
        echo "1"
    fi
}

# Migrate v1 to v2 format
migrate_v1_to_v2() {
    log_info "Migrating window config from v1 to v2..."

    # Backup v1
    cp "$POSITION_FILE" "$POSITION_FILE.v1.backup"
    log_info "Backed up v1 config to $POSITION_FILE.v1.backup"

    # Read v1 data
    local v1_data
    v1_data=$(cat "$POSITION_FILE")

    # Build v2 format with main window only
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    jq -n \
        --argjson v1 "$v1_data" \
        --arg ts "$timestamp" \
        '{
            version: 2,
            timestamp: $ts,
            windows: {
                main: ($v1 | {
                    titlePattern: " - SketchUp [0-9]{4}$",
                    matchedTitle: "unknown (migrated from v1)",
                    x: .x,
                    y: .y,
                    width: .width,
                    height: .height,
                    isMaximized: .isMaximized
                })
            }
        }' > "$POSITION_FILE"

    log_success "Migration complete (v1 backed up)"
}

# Save current window positions (all windows)
save_position() {
    log_info "Saving SketchUp window positions..."

    # Get all window positions using AppleScript
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
        log_warn "Could not get window positions: $error_msg"
        return 1
    fi

    # Log window count
    local window_count
    window_count=$(echo "$position_json" | jq '.windows | length')
    log_info "Found $window_count window(s)"

    # Log each window
    echo "$position_json" | jq -r '.windows | to_entries[] | "  \(.key): \(.value.width)x\(.value.height) at (\(.value.x),\(.value.y))"' | while read -r line; do
        log_info "$line"
    done

    # Save to file
    echo "$position_json" > "$POSITION_FILE"

    log_success "Window positions saved to $POSITION_FILE"
    return 0
}

# Restore saved window positions (all windows)
restore_position() {
    log_info "Restoring SketchUp window positions..."

    # Check if position file exists
    if [[ ! -f "$POSITION_FILE" ]]; then
        log_warn "No saved position found at $POSITION_FILE"
        return 1
    fi

    # Check version and migrate if needed
    local version
    version=$(get_config_version)
    if [[ "$version" == "1" ]]; then
        migrate_v1_to_v2
    fi

    # Validate JSON file
    if ! jq empty "$POSITION_FILE" 2>/dev/null; then
        log_error "Invalid JSON in $POSITION_FILE"
        return 1
    fi

    # Wait for SketchUp to be ready
    log_info "Waiting for SketchUp window..."
    if ! wait_for_process "SketchUp" 15; then
        log_warn "SketchUp not detected, cannot restore position"
        return 1
    fi

    # Get list of windows from config
    local windows
    windows=$(jq -r '.windows | keys[]' "$POSITION_FILE")

    if [[ -z "$windows" ]]; then
        log_warn "No windows found in config"
        return 1
    fi

    # Wait for windows to be available (retry up to 10 times)
    local max_retries=10
    local retry=0
    local any_success=false

    while [[ $retry -lt $max_retries ]]; do
        sleep 1
        any_success=false

        # Try to restore each window
        while IFS= read -r window_key; do
            local x y width height is_maximized matched_title
            x=$(jq -r ".windows[\"$window_key\"].x // empty" "$POSITION_FILE")
            y=$(jq -r ".windows[\"$window_key\"].y // empty" "$POSITION_FILE")
            width=$(jq -r ".windows[\"$window_key\"].width // empty" "$POSITION_FILE")
            height=$(jq -r ".windows[\"$window_key\"].height // empty" "$POSITION_FILE")
            is_maximized=$(jq -r ".windows[\"$window_key\"].isMaximized // false" "$POSITION_FILE")
            matched_title=$(jq -r ".windows[\"$window_key\"].matchedTitle // \"\"" "$POSITION_FILE")

            # Validate required values
            if [[ -z "$x" || -z "$y" || -z "$width" || -z "$height" ]]; then
                log_warn "Invalid position data for window: $window_key"
                continue
            fi

            # Convert boolean to 0/1 for AppleScript
            local maximized_flag="0"
            if [[ "$is_maximized" == "true" ]]; then
                maximized_flag="1"
            fi

            # Call AppleScript to restore this window
            local result
            result=$(osascript "$SCRIPT_DIR/set-window-position.applescript" \
                "$window_key" "$matched_title" "$x" "$y" "$width" "$height" "$maximized_flag" 2>&1)

            if [[ "$result" == "Restored:"* ]]; then
                log_info "$result"
                any_success=true
            elif [[ "$result" == "Warning:"* ]]; then
                log_warn "$result"
            else
                log_error "$result"
            fi
        done <<< "$windows"

        # If we restored at least one window successfully, we're done
        if [[ "$any_success" == "true" ]]; then
            log_success "Window positions restored successfully"
            return 0
        fi

        retry=$((retry + 1))
        log_info "Waiting for windows... (attempt $retry/$max_retries)"
    done

    log_warn "Could not restore any window positions after $max_retries attempts"
    return 1
}

# Get current positions (for debugging)
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
    migrate)
        version=$(get_config_version)
        if [[ "$version" == "1" ]]; then
            migrate_v1_to_v2
        elif [[ "$version" == "none" ]]; then
            log_info "No config file exists"
        else
            log_info "Already at version $version"
        fi
        ;;
    *)
        echo "Usage: $0 {save|restore|get|migrate}"
        echo "  save    - Save current SketchUp window positions (all windows)"
        echo "  restore - Restore saved window positions"
        echo "  get     - Get current window positions (JSON)"
        echo "  migrate - Manually migrate v1 config to v2"
        exit 1
        ;;
esac
