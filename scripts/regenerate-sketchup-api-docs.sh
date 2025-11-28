#!/usr/bin/env bash
# Wrapper script for SketchUp API documentation generation
# Handles submodule initialization/update before running the generator

set -euo pipefail

# Determine script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SUBMODULE_PATH="docgen/sketchup-api-stubs"
GENERATOR_SCRIPT="docgen/scripts/generate_docs.sh"

# Source common utilities (colors, logging, confirm)
source "$SCRIPT_DIR/helpers/common.sh"

cd "$ROOT"

# Check submodule status
# Output format: " <sha> path" or "-<sha> path" (- means not initialized) or "+<sha> path" (+ means modified)
SUBMODULE_STATUS=$(git submodule status "$SUBMODULE_PATH" 2>/dev/null || echo "error")

if [[ "$SUBMODULE_STATUS" == "error" ]]; then
    log_error "Failed to check submodule status"
    exit 1
fi

# First character indicates status
STATUS_CHAR="${SUBMODULE_STATUS:0:1}"

if [[ "$STATUS_CHAR" == "-" ]]; then
    # Submodule not initialized
    log_warn "Submodule '$SUBMODULE_PATH' is not initialized."
    echo ""

    if confirm "Initialize submodule now?" "y"; then
        log_info "Initializing submodule..."
        git submodule update --init "$SUBMODULE_PATH"
        log_success "Submodule initialized."
    else
        log_info "Skipping submodule initialization. Exiting."
        exit 0
    fi
else
    # Submodule is initialized - offer to update
    log_info "Submodule '$SUBMODULE_PATH' is initialized."

    if [[ "$STATUS_CHAR" == "+" ]]; then
        log_warn "Submodule has local changes or is at a different commit."
    fi

    echo ""
    if confirm "Update submodule to latest remote version?" "n"; then
        log_info "Updating submodule to latest..."
        git submodule update --remote "$SUBMODULE_PATH"
        log_success "Submodule updated."
    else
        log_info "Keeping current submodule version."
    fi
fi

echo ""
log_info "Running documentation generator..."
echo ""

# Run the actual generator
exec "$ROOT/$GENERATOR_SCRIPT"
