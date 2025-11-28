#!/usr/bin/env bash
# Common utilities for supex scripts
# Source this file at the beginning of other scripts

# Prevent double-sourcing
[[ -n "${_SUPEX_COMMON_LOADED:-}" ]] && return
readonly _SUPEX_COMMON_LOADED=1

# =============================================================================
# Colors
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly GRAY='\033[0;90m'
readonly NC='\033[0m'  # No Color

# =============================================================================
# Logging
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_debug() {
    if [[ "${SUPEX_DEBUG:-}" == "1" ]]; then
        echo -e "${GRAY}[DEBUG]${NC} $*" >&2
    fi
}

# =============================================================================
# Dependency Checks
# =============================================================================

require_jq() {
    if ! command -v jq &>/dev/null; then
        log_error "jq is required but not installed."
        log_error "Install with: brew install jq"
        exit 1
    fi
}

require_command() {
    local cmd="$1"
    local install_hint="${2:-}"
    if ! command -v "$cmd" &>/dev/null; then
        log_error "$cmd is required but not installed."
        [[ -n "$install_hint" ]] && log_error "Install with: $install_hint"
        exit 1
    fi
}

# =============================================================================
# Process Management
# =============================================================================

# Wait for a process to appear with timeout and exponential backoff
# Usage: wait_for_process "ProcessName" [timeout_seconds]
wait_for_process() {
    local name="$1"
    local timeout="${2:-30}"
    local max_delay=8
    local delay=1
    local elapsed=0

    while ! pgrep -x "$name" &>/dev/null; do
        if ((elapsed >= timeout)); then
            log_error "Timeout waiting for $name to start (${timeout}s)"
            return 1
        fi
        log_debug "Waiting for $name... (${elapsed}s/${timeout}s)"
        sleep "$delay"
        elapsed=$((elapsed + delay))
        delay=$((delay * 2 > max_delay ? max_delay : delay * 2))
    done
    return 0
}

# Wait for a process to exit with timeout
# Usage: wait_for_process_exit "ProcessName" [timeout_seconds]
wait_for_process_exit() {
    local name="$1"
    local timeout="${2:-30}"
    local elapsed=0

    while pgrep -x "$name" &>/dev/null; do
        if ((elapsed >= timeout)); then
            log_error "Timeout waiting for $name to exit (${timeout}s)"
            return 1
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 0
}

# =============================================================================
# User Interaction
# =============================================================================

# Prompt for confirmation with CI/non-interactive fallback
# Usage: confirm "Continue?" [default: y/n]
# Returns: 0 for yes, 1 for no
confirm() {
    local prompt="$1"
    local default="${2:-n}"

    # Non-interactive mode - use default
    if [[ ! -t 0 ]]; then
        log_debug "Non-interactive mode, using default: $default"
        [[ "$default" =~ ^[Yy] ]]
        return
    fi

    local yn_hint
    if [[ "$default" =~ ^[Yy] ]]; then
        yn_hint="[Y/n]"
    else
        yn_hint="[y/N]"
    fi

    read -p "$prompt $yn_hint " -n 1 -r
    echo

    if [[ -z "$REPLY" ]]; then
        [[ "$default" =~ ^[Yy] ]]
        return
    fi

    [[ $REPLY =~ ^[Yy]$ ]]
}

# =============================================================================
# JSON Utilities (requires jq)
# =============================================================================

# Get a value from JSON file
# Usage: json_get "file.json" "key"
json_get() {
    local file="$1"
    local key="$2"
    jq -r ".$key // empty" "$file"
}

# Validate JSON string
# Usage: echo "$json" | json_validate
json_validate() {
    jq empty 2>/dev/null
}

# =============================================================================
# Path Utilities
# =============================================================================

# Get the directory of the calling script
# Usage: SCRIPT_DIR=$(get_script_dir)
# Note: This should be called at the top of scripts, not from functions
get_script_dir() {
    cd "$(dirname "${BASH_SOURCE[1]}")" && pwd
}

# Get project root (assumes scripts are in scripts/ or scripts/helpers/)
# Usage: ROOT=$(get_project_root)
get_project_root() {
    local script_dir
    script_dir=$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)

    # Check if we're in helpers/
    if [[ "$(basename "$script_dir")" == "helpers" ]]; then
        dirname "$(dirname "$script_dir")"
    else
        dirname "$script_dir"
    fi
}
