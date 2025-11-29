#!/usr/bin/env bash

# SketchUp Launcher Script for Supex Runtime Development
# Deploys extension sources directly to SketchUp, then launches SketchUp

set -e -o pipefail

# Helper functions for silent pushd/popd
pushd() {
  command pushd "$@" >/dev/null
}

popd() {
  command popd >/dev/null
}

# Determine script directory and project root
pushd .
cd "$(dirname "${BASH_SOURCE[0]}")"
SCRIPTS=$(pwd)
ROOT="$(cd .. && pwd)"
EXTENSION_DIR="$ROOT/src/runtime"
popd

# Configuration
APP_NAME="SketchUp"
LOG_DIR="$ROOT/.tmp"
SKETCHUP_OUT_FILE="$LOG_DIR/sketchup_out.txt"
SKETCHUP_ERR_FILE="$LOG_DIR/sketchup_err.txt"
CONSOLE_LOG_FILE="$LOG_DIR/sketchup_console.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Create log directories
create_log_dirs() {
    for dir in "$LOG_DIR"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
        fi
    done

    # Clean old log files
    [[ -e "$SKETCHUP_OUT_FILE" ]] && rm "$SKETCHUP_OUT_FILE" || true
    [[ -e "$SKETCHUP_ERR_FILE" ]] && rm "$SKETCHUP_ERR_FILE" || true
    [[ -e "$CONSOLE_LOG_FILE" ]] && rm "$CONSOLE_LOG_FILE" || true
}

# Signal handler for graceful shutdown
sigterm_handler() {
    log_warn "Shutdown signal received"
    log_info "Shutting down SketchUp gracefully..."
    osascript "$SCRIPTS/helpers/shutdown-sketchup.applescript"
    exit 1
}

# Set up signal traps
trap 'trap " " SIGINT SIGTERM SIGHUP; kill 0; wait; sigterm_handler' SIGINT SIGTERM SIGHUP



# Clean up any old deployments and validate extension sources
prepare_extension() {
    log_info "Preparing extension for injection..."

    # Check if injector script exists
    local injector_script="$EXTENSION_DIR/injector.rb"
    if [[ ! -f "$injector_script" ]]; then
        log_error "Injector script not found: $injector_script"
        exit 1
    fi

    # Check if main extension file exists
    local main_extension="$EXTENSION_DIR/supex_runtime.rb"
    if [[ ! -f "$main_extension" ]]; then
        log_error "Main extension file not found: $main_extension"
        exit 1
    fi

    # Check if source directory exists
    local source_dir="$EXTENSION_DIR/supex_runtime"
    if [[ ! -d "$source_dir" ]]; then
        log_error "Extension source directory not found: $source_dir"
        exit 1
    fi

    log_success "Extension prepared for injection"
    log_info "Extension will be loaded from: $EXTENSION_DIR"
}

# Launch SketchUp
launch_sketchup() {
    log_info "Launching SketchUp with Ruby injector..."

    # Path to our injector script
    local injector_script="$EXTENSION_DIR/injector.rb"

    # Prepare launch arguments
    local args=()
    args+=(--stdout "$SKETCHUP_OUT_FILE")
    args+=(--stderr "$SKETCHUP_ERR_FILE")
    args+=(-a "$APP_NAME")
    args+=(--args)
    args+=(-RubyStartup "$injector_script")

    # Start monitoring error output
    touch "$SKETCHUP_ERR_FILE"
    tail -f "$SKETCHUP_ERR_FILE" | sed -u $'s/^/\033[0;31m[ERROR] /' | sed -u $'s/$/\033[0m/' &
    TAIL_STDERR_PID=$!

    # Start monitoring console log output with yellow coloring
    touch "$CONSOLE_LOG_FILE"
    tail -f "$CONSOLE_LOG_FILE" | sed -u $'s/^/\033[1;33m[CONSOLE] /' | sed -u $'s/$/\033[0m/' &
    TAIL_CONSOLE_PID=$!

    # Launch SketchUp in background
    log_success "SketchUp is starting with injected extension..."
    log_info "Extension loaded directly from source directory via -RubyStartup"
    log_info "Use 'Extensions > Supex Runtime > Reload Extension' to pick up code changes"
    log_info "Or call 'reload_extension' tool via MCP"
    log_info "Set SUPEX_VERBOSE=1 for detailed loading information"
    log_info "Console output appears in ${YELLOW}yellow${NC} with [CONSOLE] prefix"

    # Launch SketchUp without -W flag first to allow window positioning
    open "${args[@]}"

    # Give SketchUp time to start up
    sleep 2

    # Restore window position after launch
    log_info "Restoring window position..."
    "$SCRIPTS/helpers/manage-window-position.sh" restore || log_warn "Could not restore window position"

    log_info "Use Ctrl+C to stop monitoring and shutdown SketchUp"

    # Now wait for SketchUp to exit using a loop
    while pgrep -x "SketchUp" > /dev/null; do
        sleep 1
    done

    # Clean up tail processes
    kill $TAIL_STDERR_PID 2>/dev/null || true
    [[ -n "$TAIL_CONSOLE_PID" ]] && kill $TAIL_CONSOLE_PID 2>/dev/null || true
}

# Main execution
main() {
    log_info "Starting SketchUp launcher for Supex development"
    log_info "======================================================="

    create_log_dirs
    prepare_extension
    launch_sketchup

    log_success "SketchUp session completed"
}

# Run main function
main "$@"
