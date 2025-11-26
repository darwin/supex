#!/usr/bin/env bash

# Wrapper script for SketchUp API documentation generation
# Handles submodule initialization/update before running the generator

set -e

# Determine script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SUBMODULE_PATH="docgen/sketchup-api-stubs"
GENERATOR_SCRIPT="docgen/scripts/generate_docs.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

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
    read -p "Initialize submodule now? [Y/n] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log_info "Skipping submodule initialization. Exiting."
        exit 0
    fi

    log_info "Initializing submodule..."
    git submodule update --init "$SUBMODULE_PATH"
    log_success "Submodule initialized."
else
    # Submodule is initialized - offer to update
    log_info "Submodule '$SUBMODULE_PATH' is initialized."

    if [[ "$STATUS_CHAR" == "+" ]]; then
        log_warn "Submodule has local changes or is at a different commit."
    fi

    echo ""
    read -p "Update submodule to latest remote version? [y/N] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
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
