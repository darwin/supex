#!/usr/bin/env bash

# Window position management for SketchUp
# Handles saving and restoring window positions

set -e

# Script directory and paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POSITION_FILE="$HOME/.supex/window-position.json"
POSITION_DIR="$(dirname "$POSITION_FILE")"

# Ensure directory exists
mkdir -p "$POSITION_DIR"

# Function to save current window position
save_position() {
    echo "Saving SketchUp window position..."
    
    # Get current position using AppleScript
    position_json=$(osascript "$SCRIPT_DIR/get-window-position.applescript" 2>/dev/null)
    
    # Check if we got valid JSON (not an error)
    if [[ "$position_json" == *"error"* ]]; then
        echo "Warning: Could not get window position: $position_json"
        return 1
    fi
    
    # Add timestamp to JSON
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    position_with_timestamp=$(echo "$position_json" | sed 's/}$/,"timestamp":"'$timestamp'"}/')
    
    # Save to file
    echo "$position_with_timestamp" > "$POSITION_FILE"
    echo "Window position saved to $POSITION_FILE"
    
    return 0
}

# Function to restore window position
restore_position() {
    echo "Restoring SketchUp window position..."
    
    # Check if position file exists
    if [ ! -f "$POSITION_FILE" ]; then
        echo "No saved position found at $POSITION_FILE"
        return 1
    fi
    
    # Read position from file
    position_json=$(cat "$POSITION_FILE")
    
    # Extract values using grep and sed (macOS compatible)
    x=$(echo "$position_json" | grep -o '"x":[0-9]*' | sed 's/"x"://')
    y=$(echo "$position_json" | grep -o '"y":[0-9]*' | sed 's/"y"://')
    width=$(echo "$position_json" | grep -o '"width":[0-9]*' | sed 's/"width"://')
    height=$(echo "$position_json" | grep -o '"height":[0-9]*' | sed 's/"height"://')
    maximized=$(echo "$position_json" | grep -o '"maximized":[a-z]*' | sed 's/"maximized"://')
    
    # Validate we got all required values
    if [ -z "$x" ] || [ -z "$y" ] || [ -z "$width" ] || [ -z "$height" ]; then
        echo "Error: Invalid position data in $POSITION_FILE"
        return 1
    fi
    
    # Convert boolean to 0/1 for AppleScript
    if [ "$maximized" = "true" ]; then
        maximized_flag="1"
    else
        maximized_flag="0"
    fi
    
    # Wait for SketchUp to be ready (up to 10 seconds)
    echo "Waiting for SketchUp window..."
    for i in {1..20}; do
        if osascript -e 'tell application "System Events" to exists process "SketchUp"' 2>/dev/null; then
            # Additional delay to ensure window is fully initialized
            sleep 1
            break
        fi
        sleep 0.5
    done
    
    # Apply the saved position
    result=$(osascript "$SCRIPT_DIR/set-window-position.applescript" "$x" "$y" "$width" "$height" "$maximized_flag" 2>&1)
    
    if [[ "$result" == *"Error"* ]]; then
        echo "Warning: Could not restore window position: $result"
        return 1
    else
        echo "Window position restored successfully"
        return 0
    fi
}

# Function to get current position (for debugging)
get_position() {
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